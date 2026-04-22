"""Async engine + session factory."""

from __future__ import annotations

from typing import Callable

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


SessionFactory = Callable[[], AsyncSession]


def create_engine(url: str, echo: bool = False) -> AsyncEngine:
    """Create an async engine. Pool size 10 matches the spec's PoC target."""
    kwargs: dict = {"echo": echo}
    is_sqlite = url.startswith(("sqlite", "sqlite+aiosqlite"))
    if not is_sqlite:
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 5
    engine = create_async_engine(url, **kwargs)

    if is_sqlite:
        # SQLite needs PRAGMA foreign_keys=ON per connection to enforce
        # cascades and FK constraints. Postgres does this by default.
        @event.listens_for(engine.sync_engine, "connect")
        def _enable_fk(dbapi_conn, _conn_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
