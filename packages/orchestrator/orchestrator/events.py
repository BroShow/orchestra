"""RunEvent — what the orchestrator yields; what the API layer turns into SSE."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RunEventType = Literal[
    "step_start",
    "model_chunk",
    "tool_call_requested",
    "approval_required",
    "tool_result",
    "step_end",
    "run_complete",
    "error",
]


class RunEvent(BaseModel):
    type: RunEventType
    thread_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
