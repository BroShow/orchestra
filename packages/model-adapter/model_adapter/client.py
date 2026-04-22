"""Abstract ModelClient — orchestration code only ever talks to this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from model_adapter.types import (
    ModelMessage,
    ModelResponse,
    StreamChunk,
    ToolSpec,
)


class ModelClient(ABC):
    """Provider-agnostic LLM client.

    Each provider subclasses this. The orchestrator imports only this class
    and the types in `model_adapter.types`.
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ModelResponse:
        """One-shot completion. Returns a full ModelResponse."""

    @abstractmethod
    def stream(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Streaming completion. Yields StreamChunks ending with type='done'."""
