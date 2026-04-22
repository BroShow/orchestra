"""Coordinates the orchestrator with persistence and live subscribers.

Per-run lifecycle:
  1. POST /runs creates a Run row (status=running) and spawns a background
     task that calls runner.start_run(task, thread_id).
  2. Each event from the runner is persisted to run_events (via append_event,
     giving it a monotonic seq) and fanned out to every live subscriber of
     that thread_id.
  3. SSE clients subscribe via `subscribe(thread_id, last_event_id)`:
       - first, replay events from run_events with seq > last_event_id,
       - then, drain any queued live events (deduping by seq),
       - then, pull new events live until the run reaches a terminal state
         or the client disconnects.

The single-process design fits the single-user PoC. The queue-plus-replay
pattern is the one piece of architecture worth keeping when this grows —
it means SSE reconnects survive server restarts as long as the events live
in the DB.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from orchestrator import OrchestratorRunner, RunEvent
from orchestrator.persistence import (
    Run,
    RunEvent as DBRunEvent,
    RunStatus,
    append_event,
    new_run_id,
    replay_events,
)

log = logging.getLogger(__name__)


@dataclass
class _RunHandle:
    thread_id: str
    task: asyncio.Task
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    # terminal_event is set by the background task when the run is done.
    # Subscribers check it to know they can close.
    terminal: asyncio.Event = field(default_factory=asyncio.Event)


class RunManager:
    def __init__(
        self,
        runner: OrchestratorRunner,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.runner = runner
        self.session_factory = session_factory
        self._handles: dict[str, _RunHandle] = {}
        self._lock = asyncio.Lock()

    # ---------- public surface ----------

    async def create_run(self, task_text: str) -> str:
        thread_id = new_run_id()
        async with self.session_factory() as s:
            s.add(
                Run(
                    id=thread_id,
                    task=task_text,
                    status=RunStatus.RUNNING.value,
                )
            )
            await s.commit()

        task = asyncio.create_task(self._drive_start(task_text, thread_id))
        self._handles[thread_id] = _RunHandle(thread_id=thread_id, task=task)
        return thread_id

    async def approve(self, thread_id: str, decision: str) -> None:
        async with self.session_factory() as s:
            run = await s.get(Run, thread_id)
            if run is None:
                raise KeyError(f"No such run: {thread_id}")
            if run.status != RunStatus.AWAITING_APPROVAL.value:
                raise ConflictError(
                    f"Run {thread_id} is not awaiting approval (status={run.status})"
                )
            run.status = RunStatus.RUNNING.value
            await s.commit()

        # If a handle exists (same-process), reuse it; else create a fresh one.
        handle = self._handles.get(thread_id)
        if handle is None or handle.task.done():
            task = asyncio.create_task(self._drive_resume(thread_id, decision))
            self._handles[thread_id] = _RunHandle(thread_id=thread_id, task=task)
        else:
            # There's already a task running for this run. Spawn a sibling
            # task for the resume — it'll share subscribers via the handle.
            asyncio.create_task(self._drive_resume(thread_id, decision))

    async def cancel(self, thread_id: str) -> None:
        async with self.session_factory() as s:
            run = await s.get(Run, thread_id)
            if run is None:
                raise KeyError(f"No such run: {thread_id}")
            if run.status in (RunStatus.COMPLETE.value, RunStatus.ERROR.value, RunStatus.CANCELLED.value):
                return
            run.status = RunStatus.CANCELLED.value
            run.completed_at = datetime.now(tz=timezone.utc)
            await s.commit()

        handle = self._handles.get(thread_id)
        if handle and not handle.task.done():
            handle.task.cancel()
            handle.terminal.set()

    async def snapshot(self, thread_id: str) -> dict[str, Any]:
        async with self.session_factory() as s:
            run = await s.get(Run, thread_id)
            if run is None:
                raise KeyError(f"No such run: {thread_id}")
            state = await self.runner.get_run_state(thread_id)

            messages_out: list[dict[str, Any]] = []
            for m in state.messages or []:
                messages_out.append(
                    {
                        "type": type(m).__name__,
                        "content": getattr(m, "content", ""),
                        "tool_calls": getattr(m, "tool_calls", None),
                        "tool_call_id": getattr(m, "tool_call_id", None),
                    }
                )

            pending = None
            if state.pending_approval is not None:
                pending = {
                    "tool": state.pending_approval.name,
                    "arguments": state.pending_approval.arguments,
                    "tool_call_id": state.pending_approval.id,
                }

            return {
                "thread_id": run.id,
                "task": run.task,
                "status": run.status,
                "step_count": state.step_count,
                "messages": messages_out,
                "pending_approval": pending,
                "created_at": run.created_at,
                "updated_at": run.updated_at,
                "completed_at": run.completed_at,
                "error_message": run.error_message,
            }

    async def list_runs(self, limit: int = 50, offset: int = 0) -> tuple[list[Run], int]:
        async with self.session_factory() as s:
            total = await s.scalar(select(func.count()).select_from(Run))
            rows = await s.scalars(
                select(Run).order_by(Run.created_at.desc()).limit(limit).offset(offset)
            )
            return list(rows), int(total or 0)

    @asynccontextmanager
    async def subscribe(
        self, thread_id: str, last_event_id: int | None = None
    ) -> AsyncIterator[AsyncIterator[tuple[int, RunEvent]]]:
        """Yield an async iterator of (seq, event) tuples.

        First replays persisted events after `last_event_id`, then pulls live
        events from an in-memory queue. Deduplicates across the replay/live
        boundary using seq.
        """
        # ensure the run exists
        async with self.session_factory() as s:
            run = await s.get(Run, thread_id)
            if run is None:
                raise KeyError(f"No such run: {thread_id}")

        # Create a queue for this subscriber BEFORE the replay, so any events
        # landing during the replay are captured (will be deduped by seq).
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        handle = self._handles.get(thread_id)
        if handle is not None:
            handle.subscribers.append(queue)

        async def _iter() -> AsyncIterator[tuple[int, RunEvent]]:
            emitted_max_seq = last_event_id if last_event_id is not None else -1

            # Replay persisted events past last_event_id.
            async with self.session_factory() as s:
                events = await replay_events(s, thread_id, after_seq=last_event_id)
            for ev in events:
                if ev.seq <= emitted_max_seq:
                    continue
                emitted_max_seq = ev.seq
                yield ev.seq, RunEvent(
                    type=ev.event_type,  # type: ignore[arg-type]
                    thread_id=thread_id,
                    payload=dict(ev.payload or {}),
                )

            # Drain queue — live events. Stop when the handle's terminal is
            # set AND the queue is empty.
            while True:
                if handle is None:
                    # No active handle: just terminate after replay.
                    break
                try:
                    seq, ev = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    if handle.terminal.is_set() and queue.empty():
                        return
                    continue
                if seq <= emitted_max_seq:
                    continue
                emitted_max_seq = seq
                yield seq, ev

        try:
            yield _iter()
        finally:
            if handle is not None:
                try:
                    handle.subscribers.remove(queue)
                except ValueError:
                    pass

    # ---------- internals ----------

    async def _drive_start(self, task_text: str, thread_id: str) -> None:
        try:
            async for ev in self.runner.start_run(task_text, thread_id):
                await self._persist_and_fanout(thread_id, ev)
            await self._finalize(thread_id, default_status=RunStatus.COMPLETE)
        except asyncio.CancelledError:
            log.info("run %s cancelled", thread_id)
            raise
        except Exception as e:  # surfaces as an error event
            log.exception("run %s failed", thread_id)
            await self._persist_and_fanout(
                thread_id,
                RunEvent(
                    type="error",
                    thread_id=thread_id,
                    payload={"message": str(e), "exception": type(e).__name__},
                ),
            )
            await self._finalize(thread_id, default_status=RunStatus.ERROR, error=str(e))

    async def _drive_resume(self, thread_id: str, decision: str) -> None:
        try:
            async for ev in self.runner.resume_run(thread_id, approval=decision):
                await self._persist_and_fanout(thread_id, ev)
            await self._finalize(thread_id, default_status=RunStatus.COMPLETE)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("run %s failed on resume", thread_id)
            await self._persist_and_fanout(
                thread_id,
                RunEvent(
                    type="error",
                    thread_id=thread_id,
                    payload={"message": str(e), "exception": type(e).__name__},
                ),
            )
            await self._finalize(thread_id, default_status=RunStatus.ERROR, error=str(e))

    async def _persist_and_fanout(self, thread_id: str, ev: RunEvent) -> None:
        async with self.session_factory() as s:
            row = await append_event(s, thread_id, ev.type, ev.payload)
            seq = row.seq
            # Update run.status if the event tells us something meaningful.
            if ev.type == "approval_required":
                run = await s.get(Run, thread_id)
                if run is not None:
                    run.status = RunStatus.AWAITING_APPROVAL.value
            await s.commit()

        handle = self._handles.get(thread_id)
        if handle is None:
            return
        dead: list[asyncio.Queue] = []
        for q in handle.subscribers:
            try:
                q.put_nowait((seq, ev))
            except asyncio.QueueFull:
                # slow consumer — drop it so we don't block the whole run
                dead.append(q)
        for q in dead:
            try:
                handle.subscribers.remove(q)
            except ValueError:
                pass

    async def _finalize(
        self,
        thread_id: str,
        default_status: RunStatus,
        error: str | None = None,
    ) -> None:
        async with self.session_factory() as s:
            run = await s.get(Run, thread_id)
            if run is None:
                return
            # Don't overwrite awaiting_approval with complete — the run is
            # paused, not finished.
            if run.status == RunStatus.AWAITING_APPROVAL.value:
                pass
            else:
                run.status = default_status.value
                run.completed_at = datetime.now(tz=timezone.utc)
                if error is not None:
                    run.error_message = error
            await s.commit()
            status_after = run.status

        handle = self._handles.get(thread_id)
        # Only release subscribers if the run is actually terminal.
        if handle is not None and status_after != RunStatus.AWAITING_APPROVAL.value:
            handle.terminal.set()


class ConflictError(RuntimeError):
    """Raised when an operation is illegal given the run's current state."""
