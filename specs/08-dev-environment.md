# 08 — Dev Environment

## Goal
A developer (you) can clone the repo and have everything running locally with two commands. No manual config beyond `.env`.

## Prerequisites (documented in README)
- macOS or Linux (Mac Studio for the target deploy)
- Docker Desktop or OrbStack
- Python 3.11+ (use `uv` for venv management)
- Node.js 20 LTS (use `pnpm` for package management)
- Ollama installed natively (NOT in Docker — needs GPU access)

## Repo Bootstrap
```bash
# One-time
./scripts/bootstrap.sh   # installs uv, pnpm if missing; pulls Ollama models; creates .env from .env.example

# Daily
docker compose up -d     # Postgres + Qdrant
pnpm dev                 # starts both api and web concurrently via turbo or similar
```

## docker-compose.yml (infra/docker/)
```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: orchestrator
      POSTGRES_PASSWORD: orchestrator
      POSTGRES_DB: orchestrator
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes: ["qdrant_data:/qdrant/storage"]

volumes:
  pgdata:
  qdrant_data:
```

## Ollama Models to Pre-pull
The bootstrap script runs:
```bash
ollama pull llama3.2:3b
ollama pull qwen2.5:14b
ollama pull qwen2.5:32b   # only if RAM check passes
ollama pull nomic-embed-text
```

## Monorepo Tooling
- **Turborepo** for orchestrating `pnpm dev`, `pnpm build`, `pnpm test` across `apps/*` and `packages/*` (frontend side).
- **uv workspaces** for the Python side (`packages/model-adapter`, `packages/orchestrator`, `packages/tools`, `apps/api`).
- Single root `Makefile` with common commands so people don't have to remember tool-specific incantations:
  ```
  make setup       # bootstrap
  make dev         # start everything
  make test        # run all tests
  make lint        # ruff + eslint
  make typecheck   # mypy + tsc
  make migrate     # alembic upgrade head
  ```

## .env.example (root)
```
# Database
DATABASE_URL=postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator

# Qdrant
QDRANT_URL=http://localhost:6333

# Model provider
MODEL_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_MODEL=qwen2.5:14b
ROUTER_MODEL=llama3.2:3b
HEAVY_MODEL=qwen2.5:32b

# Workspace
WORKSPACE_DIR=./workspace

# API
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000

# Frontend
NEXT_PUBLIC_API_BASE=http://localhost:8000

# Logging
LOG_LEVEL=info
LOG_FORMAT=json
```

## Pre-commit Hooks
Use `pre-commit` framework:
- Python: `ruff` (lint + format), `mypy` (typecheck on staged packages)
- TypeScript: `eslint`, `prettier`
- General: trailing whitespace, EOF newline, large file check

## CI (defer, document only)
GitHub Actions workflow stub in `.github/workflows/ci.yml`:
- Run `make lint`, `make typecheck`, `make test` on PR
- Don't run integration tests requiring Ollama in CI; mark them with `@pytest.mark.integration` and skip in CI

## Acceptance Criteria
- [ ] Fresh clone → `make setup && make dev` produces a working app within 5 minutes (excluding model download time).
- [ ] `make test` runs full unit-test suite without external services (Postgres can be required; Ollama must be mocked).
- [ ] `.env.example` documents every variable any service reads.
- [ ] README has a "Running locally" section that walks through the two-command flow.
- [ ] Pre-commit hooks block commits with lint/type errors.

## Anti-Goals (v1)
- No production Dockerfiles for the apps. Run them with `uv run` and `pnpm dev` locally.
- No CI/CD beyond the lint/test workflow stub.
- No remote dev environments (Codespaces, Devcontainers).
