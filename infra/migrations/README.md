# Migrations

This directory holds Alembic migrations for the `runs` and `run_events` tables.

## Running

```sh
# From repo root
uv run alembic -c infra/migrations/alembic.ini upgrade head
```

`DATABASE_URL` must be set (see `.env.example`).

## LangGraph checkpointer tables

The LangGraph Postgres checkpointer (`PostgresSaver`) creates its own tables via
`PostgresSaver.setup()` on first use. They live in the same database as the
orchestra tables and are **not managed by Alembic**.

If you ever need to reset the checkpointer's tables, drop them with:
```sql
DROP TABLE IF EXISTS checkpoints, checkpoint_writes, checkpoint_migrations CASCADE;
```
and rerun the orchestrator once — it'll call `setup()` again on startup.

## Adding a new migration

```sh
uv run alembic -c infra/migrations/alembic.ini revision --autogenerate -m "describe change"
```

Review the generated file before applying. Autogen misses check constraints and
enum changes.
