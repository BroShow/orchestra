"""API test harness.

Builds a FastAPI app backed by:
- An in-memory SQLite DB (real ORM, no mocks).
- A MemorySaver checkpointer.
- A ScriptedModelClient (queued responses per test).
- A FakeToolRunner (lambdas instead of MCP subprocesses).

Tests get an httpx AsyncClient connected via ASGITransport.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from langgraph.checkpoint.memory import MemorySaver

# Make the orchestrator's own tests importable — we reuse the scripted fakes.
_ORCH_TESTS = Path(__file__).parents[3] / "packages" / "orchestrator" / "tests"
if str(_ORCH_TESTS) not in sys.path:
    sys.path.insert(0, str(_ORCH_TESTS))

from fakes import FakeToolRunner, ScriptedModelClient  # noqa: E402

from orchestra_api.main import create_app
from orchestra_api.run_manager import RunManager
from orchestrator import OrchestratorRunner
from orchestrator.persistence import Base, create_engine, make_session_factory


@pytest_asyncio.fixture
async def engine():
    eng = create_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return make_session_factory(engine)


@pytest.fixture
def scripted_model() -> ScriptedModelClient:
    return ScriptedModelClient([])


@pytest.fixture
def tool_runner() -> FakeToolRunner:
    return FakeToolRunner(
        tools={
            "fs.read_file": lambda path: f"<contents of {path}>",
            "shell.exec": lambda command, timeout=30: {
                "stdout": "ran " + " ".join(command),
                "stderr": "",
                "returncode": 0,
            },
        },
        approval_needed={"shell.exec"},
    )


@pytest.fixture
def manager(scripted_model, tool_runner, session_factory) -> RunManager:
    checkpointer = MemorySaver()
    runner = OrchestratorRunner(
        model_client=scripted_model,
        tool_runner=tool_runner,
        tool_specs=[],
        checkpointer=checkpointer,
    )
    return RunManager(runner=runner, session_factory=session_factory)


@pytest_asyncio.fixture
async def app(manager) -> FastAPI:
    """An app with lifespan skipped — we wire the manager directly onto state."""
    app = FastAPI()
    from orchestra_api.routes import runs as runs_routes

    app.include_router(runs_routes.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    app.state.manager = manager
    return app


@pytest_asyncio.fixture
async def client(app) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
