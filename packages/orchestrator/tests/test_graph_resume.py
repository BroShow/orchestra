"""Checkpointer resume: kill-and-restart replays from the last checkpoint.

MemorySaver obviously doesn't survive a real process kill, but we can
simulate it: build two runner instances sharing the same checkpointer,
run partially through one, then finish through the other.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from orchestrator import OrchestratorRunner
from tests.fakes import (
    FakeToolRunner,
    ScriptedModelClient,
    ai_final_answer,
    ai_response_with_tool_call,
)


async def test_resume_after_approval_interrupt():
    checkpointer = MemorySaver()
    tool_runner = FakeToolRunner(
        tools={"shell.exec": lambda command, timeout=30: {"stdout": "ok", "stderr": "", "returncode": 0}},
        approval_needed={"shell.exec"},
    )

    # Runner 1 starts and pauses at approval
    model1 = ScriptedModelClient(
        [
            ai_response_with_tool_call("shell.exec", {"command": ["echo", "hi"]}),
            ai_final_answer("done"),
        ]
    )
    runner1 = OrchestratorRunner(
        model_client=model1,
        tool_runner=tool_runner,
        tool_specs=[],
        checkpointer=checkpointer,
    )
    events1 = [ev async for ev in runner1.start_run("echo", thread_id="t-rez")]
    assert events1[-1].type == "approval_required"

    # Runner 2 — new process, same checkpointer — picks up and finishes
    model2 = ScriptedModelClient([ai_final_answer("done")])
    runner2 = OrchestratorRunner(
        model_client=model2,
        tool_runner=tool_runner,
        tool_specs=[],
        checkpointer=checkpointer,
    )
    events2 = [ev async for ev in runner2.resume_run("t-rez", approval="approved")]
    types = [e.type for e in events2]
    assert "tool_result" in types
    assert types[-1] == "run_complete"


async def test_get_run_state_returns_snapshot():
    checkpointer = MemorySaver()
    tool_runner = FakeToolRunner(tools={}, approval_needed=set())
    model = ScriptedModelClient([ai_final_answer("hello")])
    runner = OrchestratorRunner(
        model_client=model,
        tool_runner=tool_runner,
        tool_specs=[],
        checkpointer=checkpointer,
    )

    [_ async for _ in runner.start_run("hi", thread_id="t-snap")]
    state = await runner.get_run_state("t-snap")
    assert state.step_count >= 1
    assert len(state.messages) >= 2  # user + assistant
