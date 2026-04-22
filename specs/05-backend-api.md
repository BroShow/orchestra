# 05 — Backend API (FastAPI)

## Goal
A thin HTTP layer over the orchestrator. Exposes REST endpoints for run management and an SSE endpoint for streaming run events to the frontend.

## Location
`apps/api/`

## Endpoints

### `POST /runs`
Create and start a new run.
```json
// Request
{ "task": "Find the latest LangGraph release notes and summarize them" }

// Response (201)
{ "thread_id": "run_01HXY...", "status": "running" }
```

### `GET /runs/{thread_id}/events` (SSE)
Stream events for a run. Long-lived connection. Each SSE message is a `RunEvent` JSON-encoded.
```
event: step_start
data: {"thread_id":"run_01...","payload":{"step":1}}

event: model_chunk
data: {"thread_id":"run_01...","payload":{"text":"I'll start by"}}

event: approval_required
data: {"thread_id":"run_01...","payload":{"tool":"shell.exec","args":{...}}}
```

Reconnection: if a client reconnects with `Last-Event-ID` header, replay events from that ID onward (events stored in Postgres alongside checkpoints).

### `POST /runs/{thread_id}/approve`
Resolve a pending approval.
```json
// Request
{ "decision": "approved" }   // or "denied"

// Response (200)
{ "thread_id": "...", "status": "running" }
```

### `GET /runs/{thread_id}`
Fetch current state (snapshot, no streaming).
```json
{
  "thread_id": "...",
  "status": "running" | "awaiting_approval" | "complete" | "error",
  "messages": [...],
  "step_count": 7
}
```

### `GET /runs`
List recent runs (paginated).

### `DELETE /runs/{thread_id}`
Cancel a running run. Sets a cancellation flag; the agent loop checks before each step.

## Project Structure
```
apps/api/
  api/
    __init__.py
    main.py              # FastAPI app
    routes/
      runs.py
    deps.py              # DI: model client, orchestrator, db session
    sse.py               # SSE response helper
    schemas.py           # Request/response Pydantic models
  pyproject.toml
  Dockerfile
```

## Dependency Injection
Wire the orchestrator, model client, and DB session via FastAPI `Depends`. Don't use globals. This makes the API testable with a fake orchestrator.

## SSE Implementation Notes
- Use `StreamingResponse` with `media_type="text/event-stream"`.
- Send a heartbeat comment (`:keepalive\n\n`) every 15s to prevent proxy timeouts.
- Set `X-Accel-Buffering: no` header for nginx compatibility (defensive — we're not behind nginx in PoC but documenting the pattern saves pain later).
- Client disconnects: detect via `request.is_disconnected()` in the generator and break cleanly.

## Error Handling
- Validation errors → 422 with detail (FastAPI default is fine).
- Missing thread → 404.
- Orchestrator/model errors → 500 with a sanitized message; full traceback in structured logs (never to client).
- Approval on a run not awaiting approval → 409 Conflict.

## Logging
Structured JSON via `structlog`. Every request gets a correlation ID; every orchestrator event includes the `thread_id` and correlation ID.

## CORS
Allow `http://localhost:3000` only (the Next.js dev server). Configurable via env.

## Acceptance Criteria
- [ ] All endpoints implemented and documented in the auto-generated `/docs` (FastAPI OpenAPI).
- [ ] SSE stream works end-to-end with `curl -N` and shows events flowing.
- [ ] Approval flow: start a run that triggers shell.exec, observe `approval_required` event, POST `/approve`, observe execution continues.
- [ ] Reconnect with `Last-Event-ID` replays missing events.
- [ ] Tests cover all endpoints with a fake orchestrator (httpx + ASGI transport).
- [ ] No business logic in routes; routes only validate input and call orchestrator methods.

## Anti-Goals (v1)
- No WebSockets. SSE is sufficient and simpler.
- No auth. PoC is single-user on localhost.
- No rate limiting.
