"""OpenAI-compatible provider — works for OpenAI itself and any vLLM/TGI/etc.
server that implements /v1/chat/completions."""

from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator

import httpx

from model_adapter.client import ModelClient
from model_adapter.types import (
    ModelMessage,
    ModelResponse,
    StreamChunk,
    ToolCall,
    ToolSpec,
    Usage,
)


class OpenAICompatProvider(ModelClient):
    def __init__(self, base_url: str, api_key: str | None, default_model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def complete(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ModelResponse:
        body = self._build_body(messages, tools, model, temperature, max_tokens, stream=False)
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
        return _parse_openai_response(data)

    async def stream(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        body = self._build_body(messages, tools, model, temperature, max_tokens, stream=True)
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        yield StreamChunk(type="done")
                        return
                    if not payload:
                        continue
                    chunk = json.loads(payload)
                    choice = (chunk.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}
                    text = delta.get("content")
                    if text:
                        yield StreamChunk(type="text", content=text)
                    for tc in delta.get("tool_calls") or []:
                        yield StreamChunk(
                            type="tool_call_delta",
                            tool_call=_normalize_openai_tool_call(tc),
                        )

    def _build_body(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None,
        model: str | None,
        temperature: float,
        max_tokens: int | None,
        stream: bool,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": [_message_to_openai(m) for m in messages],
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
        return body


def _message_to_openai(m: ModelMessage) -> dict[str, Any]:
    d: dict[str, Any] = {"role": m.role, "content": m.content}
    if m.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
            }
            for tc in m.tool_calls
        ]
    if m.tool_call_id and m.role == "tool":
        d["tool_call_id"] = m.tool_call_id
    return d


def _normalize_openai_tool_call(tc: dict[str, Any]) -> ToolCall:
    fn = tc.get("function") or {}
    raw_args = fn.get("arguments") or "{}"
    if isinstance(raw_args, str):
        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            args = {"_raw": raw_args}
    else:
        args = raw_args
    return ToolCall(
        id=tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
        name=fn.get("name") or "",
        arguments=args,
    )


def _parse_openai_response(data: dict[str, Any]) -> ModelResponse:
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content = msg.get("content") or ""
    raw_calls = msg.get("tool_calls") or []
    tool_calls = [_normalize_openai_tool_call(tc) for tc in raw_calls]
    finish = choice.get("finish_reason") or ("tool_calls" if tool_calls else "stop")
    if finish not in ("stop", "tool_calls", "length", "error"):
        finish = "stop"
    usage_data = data.get("usage") or {}
    return ModelResponse(
        content=content,
        tool_calls=tool_calls,
        finish_reason=finish,
        usage=Usage(
            input_tokens=int(usage_data.get("prompt_tokens") or 0),
            output_tokens=int(usage_data.get("completion_tokens") or 0),
        ),
    )
