# 07 — Persistence

## Goal
Define the data model, migrations, and storage choices. Two stores: Postgres for transactional state and event log, Qdrant for vector memory (optional in PoC; wire it up but don't require it for the demo).

## Location
`infra/migrations/` (Alembic) and `packages/orchestrator/orchestrator/persistence/` for ORM models.

## Postgres Schema

### `runs`
| Column | Type | Notes |
|--------|------|-------|
| `id` | `text` PK | ULID, e.g. `run_01HXY...` |
| `task` | `text` | Original user task |
| `status` | `text` | `running` \| `awaiting_approval` \| `complete` \| `error` \| `cancelled` |
| `created_at` | `timestamptz` | |
| `updated_at` | `timestamptz` | |
| `completed_at` | `timestamptz` nullable | |
| `error_message` | `text` nullable | |

### `run_events`
Append-only event log. Sourced for both UI replay (Last-Event-ID) and audit.
| Column | Type | Notes |
|--------|------|-------|
| `id` | `bigserial` PK | |
| `run_id` | `text` FK → runs.id | indexed |
| `seq` | `int` | per-run sequence; `(run_id, seq)` unique |
| `event_type` | `text` | matches `RunEvent.type` |
| `payload` | `jsonb` | |
| `created_at` | `timestamptz` | |

### LangGraph checkpointer tables
Created automatically by `PostgresSaver.setup()`. Don't manage these manually. They live in the same database.

## Qdrant Schema (deferred — wire interface, defer use)
Single collection `agent_memory` with payload fields:
- `run_id` (filter)
- `kind` (`task` | `observation` | `summary`)
- `text` (raw text)
- `created_at`

Embedding dimension matches the embed model (`nomic-embed-text` = 768).

The orchestrator does NOT read from Qdrant in v1. The `MemoryStore` class is implemented and tested standalone, but the agent loop ignores it. v2 ticket: add a memory-retrieval node before the agent node.

## ORM
SQLAlchemy 2.x async with declarative models. One model per table above. Use `pydantic-settings` to load `DATABASE_URL`.

## Migrations
Alembic, autogenerate from models. Initial migration creates `runs` and `run_events`. The LangGraph checkpointer tables are created via its own `setup()` method on first run; document this in `infra/migrations/README.md`.

## Connection Management
- Single async engine, configured pool size = 10 for PoC.
- Sessions managed via FastAPI `Depends(get_db_session)` in the API layer.
- Orchestrator gets its own session per node execution (LangGraph nodes are short-lived; no long-held transactions).

## Backup / Recovery (PoC scope)
- Document `pg_dump` command in `infra/README.md`. Don't automate.
- Workspace dir (`./workspace`) is user-managed; no automated backup.

## Acceptance Criteria
- [ ] Migrations run cleanly from empty Postgres.
- [ ] LangGraph checkpointer tables coexist with our tables in the same DB.
- [ ] Event log: writing 10k events and replaying them by `(run_id, seq > N)` is fast (<100ms).
- [ ] `DELETE /runs/{id}` cascades to `run_events`.
- [ ] Qdrant: `MemoryStore.add()` and `MemoryStore.search()` work in isolation; tests mock the Qdrant client.
- [ ] All ORM models have type-checked schemas; mypy passes on `packages/orchestrator`.

## Anti-Goals
- No multi-database setup. One Postgres instance holds everything.
- No event-sourcing rebuild. The event log is for replay/audit; the source of truth for agent state is the LangGraph checkpoint.
