"""FastAPI dependency wiring.

Construction order:
  model client → tool registry (async) → checkpointer → session factory
  → OrchestratorRunner → RunManager.

Heavy objects (engine, registry, runner, manager) live on app.state and are
created once at startup. Routes pull them via Depends so tests can override
them cleanly with app.dependency_overrides.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from model_adapter import ModelSettings, ToolSpec, get_client
from orchestra_api.config import ApiSettings
from orchestra_api.run_manager import RunManager
from orchestrator import OrchestratorRunner
from orchestrator.persistence import (
    Base,
    create_engine,
    make_session_factory,
)
from tools import ToolRegistry
from tools.approval import requires_approval


class _AdapterToolRunner:
    """Bridges the ToolRunner protocol (what the orchestrator expects) to the
    MCP-backed ToolRegistry."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def call(self, qualified_name: str, arguments: dict) -> str:
        return await self._registry.call(qualified_name, arguments)

    def requires_approval(self, qualified_name: str) -> bool:
        return requires_approval(qualified_name)


def _tool_specs_from_registry(reg: ToolRegistry) -> list[ToolSpec]:
    return [
        ToolSpec(
            name=t.qualified_name,
            description=t.description,
            parameters=t.parameters,
        )
        for t in reg.list_specs()
    ]


@asynccontextmanager
async def lifespan(app: FastAPI):
    api_settings = ApiSettings()
    model_settings = ModelSettings()

    # DB engine + session factory
    engine = create_engine(api_settings.database_url)
    # For SQLite dev, create tables on startup if they're not there.
    # (Alembic is the source of truth in Postgres.)
    if api_settings.database_url.startswith(("sqlite", "sqlite+aiosqlite")):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    session_factory = make_session_factory(engine)

    # Model client
    model_client = get_client(model_settings)

    # Tool registry — open MCP subprocesses for the configured servers
    registry = await ToolRegistry.from_config(api_settings.mcp_config)
    tool_runner = _AdapterToolRunner(registry)
    tool_specs = _tool_specs_from_registry(registry)

    # Checkpointer
    checkpointer = _build_checkpointer(api_settings)

    runner = OrchestratorRunner(
        model_client=model_client,
        tool_runner=tool_runner,
        tool_specs=tool_specs,
        checkpointer=checkpointer,
    )
    manager = RunManager(runner=runner, session_factory=session_factory)

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.registry = registry
    app.state.manager = manager

    try:
        yield
    finally:
        await registry.aclose()
        await engine.dispose()


def _build_checkpointer(settings: ApiSettings) -> BaseCheckpointSaver:
    if settings.checkpointer == "memory":
        return MemorySaver()
    if settings.checkpointer == "postgres":
        # Only imported when requested, so MemorySaver dev path doesn't require
        # a running Postgres. Setup of the checkpointer's own tables happens
        # on first use via PostgresSaver.setup() — see migrations/README.
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        # Translate DATABASE_URL asyncpg scheme -> psycopg scheme if needed
        # (PostgresSaver uses psycopg; our ORM uses asyncpg).
        pg_url = settings.database_url.replace("+asyncpg", "")
        return AsyncPostgresSaver.from_conn_string(pg_url).__enter__()
    raise ValueError(f"Unknown checkpointer: {settings.checkpointer!r}")


def get_manager(request: Request) -> RunManager:
    return request.app.state.manager
