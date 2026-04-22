# Acceptance Demo Walkthrough

This is the concrete, runnable form of `specs/10-acceptance-demo.md`. If all four demos pass, the PoC is done.

## Prereqs

1. Ollama installed and these models pulled:
   ```sh
   ollama pull llama3.2:3b
   ollama pull qwen2.5:14b
   ```
2. Docker Desktop / OrbStack running.
3. `.env` in repo root (copy from `.env.example` and leave defaults).

## Boot everything

```sh
make setup            # uv sync --all-packages + pnpm install + .env bootstrap
make infra-up         # Postgres + Qdrant
make migrate          # alembic upgrade head

# Terminal 1 — API
uv run uvicorn orchestra_api.main:app --reload --port 8000

# Terminal 2 — web
pnpm dev:web
```

Open <http://localhost:3000>.

## Demo 1 — multi-step research task (no approval gate)

**Task:**
```
Search for the latest LangGraph release notes, fetch the page, and write a
5-bullet summary to ./workspace/langgraph-summary.md.
```

**Expected:** agent calls `web.search` → `web.fetch` → `fs.write_file`, ends with a confirmation referencing the file.

**Pass:** file exists with sensible content, total steps ≤ 8, UI renders every event type.

## Demo 2 — approval gate

**Task:**
```
List the running processes on this machine.
```

**Expected:** agent proposes `shell.exec(["ps", "aux"])`, approval card appears in the timeline.

**Pass:**
- Approve → the run resumes, tool_result streams in, agent summarizes the output.
- Run again and deny → agent gets a refusal tool message and gracefully ends.

## Demo 3 — resume after crash

Requires `CHECKPOINTER=postgres` in `.env` (MemorySaver is intentionally volatile — it's fine for dev, not for this demo).

1. Start demo 1 again.
2. After step 2 completes, `kill -9` the uvicorn process.
3. Restart: `uv run uvicorn orchestra_api.main:app --reload --port 8000`.
4. Reopen <http://localhost:3000/runs/{id}> — the timeline replays past events (from `run_events`) and the orchestrator resumes from the last checkpoint.

**Pass:** no duplicate tool executions (check `run_events` for `tool_result` count), final output equivalent to a clean run.

## Demo 4 — provider swap

Proves the model-adapter abstraction: zero code changes to switch backends.

1. Stop the API.
2. Edit `.env`:
   ```
   MODEL_PROVIDER=openai_compat
   OPENAI_BASE_URL=https://api.openai.com/v1   # or a local vLLM endpoint
   OPENAI_API_KEY=sk-...
   DEFAULT_MODEL=gpt-4o-mini
   ```
3. Restart API. Run demo 1 again.

**Pass:** same demo completes. No source changes between runs.

## What this demo does NOT prove

Be honest in any writeup:
- Multi-user concurrency — untested.
- Long-running agents (> 30 min) — untested.
- Postgres downtime recovery — untested.
- Tool sandbox is path-check only; not a real security boundary.
- Local model quality varies wildly by task — the demo tasks above play to qwen2.5's strengths.

These are v2 planning inputs.
