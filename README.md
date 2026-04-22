# orchestra

AI agent orchestration platform — PoC. Single-user, local-first (Ollama), with a swappable model adapter so the same orchestration runs against hosted providers later via env-var change.

See [`specs/00-overview.md`](./specs/00-overview.md) for the full design.

## Stack (PoC)

- **Frontend**: Next.js 15 + Tailwind + shadcn/ui + Zustand (SSE streaming)
- **Backend API**: FastAPI + SSE
- **Orchestrator**: LangGraph state machine, Postgres checkpointer
- **Model adapter**: in-repo abstraction; providers for Ollama (real), OpenAI-compat (real), Anthropic (stub)
- **Tools**: MCP servers (filesystem, web search/fetch, shell with HITL approval)
- **Storage**: Postgres (state/checkpoints), Qdrant (vector memory; wired but unused in v1)

## Layout

```
apps/
  api/              # FastAPI backend
  web/              # Next.js frontend
packages/
  model-adapter/    # Provider-agnostic LLM client
  orchestrator/     # LangGraph graphs
  tools/            # MCP tool servers
  shared-types/     # TS types mirroring the Pydantic schemas
infra/
  docker/           # docker-compose for Postgres + Qdrant
  migrations/       # Alembic
specs/              # 00–10: the source of truth for what to build
```

## Setup

Prerequisites: Python 3.11+, Node 20+, `uv`, `pnpm`, Docker, Ollama (installed natively, not containerized — GPU access).

```sh
make setup         # uv sync + pnpm install + copy .env
make infra-up      # postgres + qdrant via docker compose
make migrate       # alembic upgrade head (once persistence spec lands)
make dev           # prints instructions for starting api + web
```

Pull the default Ollama models:

```sh
ollama pull llama3.2:3b
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
# qwen2.5:32b only if you have 64GB+ RAM
```

## Status

Scaffolding is in place. Implementation against the specs is in progress — see the spec index in [`specs/00-overview.md`](./specs/00-overview.md).
