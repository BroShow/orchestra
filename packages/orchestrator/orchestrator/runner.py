"""OrchestratorRunner — the public entry point for starting and resuming runs.

Yields RunEvents that the API layer turns into SSE messages. The graph does
the real work; this class is a thin adapter that:
  - accepts a natural-language task + thread_id,
  - streams graph updates as RunEvents,
  - pauses when approval is needed (via LangGraph's interrupt_before),
  - resumes with an approval decision.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command

from model_adapter import ModelClient, ToolSpec
from orchestrator.events import RunEvent
from orchestrator.graph import build_graph
from orchestrator.state import AgentState
from orchestrator.tool_runner import ToolRunner


class OrchestratorRunner:
    def __init__(
        self,
        model_client: ModelClient,
        tool_runner: ToolRunner,
        tool_specs: list[ToolSpec],
        checkpointer: BaseCheckpointSaver,
    ) -> None:
        self.graph = build_graph(model_client, tool_runner, tool_specs, checkpointer)

    async def start_run(
        self, task: str, thread_id: str
    ) -> AsyncIterator[RunEvent]:
        """Start a new run. Yields RunEvents."""
        initial: dict[str, Any] = {"messages": [HumanMessage(content=task)]}
        async for ev in self._stream(initial, thread_id):
            yield ev

    async def resume_run(
        self, thread_id: str, approval: str | None = None
    ) -> AsyncIterator[RunEvent]:
        """Resume a paused run.

        `approval` must be 'approved' or 'denied' if the run paused at an
        approval gate. For any other resume (e.g., after a crash with no
        approval needed), pass None.
        """
        if approval is not None and approval not in ("approved", "denied"):
            raise ValueError(
                f"approval must be 'approved' or 'denied', got {approval!r}"
            )
        input_ = Command(resume=approval) if approval is not None else None
        async for ev in self._stream(input_, thread_id):
            yield ev

    async def get_run_state(self, thread_id: str) -> AgentState:
        """Snapshot the current state without advancing the graph."""
        snap = await self.graph.aget_state(_config(thread_id))
        values = snap.values if snap else {}
        return AgentState.model_validate(values or {})

    async def _stream(
        self, input_: Any, thread_id: str
    ) -> AsyncIterator[RunEvent]:
        config = _config(thread_id)
        interrupted = False
        try:
            async for event in self.graph.astream(input_, config, stream_mode="updates"):
                for node, update in event.items():
                    if node == "__interrupt__":
                        # update is a tuple of Interrupt objects. Emit one
                        # approval_required per interrupt (usually just one).
                        for ir in update or ():
                            payload = getattr(ir, "value", {}) or {}
                            yield RunEvent(
                                type="approval_required",
                                thread_id=thread_id,
                                payload=payload if isinstance(payload, dict) else {"value": payload},
                            )
                        interrupted = True
                        continue
                    if node.startswith("__") or not isinstance(update, dict):
                        continue
                    for e in _events_from_node(node, update, thread_id):
                        yield e
        except Exception as e:
            yield RunEvent(
                type="error",
                thread_id=thread_id,
                payload={"message": str(e), "exception": type(e).__name__},
            )
            return

        if interrupted:
            return

        # Terminal — final assistant message as the result.
        snap = await self.graph.aget_state(config)
        if not list(getattr(snap, "next", ()) or []):
            messages = (snap.values or {}).get("messages") or []
            final = _last_ai_text(messages)
            yield RunEvent(
                type="run_complete",
                thread_id=thread_id,
                payload={"final": final},
            )


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _events_from_node(
    node: str, update: dict, thread_id: str
) -> list[RunEvent]:
    out: list[RunEvent] = []
    if update is None:
        return out
    messages = update.get("messages") or []

    if node == "agent":
        out.append(
            RunEvent(type="step_start", thread_id=thread_id, payload={"node": node})
        )
        for m in messages:
            if isinstance(m, AIMessage):
                if m.content:
                    out.append(
                        RunEvent(
                            type="model_chunk",
                            thread_id=thread_id,
                            payload={"text": m.content},
                        )
                    )
                for tc in m.tool_calls or []:
                    out.append(
                        RunEvent(
                            type="tool_call_requested",
                            thread_id=thread_id,
                            payload={
                                "tool": tc["name"],
                                "arguments": tc.get("args") or {},
                                "tool_call_id": tc["id"],
                            },
                        )
                    )
        out.append(
            RunEvent(type="step_end", thread_id=thread_id, payload={"node": node})
        )
    elif node in ("tool_executor", "tool_denied"):
        for m in messages:
            if isinstance(m, ToolMessage):
                out.append(
                    RunEvent(
                        type="tool_result",
                        thread_id=thread_id,
                        payload={
                            "tool_call_id": m.tool_call_id,
                            "content": m.content,
                            "denied": node == "tool_denied",
                        },
                    )
                )
    # approval_gate itself is a passthrough — the approval_required event is
    # emitted after the stream interrupts, in _stream().
    return out


def _last_ai_text(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            content = m.content
            if isinstance(content, str):
                return content
    return ""
