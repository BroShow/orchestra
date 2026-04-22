# 04 — Orchestrator (LangGraph)

## Goal
A LangGraph state machine that drives the agent loop: receive a task, plan, call tools, observe results, decide whether to continue, and produce a final answer. State is checkpointed to Postgres so a crashed run can resume.

## Location
`packages/orchestrator/`

## Graph Definition (v1: single-agent loop)
Start with a single ReAct-style agent. Multi-agent orchestration is a v2 concern; resist building it now.

```
                ┌──────────┐
                │  start   │
                └────┬─────┘
                     │
                ┌────▼─────┐
         ┌──────│  agent   │◄─────────┐
         │      └────┬─────┘          │
         │           │                │
   needs tool?   final answer?    tool result
         │           │                │
    ┌────▼─────┐     │           ┌────┴────────┐
    │ approval │     │           │ tool_executor│
    │  gate    │     │           └──────────────┘
    └────┬─────┘     │                  ▲
         │           │                  │
    approved?        │              approved
         │           │
         └───────────┴────► tool_executor
                     │
                ┌────▼─────┐
                │   end    │
                └──────────┘
```

## State Schema
```python
from typing import Annotated, Sequence
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

class AgentState(BaseModel):
    # Conversation history (LangGraph's reducer appends)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    # Pending tool call awaiting human approval (None when no gate active)
    pending_approval: ToolCall | None = None
    # User's approval decision; agent reads then clears
    approval_decision: Literal["approved", "denied"] | None = None
    # Iteration counter to prevent infinite loops
    step_count: int = 0
    # Hard cap; node returns end if exceeded
    max_steps: int = 25
```

## Nodes
- **`agent`**: calls `ModelClient.complete()` with full message history + tool specs. Returns either a final assistant message or one with `tool_calls`.
- **`approval_gate`**: if the requested tool is in the approval-required set, set `pending_approval` and interrupt (`langgraph` supports `interrupt_before` natively). The API layer surfaces this as an SSE event.
- **`tool_executor`**: dispatches the tool call via the MCP client, appends a `ToolMessage` with the result.

## Routing Logic
```python
def should_continue(state: AgentState) -> str:
    last = state.messages[-1]
    if state.step_count >= state.max_steps:
        return "end"
    if isinstance(last, AIMessage) and last.tool_calls:
        if any(tc.name in REQUIRES_APPROVAL for tc in last.tool_calls):
            return "approval_gate"
        return "tool_executor"
    return "end"
```

## Checkpointing
Use LangGraph's Postgres checkpointer (`langgraph.checkpoint.postgres.PostgresSaver`). Every node transition persists state. On process restart, re-attach to a `thread_id` to resume exactly where it stopped.

## Public API
```python
# packages/orchestrator/orchestrator/runner.py

class OrchestratorRunner:
    def __init__(self, model_client: ModelClient, tool_registry: ToolRegistry, checkpointer: BaseCheckpointSaver): ...

    async def start_run(self, task: str, thread_id: str) -> AsyncIterator[RunEvent]:
        """Start a new run. Yields events for streaming to the UI."""

    async def resume_run(self, thread_id: str, approval: Literal["approved", "denied"] | None = None) -> AsyncIterator[RunEvent]:
        """Resume an interrupted run, optionally with an approval decision."""

    async def get_run_state(self, thread_id: str) -> AgentState:
        """Read current state without advancing."""
```

## Event Types Emitted
```python
class RunEvent(BaseModel):
    type: Literal[
        "step_start",
        "model_chunk",         # streaming token
        "tool_call_requested",
        "approval_required",   # surfaced when interrupt fires
        "tool_result",
        "step_end",
        "run_complete",
        "error",
    ]
    thread_id: str
    payload: dict
```

These events are what the API layer turns into SSE messages.

## Acceptance Criteria
- [ ] Graph compiles and runs end-to-end against the model adapter.
- [ ] State persists to Postgres; killing the process mid-run and restarting with the same `thread_id` resumes correctly.
- [ ] Approval gate fires for `shell.exec`, blocks until `resume_run(approval="approved"|"denied")` is called.
- [ ] Step limit prevents runaway loops; graph terminates with a clear error event when exceeded.
- [ ] Unit tests use a fake `ModelClient` that returns scripted responses; full graph behavior is testable without a live model.
- [ ] Integration test runs a 5+ step task against real Ollama and completes successfully.

## Anti-Goals (v1)
- No multi-agent orchestration (no team-lead/teammate pattern). Add in v2 once single-agent is solid.
- No long-term memory / RAG inside the graph. The vector store is wired up in persistence spec but the agent doesn't use it yet — keep the agent loop simple.
- No custom retry/backoff logic. LangGraph + checkpointer handles resume; rely on it.
