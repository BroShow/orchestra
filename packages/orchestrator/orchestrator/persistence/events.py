"""Event log: append-only writes + sequential replay.

The event log is the source for SSE replay (spec 05) and audit. The source
of truth for *agent state* is still the LangGraph checkpoint; events are
what the UI consumes.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.persistence.models import RunEvent


async def append_event(
    session: AsyncSession,
    run_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> RunEvent:
    """Append an event. `seq` is auto-assigned as max(seq)+1 for the run.

    Concurrent writers for the same run would race on this; in the PoC only
    one orchestrator task writes per run, so the simple approach is fine.
    """
    last_seq = await session.scalar(
        select(func.coalesce(func.max(RunEvent.seq), -1)).where(RunEvent.run_id == run_id)
    )
    event = RunEvent(
        run_id=run_id,
        seq=(last_seq or 0) + 1,
        event_type=event_type,
        payload=payload,
    )
    session.add(event)
    await session.flush()
    return event


async def replay_events(
    session: AsyncSession,
    run_id: str,
    after_seq: int | None = None,
) -> list[RunEvent]:
    """Return events in sequence order. `after_seq` is exclusive for resume."""
    stmt = select(RunEvent).where(RunEvent.run_id == run_id)
    if after_seq is not None:
        stmt = stmt.where(RunEvent.seq > after_seq)
    stmt = stmt.order_by(RunEvent.seq)
    result = await session.scalars(stmt)
    return list(result)
