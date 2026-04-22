"""Request/response Pydantic models for the API routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    task: str = Field(..., min_length=1)


class CreateRunResponse(BaseModel):
    thread_id: str
    status: str


class ApprovalRequest(BaseModel):
    decision: Literal["approved", "denied"]


class ApprovalResponse(BaseModel):
    thread_id: str
    status: str


class RunSnapshot(BaseModel):
    thread_id: str
    task: str
    status: str
    step_count: int
    messages: list[dict[str, Any]]
    pending_approval: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class RunListItem(BaseModel):
    thread_id: str
    task: str
    status: str
    created_at: datetime
    updated_at: datetime


class RunListResponse(BaseModel):
    runs: list[RunListItem]
    total: int
