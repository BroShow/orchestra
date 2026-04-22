"""RoutingClient — picks a model per call based on a TaskClass hint."""

from __future__ import annotations

from typing import AsyncIterator

from model_adapter.client import ModelClient
from model_adapter.types import (
    ModelMessage,
    ModelResponse,
    StreamChunk,
    TaskClass,
    ToolSpec,
)


class RoutingClient(ModelClient):
    """Wraps a base ModelClient and selects a model per TaskClass hint.

    Passing `task_class` through kwargs is intentional — it keeps the base
    ModelClient interface narrow, and the orchestrator can opt in without
    every caller threading a new parameter.
    """

    def __init__(self, inner: ModelClient, task_model_map: dict[TaskClass, str]) -> None:
        self.inner = inner
        self.task_model_map = task_model_map

    def _resolve(self, task_class: TaskClass | None, explicit_model: str | None) -> str | None:
        if explicit_model is not None:
            return explicit_model
        if task_class is None:
            return None
        return self.task_model_map.get(task_class)

    async def complete(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        task_class: TaskClass | None = TaskClass.REASON,
    ) -> ModelResponse:
        resolved = self._resolve(task_class, model)
        return await self.inner.complete(
            messages=messages,
            tools=tools,
            model=resolved,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def stream(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        task_class: TaskClass | None = TaskClass.REASON,
    ) -> AsyncIterator[StreamChunk]:
        resolved = self._resolve(task_class, model)
        async for chunk in self.inner.stream(
            messages=messages,
            tools=tools,
            model=resolved,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk
