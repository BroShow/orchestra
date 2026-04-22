"""Approval gate: interrupt on approval-required tool, resume on decision."""

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
def tool_runner() -> FakeToolRunner:
    return FakeToolRunner(
        tools={
            "shell.exec": lambda command, timeout=30: {
                "stdout": "PID 1 init\n",
                "stderr": "",
                "returncode": 0,
            }
        },
        approval_needed={"shell.exec"},
    )


async def test_approve_runs_tool(tool_runner):
    checkpointer = MemorySaver()
    model = ScriptedModelClient(
        [
            ai_response_with_tool_call("shell.exec", {"command": ["ps", "aux"]}),
            ai_final_answer("ran the command"),
        ]
    )
    runner = OrchestratorRunner(
        model_client=model,
        tool_runner=tool_runner,
        tool_specs=[],
        checkpointer=checkpointer,
    )

    events = [ev async for ev in runner.start_run("list procs", thread_id="t-ap")]
    types = [e.type for e in events]
    assert types[-1] == "approval_required"
    assert events[-1].payload["tool"] == "shell.exec"
    assert events[-1].payload["arguments"] == {"command": ["ps", "aux"]}

    # Tool must not have run yet
    assert tool_runner.calls == []

    # Resume with approval
    resume_events = [
        ev async for ev in runner.resume_run("t-ap", approval="approved")
    ]
    types = [e.type for e in resume_events]
    assert "tool_result" in types
    assert types[-1] == "run_complete"
    assert tool_runner.calls == [("shell.exec", {"command": ["ps", "aux"]})]


async def test_deny_skips_tool_and_lets_agent_continue(tool_runner):
    checkpointer = MemorySaver()
    model = ScriptedModelClient(
        [
            ai_response_with_tool_call("shell.exec", {"command": ["rm", "-rf", "/"]}),
            ai_final_answer("understood, won't do that"),
        ]
    )
    runner = OrchestratorRunner(
        model_client=model,
        tool_runner=tool_runner,
        tool_specs=[],
        checkpointer=checkpointer,
    )

    [_ async for _ in runner.start_run("destroy everything", thread_id="t-deny")]

    resume_events = [
        ev async for ev in runner.resume_run("t-deny", approval="denied")
    ]
    types = [e.type for e in resume_events]
    # A tool_result event still fires — but with denied=True and no actual execution
    tool_results = [e for e in resume_events if e.type == "tool_result"]
    assert len(tool_results) == 1
    assert tool_results[0].payload["denied"] is True
    assert "denied" in tool_results[0].payload["content"].lower()
    assert types[-1] == "run_complete"
    # Real tool was never invoked
    assert tool_runner.calls == []


async def test_invalid_approval_value_rejected(tool_runner):
    checkpointer = MemorySaver()
    model = ScriptedModelClient(
        [ai_response_with_tool_call("shell.exec", {"command": ["ls"]})]
    )
    runner = OrchestratorRunner(
        model_client=model,
        tool_runner=tool_runner,
        tool_specs=[],
        checkpointer=checkpointer,
    )
    [_ async for _ in runner.start_run("list", thread_id="t-bad")]
    with pytest.raises(ValueError, match="approval"):
        [_ async for _ in runner.resume_run("t-bad", approval="maybe")]
