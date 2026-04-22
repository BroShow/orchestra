"""Anthropic provider — stub for v1.

The file must exist so the abstraction is proven (spec 02 acceptance
criterion). Wire up the real Anthropic SDK call when a user opts into
paid inference. Until then, any attempt to use this provider raises
NotImplementedError with a clear message.
"""

from __future__ import annotations

from typing import AsyncIterator

from model_adapter.client import ModelClient
from model_adapter.types import (
    ModelMessage,
    ModelResponse,
    StreamChunk,
    ToolSpec,
)


class AnthropicProvider(ModelClient):
    def __init__(self, api_key: str | None, default_model: str) -> None:
        self.api_key = api_key
        self.default_model = default_model

    async def complete(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ModelResponse:
        raise NotImplementedError(
            "AnthropicProvider.complete is a v1 stub. Wire the Anthropic SDK here "
            "when you're ready to spend on inference."
        )

    async def stream(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        raise NotImplementedError(
            "AnthropicProvider.stream is a v1 stub."
        )
        # unreachable, but satisfies the async-generator return type
        yield  # type: ignore[unreachable]
