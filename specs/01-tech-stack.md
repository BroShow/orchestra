# 01 — Tech Stack & Versions

## Languages & Runtimes
- **Python 3.11+** (backend, orchestrator, tools)
- **Node.js 20 LTS** (frontend)
- **TypeScript 5.x** (frontend)

## Backend Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | ^0.115 | HTTP API |
| `uvicorn[standard]` | ^0.32 | ASGI server |
| `langgraph` | ^1.0 | Agent orchestration |
| `langchain-core` | ^0.3 | Message types, runnable interface |
| `langchain-ollama` | latest | Ollama adapter (used inside model-adapter) |
| `langchain-openai` | latest | OpenAI-compatible adapter |
| `pydantic` | ^2.9 | Schema validation |
| `pydantic-settings` | ^2.6 | Config from env |
| `sqlalchemy[asyncio]` | ^2.0 | DB ORM |
| `asyncpg` | latest | Postgres async driver |
| `alembic` | latest | Migrations |
| `qdrant-client` | latest | Vector store |
| `mcp` | latest | Model Context Protocol SDK |
| `httpx` | latest | HTTP client |
| `structlog` | latest | Structured logging |
| `pytest`, `pytest-asyncio`, `pytest-mock` | latest | Tests |

## Frontend Dependencies
| Package | Purpose |
|---------|---------|
| `next` (15+, app router) | Framework |
| `react`, `react-dom` (19+) | UI |
| `tailwindcss` (4+) | Styling |
| `shadcn/ui` | Component primitives |
| `lucide-react` | Icons |
| `zod` | Runtime validation |
| `@microsoft/fetch-event-source` | SSE client (handles reconnection better than native EventSource) |
| `zustand` | Client state |

## Infrastructure
- **Postgres 16** (state, checkpoints)
- **Qdrant** (vector memory) — can defer to v2 if not needed for PoC scope
- **Ollama** (model serving) — host install, not containerized (better Mac GPU access)

## Models (Local PoC Defaults)
- **Router/classifier**: `llama3.2:3b`
- **General reasoning**: `qwen2.5:14b`
- **Heavy reasoning**: `qwen2.5:32b` (or `llama3.1:70b` if 64GB+ RAM)
- **Embeddings**: `nomic-embed-text`

Tool-calling reliability matters more than parameter count. Qwen 2.5 series is the current best-in-class for local agent work; do not substitute smaller general-purpose models.

## What We Are NOT Using (and why)
- **CrewAI / AutoGen**: Prototype-grade orchestration, weak production primitives.
- **Temporal**: Right answer at scale, premature for PoC.
- **LangChain agent abstractions** (the high-level `AgentExecutor` etc.): Use LangGraph directly. The high-level wrappers obscure control flow.
- **Vercel AI SDK**: Fine for the JS frontend if helpful for streaming UI hooks, but the orchestration lives in Python.
- **LiteLLM**: Excluded due to the March 2026 PyPI supply-chain compromise (credential-stealing payload shipped in versions 1.82.7/1.82.8) and the follow-on April 2026 CVE cluster (OIDC auth bypass, privesc, SSRF, unsalted password hashes). The model adapter (spec 02) calls providers directly — `langchain-ollama` for Ollama, `httpx` against OpenAI-compatible `/v1/chat/completions` for everything else. Do not re-add LiteLLM as a "fallback router"; build what we need inside `packages/model-adapter/` instead.

## Configuration Source of Truth
All runtime config via environment variables, loaded by `pydantic-settings`. A single `.env.example` at repo root documents every variable. No config in code.
