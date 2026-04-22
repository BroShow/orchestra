"""Shared fixtures: async SQLite engine, session factory, ids."""

from __future__ import annotations

import pytest_asyncio

from orchestrator.persistence import (
    Base,
    create_engine,
    make_session_factory,
)


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
