"""Ollama provider — direct httpx against /api/chat.

We deliberately skip `langchain-ollama` here because we want explicit control
over the tool-call normalization: Ollama's tool output shape varies by model
and by whether native tool-calling is supported at all. `langchain-ollama`
hides some of that variance behind its own message types.
"""

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


class OllamaProvider(ModelClient):
    def __init__(self, base_url: str, default_model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    # ---------- complete ----------

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
            resp = await client.post(f"{self.base_url}/api/chat", json=body)
            resp.raise_for_status()
            data = resp.json()
        return self._parse_response(data)

    # ---------- stream ----------

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
            async with client.stream("POST", f"{self.base_url}/api/chat", json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    msg = data.get("message") or {}
                    content = msg.get("content")
                    if content:
                        yield StreamChunk(type="text", content=content)
                    tool_calls = msg.get("tool_calls") or []
                    for tc in tool_calls:
                        yield StreamChunk(
                            type="tool_call_end",
                            tool_call=_normalize_tool_call(tc),
                        )
                    if data.get("done"):
                        yield StreamChunk(type="done")
                        return

    # ---------- internals ----------

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
            "messages": [_message_to_ollama(m) for m in messages],
            "stream": stream,
            "options": {"temperature": temperature},
        }
        if max_tokens is not None:
            body["options"]["num_predict"] = max_tokens
        if tools:
            body["tools"] = [_tool_to_ollama(t) for t in tools]
        return body

    def _parse_response(self, data: dict[str, Any]) -> ModelResponse:
        msg = data.get("message") or {}
        content = msg.get("content") or ""
        raw_calls = msg.get("tool_calls") or []
        tool_calls = [_normalize_tool_call(tc) for tc in raw_calls]
        finish = "tool_calls" if tool_calls else "stop"
        usage = Usage(
            input_tokens=int(data.get("prompt_eval_count") or 0),
            output_tokens=int(data.get("eval_count") or 0),
        )
        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish,
            usage=usage,
        )


def _message_to_ollama(m: ModelMessage) -> dict[str, Any]:
    d: dict[str, Any] = {"role": m.role, "content": m.content}
    if m.tool_calls:
        d["tool_calls"] = [
            {"function": {"name": tc.name, "arguments": tc.arguments}}
            for tc in m.tool_calls
        ]
    if m.tool_call_id and m.role == "tool":
        d["tool_call_id"] = m.tool_call_id
    return d


def _tool_to_ollama(t: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        },
    }


def _normalize_tool_call(tc: dict[str, Any]) -> ToolCall:
    fn = tc.get("function") or {}
    args = fn.get("arguments") or tc.get("arguments") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {"_raw": args}
    return ToolCall(
        id=tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
        name=fn.get("name") or tc.get("name") or "",
        arguments=args,
    )
