"""Test doubles used across orchestrator tests."""

from __future__ import annotations

from typing import Any, AsyncIterator

from model_adapter import (
    ModelClient,
    ModelMessage,
    ModelResponse,
    StreamChunk,
    ToolCall,
    ToolSpec,
    Usage,
)
from orchestrator.tool_runner import ToolRunner


class ScriptedModelClient(ModelClient):
    """Returns canned ModelResponse objects in order. Good enough to drive
    the graph through any deterministic path."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[list[ModelMessage]] = []

    async def complete(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ModelResponse:
        self.calls.append(list(messages))
        if not self.responses:
            raise AssertionError("ScriptedModelClient: ran out of responses")
        return self.responses.pop(0)

    async def stream(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        resp = await self.complete(messages, tools, model, temperature, max_tokens)
        if resp.content:
            yield StreamChunk(type="text", content=resp.content)
        for tc in resp.tool_calls:
            yield StreamChunk(type="tool_call_end", tool_call=tc)
        yield StreamChunk(type="done")


class FakeToolRunner(ToolRunner):
    """In-process tool runner. Holds a map of name -> callable and a
    requires_approval set."""

    def __init__(
        self,
        tools: dict[str, Any],
        approval_needed: set[str] | None = None,
    ) -> None:
        self.tools = tools
        self.approval_needed = approval_needed or set()
        self.calls: list[tuple[str, dict]] = []

    async def call(self, qualified_name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((qualified_name, arguments))
        fn = self.tools[qualified_name]
        return fn(**arguments)

    def requires_approval(self, qualified_name: str) -> bool:
        return qualified_name in self.approval_needed


def ai_response_with_tool_call(name: str, args: dict, call_id: str = "call_1") -> ModelResponse:
    return ModelResponse(
        content="",
        tool_calls=[ToolCall(id=call_id, name=name, arguments=args)],
        finish_reason="tool_calls",
        usage=Usage(),
    )


def ai_final_answer(text: str) -> ModelResponse:
    return ModelResponse(
        content=text,
        tool_calls=[],
        finish_reason="stop",
        usage=Usage(),
    )
