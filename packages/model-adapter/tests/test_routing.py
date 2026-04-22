"""RoutingClient resolves the right model per TaskClass."""

from __future__ import annotations

from typing import AsyncIterator

from model_adapter import (
    ModelClient,
    ModelMessage,
    ModelResponse,
    RoutingClient,
    StreamChunk,
    TaskClass,
    ToolSpec,
    Usage,
)


class Recorder(ModelClient):
    def __init__(self) -> None:
        self.last_model: str | None = None

    async def complete(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ModelResponse:
        self.last_model = model
        return ModelResponse(content="", finish_reason="stop", usage=Usage())

    async def stream(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        self.last_model = model
        yield StreamChunk(type="done")


MAP = {
    TaskClass.CLASSIFY: "llama3.2:3b",
    TaskClass.REASON: "qwen2.5:14b",
    TaskClass.HEAVY: "qwen2.5:32b",
}


async def test_routes_by_task_class():
    inner = Recorder()
    router = RoutingClient(inner, MAP)
    await router.complete(messages=[], task_class=TaskClass.HEAVY)
    assert inner.last_model == "qwen2.5:32b"


async def test_explicit_model_wins_over_task_class():
    inner = Recorder()
    router = RoutingClient(inner, MAP)
    await router.complete(messages=[], model="custom-model", task_class=TaskClass.CLASSIFY)
    assert inner.last_model == "custom-model"


async def test_default_task_class_is_reason():
    inner = Recorder()
    router = RoutingClient(inner, MAP)
    await router.complete(messages=[])
    assert inner.last_model == "qwen2.5:14b"
