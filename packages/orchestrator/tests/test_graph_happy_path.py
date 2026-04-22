"""Graph flows end-to-end against scripted model + fake tools."""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver

from orchestrator import OrchestratorRunner
from tests.fakes import (
    FakeToolRunner,
    ScriptedModelClient,
    ai_final_answer,
    ai_response_with_tool_call,
)


@pytest.fixture
def checkpointer() -> MemorySaver:
    return MemorySaver()


@pytest.fixture
def tool_runner() -> FakeToolRunner:
    return FakeToolRunner(
        tools={
            "fs.read_file": lambda path: f"<contents of {path}>",
            "web.fetch": lambda url, max_chars=20_000: f"<page at {url}>",
        }
    )


async def test_simple_final_answer(checkpointer, tool_runner):
    model = ScriptedModelClient([ai_final_answer("here is the answer")])
    runner = OrchestratorRunner(
        model_client=model,
        tool_runner=tool_runner,
        tool_specs=[],
        checkpointer=checkpointer,
    )
    events = [ev async for ev in runner.start_run("what's up", thread_id="t-simple")]
    types = [e.type for e in events]

    assert "step_start" in types
    assert "model_chunk" in types
    assert types[-1] == "run_complete"
    final = events[-1].payload["final"]
    assert final == "here is the answer"


async def test_tool_call_then_answer(checkpointer, tool_runner):
    model = ScriptedModelClient(
        [
            ai_response_with_tool_call("fs.read_file", {"path": "notes.md"}),
            ai_final_answer("file says: <contents of notes.md>"),
        ]
    )
    runner = OrchestratorRunner(
        model_client=model,
        tool_runner=tool_runner,
        tool_specs=[],
        checkpointer=checkpointer,
    )
    events = [ev async for ev in runner.start_run("read notes", thread_id="t-tool")]
    types = [e.type for e in events]

    assert "tool_call_requested" in types
    assert "tool_result" in types
    assert types[-1] == "run_complete"
    assert tool_runner.calls == [("fs.read_file", {"path": "notes.md"})]


async def test_step_cap_terminates(checkpointer, tool_runner):
    # Script tool-call responses forever; verify cap halts the loop.
    model = ScriptedModelClient(
        [ai_response_with_tool_call("fs.read_file", {"path": "x"}, call_id=f"c{i}") for i in range(50)]
    )
    runner = OrchestratorRunner(
        model_client=model,
        tool_runner=tool_runner,
        tool_specs=[],
        checkpointer=checkpointer,
    )
    # override max_steps via a smaller starting value — we set through initial state
    # (AgentState's max_steps default is 25; we'll verify the graph doesn't run forever)
    events = [ev async for ev in runner.start_run("loop", thread_id="t-cap")]
    # Without loop prevention, the scripted client would eventually exhaust.
    # With cap, we expect termination well before 50 calls.
    tool_calls = [e for e in events if e.type == "tool_call_requested"]
    assert len(tool_calls) <= 25
    assert events[-1].type == "run_complete"
