# AI Agent Orchestration Platform — Proof of Concept

## Purpose
Build a user-facing AI agent orchestration platform that runs entirely on local infrastructure (no paid API dependencies) for the proof-of-concept phase. Users interact with a web UI; the system spawns and coordinates LLM-powered agents to complete multi-step tasks. Model backend is swappable so the same orchestration runs against local Ollama today and Claude/OpenAI later without code changes.

## Non-Goals (PoC)
- Multi-tenancy, auth/SSO, billing — single-user only
- Horizontal scaling, Kubernetes — single-machine deployment
- Production-grade durability (Temporal, etc.) — checkpointer-based recovery is sufficient
- Mobile UI — desktop browser only
- Production observability stack — basic structured logging + LangSmith local mode

## Success Criteria
A user can:
1. Open a web UI, type a multi-step task in natural language ("research X, summarize, draft an email")
2. Watch the agent's reasoning, tool calls, and intermediate outputs stream in real time
3. Approve/deny tool calls when the agent requests human-in-the-loop confirmation
4. Resume an interrupted run after a process crash without losing progress
5. Swap the underlying model from Qwen 32B to Llama 3.1 70B (or, later, Claude) via a single config value

## Architecture (one-liner per layer)
- **Frontend**: Next.js + SSE streaming, renders agent state from AG-UI-style events
- **Backend API**: FastAPI, exposes `/runs` endpoints, streams events to frontend
- **Orchestration**: LangGraph state machine, Postgres checkpointer for durability
- **Model adapter**: LiteLLM-style abstraction; OpenAI-compatible interface; pluggable providers
- **Model serving**: Ollama (local, default), with adapter slots for vLLM, OpenAI, Anthropic
- **Tools**: MCP-defined; initial set is filesystem read, web search, web fetch, shell exec (sandboxed)
- **Storage**: Postgres for state/checkpoints, Qdrant for vector memory, local filesystem for artifacts

## Repo Layout
```
/apps
  /web              # Next.js frontend
  /api              # FastAPI backend
/packages
  /orchestrator     # LangGraph graphs, agent definitions
  /model-adapter    # Provider-agnostic LLM client
  /tools            # MCP tool implementations
  /shared-types     # Pydantic + TS schemas (generated from one source)
/infra
  /docker           # docker-compose for Postgres, Qdrant, Ollama
  /migrations       # Alembic migrations
/specs              # These files
```

## Spec Index
| # | File | Owner-able by one agent? | Depends on |
|---|------|--------------------------|------------|
| 01 | tech-stack.md | N/A — reference | — |
| 02 | model-adapter.md | Yes | 01 |
| 03 | tools-mcp.md | Yes | 01 |
| 04 | orchestrator-langgraph.md | Yes | 02, 03 |
| 05 | backend-api.md | Yes | 04 |
| 06 | frontend-web.md | Yes | 05 |
| 07 | persistence.md | Yes | 01 |
| 08 | dev-environment.md | Yes | 01 |
| 09 | testing-strategy.md | Yes | all |
| 10 | acceptance-demo.md | N/A — validation | all |

## How to Use These Specs with Claude Code
Each spec file is self-contained and includes acceptance criteria. Recommended workflow:
1. Spawn one subagent per spec file (02–08 are parallelizable in pairs after dependencies).
2. The orchestrator subagent (you, the lead session) holds the architecture and reviews each spec's output against its acceptance criteria.
3. Use git worktrees so subagents don't collide on shared files (`packages/shared-types` especially).
4. Run `09-testing-strategy.md` after each spec lands to verify nothing regressed.
