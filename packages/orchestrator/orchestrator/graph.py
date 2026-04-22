"""LangGraph state machine: agent → [approval_gate] → tool_executor → agent loop.

Graph shape (matches spec 04):
    START
      │
      ▼
    ┌─────────┐
    │  agent  │◄──────────┐
    └────┬────┘           │
         │                │
    should_continue       │
         │                │
   ┌─────┴─────┬──────────┤
   │           │          │
   ▼           ▼          │
  END   approval_gate     │
         │         │      │
    approved?   denied?   │
         │         │      │
         ▼         ▼      │
  tool_executor  tool_denied
         │         │      │
         └────┬────┘      │
              ▼           │
           (loop)─────────┘

`approval_gate` is marked `interrupt_before` in compile(), so the graph
halts between `agent` and `approval_gate`. The API layer reads
`pending_approval` from the state snapshot, surfaces it to the UI, and on
resume provides `approval_decision` via Command(update=...).
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from model_adapter import ModelClient, ToolCall, ToolSpec
from orchestrator._messages import ai_message_from_response, to_model_messages
from orchestrator.state import AgentState
from orchestrator.tool_runner import ToolRunner


def _find_pending_approval(
    tool_calls: list[ToolCall], tool_runner: ToolRunner
) -> ToolCall | None:
    for tc in tool_calls:
        if tool_runner.requires_approval(tc.name):
            return tc
    return None


def build_graph(
    model: ModelClient,
    tool_runner: ToolRunner,
    tool_specs: list[ToolSpec],
    checkpointer: BaseCheckpointSaver,
) -> Any:
    """Compile the agent graph. Closures capture model, tool_runner, tool_specs."""

    async def agent_node(state: AgentState) -> dict:
        resp = await model.complete(
            messages=to_model_messages(list(state.messages)),
            tools=tool_specs,
        )
        ai_msg = ai_message_from_response(resp.content, resp.tool_calls)

        pending = _find_pending_approval(resp.tool_calls, tool_runner)

        return {
            "messages": [ai_msg],
            "pending_approval": pending,
            "step_count": state.step_count + 1,
        }

    def should_continue(state: AgentState) -> str:
        if state.step_count >= state.max_steps:
            return "end"
        last = state.messages[-1] if state.messages else None
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return "end"
        if state.pending_approval is not None and state.approval_decision is None:
            return "approval_gate"
        return "tool_executor"

    async def approval_gate_node(state: AgentState) -> dict:
        # Dynamic interrupt: halts until the caller resumes with
        # Command(resume="approved"|"denied"). On the first pass through this
        # node, interrupt() raises GraphInterrupt and the graph checkpoints;
        # on resume, interrupt() returns the value that Command(resume=...)
        # supplied.
        pending = state.pending_approval
        payload = (
            {
                "tool": pending.name,
                "arguments": pending.arguments,
                "tool_call_id": pending.id,
            }
            if pending is not None
            else {}
        )
        decision = interrupt(payload)
        if decision not in ("approved", "denied"):
            raise ValueError(
                f"Approval resume must be 'approved' or 'denied', got {decision!r}"
            )
        return {"approval_decision": decision}

    def after_approval(state: AgentState) -> str:
        if state.approval_decision == "approved":
            return "tool_executor"
        return "tool_denied"

    async def tool_executor_node(state: AgentState) -> dict:
        last = state.messages[-1]
        assert isinstance(last, AIMessage)
        tool_messages: list[ToolMessage] = []
        for tc in last.tool_calls:
            name = tc["name"]
            args = tc.get("args") or {}
            try:
                result = await tool_runner.call(name, args)
                content = result if isinstance(result, str) else str(result)
            except Exception as e:
                content = f"[tool {name} failed] {type(e).__name__}: {e}"
            tool_messages.append(ToolMessage(content=content, tool_call_id=tc["id"]))
        return {
            "messages": tool_messages,
            "pending_approval": None,
            "approval_decision": None,
        }

    async def tool_denied_node(state: AgentState) -> dict:
        last = state.messages[-1]
        assert isinstance(last, AIMessage)
        refusals: list[ToolMessage] = []
        for tc in last.tool_calls:
            refusals.append(
                ToolMessage(
                    content=f"User denied execution of tool '{tc['name']}'.",
                    tool_call_id=tc["id"],
                )
            )
        return {
            "messages": refusals,
            "pending_approval": None,
            "approval_decision": None,
        }

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("approval_gate", approval_gate_node)
    graph.add_node("tool_executor", tool_executor_node)
    graph.add_node("tool_denied", tool_denied_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "end": END,
            "approval_gate": "approval_gate",
            "tool_executor": "tool_executor",
        },
    )
    graph.add_conditional_edges(
        "approval_gate",
        after_approval,
        {
            "tool_executor": "tool_executor",
            "tool_denied": "tool_denied",
        },
    )
    graph.add_edge("tool_executor", "agent")
    graph.add_edge("tool_denied", "agent")

    return graph.compile(checkpointer=checkpointer)
