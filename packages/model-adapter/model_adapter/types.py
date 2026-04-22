"""Schema for the model adapter's public interface.

Provider implementations normalize to these types so the orchestrator never
sees provider-specific shapes.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


class ModelMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class ModelResponse(BaseModel):
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: Literal["stop", "tool_calls", "length", "error"]
    usage: Usage = Field(default_factory=Usage)


class StreamChunk(BaseModel):
    type: Literal["text", "tool_call_start", "tool_call_delta", "tool_call_end", "done"]
    content: str | None = None
    tool_call: ToolCall | None = None


class TaskClass(str, Enum):
    CLASSIFY = "classify"
    REASON = "reason"
    HEAVY = "heavy"
