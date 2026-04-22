"""AgentState — the LangGraph state schema for a single agent run."""

from __future__ import annotations

from typing import Annotated, Literal, Sequence

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from model_adapter import ToolCall


class AgentState(BaseModel):
    """Per-run state. LangGraph checkpoints one of these per thread_id."""

    # Conversation history. LangGraph's reducer appends to this list.
    messages: Annotated[Sequence[BaseMessage], add_messages] = Field(default_factory=list)

    # The tool call currently awaiting human approval. None when no gate is active.
    pending_approval: ToolCall | None = None

    # The user's decision on the pending approval. Cleared after each use.
    approval_decision: Literal["approved", "denied"] | None = None

    # Iteration counter to prevent infinite agent loops.
    step_count: int = 0

    # Hard cap; graph terminates with an error once exceeded.
    max_steps: int = 25

    model_config = {"arbitrary_types_allowed": True}
