"""Runs + events round-trip through the ORM."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from orchestrator.persistence import Run, RunEvent, RunStatus, new_run_id


async def test_insert_and_read_run(session_factory):
    async with session_factory() as s:
        run = Run(id=new_run_id(), task="do a thing", status=RunStatus.RUNNING.value)
        s.add(run)
        await s.commit()

        fetched = await s.get(Run, run.id)
        assert fetched is not None
        assert fetched.task == "do a thing"
        assert fetched.status == "running"


async def test_run_id_format():
    rid = new_run_id()
    assert rid.startswith("run_")
    assert len(rid) > 20  # ULID is 26 chars


async def test_event_log_sequential(session_factory):
    from orchestrator.persistence import append_event, replay_events

    run_id = new_run_id()
    async with session_factory() as s:
        s.add(Run(id=run_id, task="x"))
        await s.commit()

        await append_event(s, run_id, "step_start", {"step": 1})
        await append_event(s, run_id, "model_chunk", {"text": "hello"})
        await append_event(s, run_id, "step_end", {})
        await s.commit()

        events = await replay_events(s, run_id)
        assert [e.event_type for e in events] == ["step_start", "model_chunk", "step_end"]
        assert [e.seq for e in events] == [0, 1, 2]


async def test_event_log_replay_after_seq(session_factory):
    from orchestrator.persistence import append_event, replay_events

    run_id = new_run_id()
    async with session_factory() as s:
        s.add(Run(id=run_id, task="x"))
        for _ in range(5):
            await append_event(s, run_id, "model_chunk", {})
        await s.commit()

        after = await replay_events(s, run_id, after_seq=1)
        assert [e.seq for e in after] == [2, 3, 4]


async def test_cascade_delete(session_factory):
    from orchestrator.persistence import append_event

    run_id = new_run_id()
    async with session_factory() as s:
        s.add(Run(id=run_id, task="x"))
        await append_event(s, run_id, "step_start", {})
        await append_event(s, run_id, "step_end", {})
        await s.commit()

        run = await s.get(Run, run_id)
        await s.delete(run)
        await s.commit()

        remaining = await s.scalars(select(RunEvent).where(RunEvent.run_id == run_id))
        assert list(remaining) == []


async def test_unique_constraint_on_seq(session_factory):
    from sqlalchemy.exc import IntegrityError

    run_id = new_run_id()
    async with session_factory() as s:
        s.add(Run(id=run_id, task="x"))
        s.add(RunEvent(run_id=run_id, seq=0, event_type="a", payload={}))
        await s.commit()

        s.add(RunEvent(run_id=run_id, seq=0, event_type="b", payload={}))
        with pytest.raises(IntegrityError):
            await s.commit()
