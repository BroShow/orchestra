# 09 — Testing Strategy

## Goal
Each spec ships with tests. The test pyramid is heavy on unit tests with mocked LLM responses, with a handful of integration tests against real Ollama gated behind a marker.

## Pyramid

### Unit (the bulk)
- Pure logic. No network, no DB, no LLM.
- Use `pytest-mock` for Python, `vitest` for TypeScript.
- Mock `ModelClient` with scripted responses for orchestrator graph tests. This lets you assert exact graph behavior under controlled inputs.

### Component / Integration (DB, MCP)
- Spin up a real Postgres via testcontainers (`testcontainers-python`) for ORM and orchestrator persistence tests.
- Spin up real MCP tool servers (subprocess) for tool-discovery tests.
- LLM still mocked.

### End-to-End (real Ollama, gated)
- Marker: `@pytest.mark.integration`. Skipped by default; run with `pytest -m integration`.
- Calls a real local Ollama with a small model (`llama3.2:3b`) for fast feedback.
- Covers: a complete run that uses 2–3 tools, an approval flow, a resume-after-restart flow.

### Frontend E2E (defer)
- Note in spec: Playwright tests are v2. For PoC, manual demo against real backend is sufficient.

## Patterns

### Scripted ModelClient for graph tests
```python
class ScriptedModelClient(ModelClient):
    def __init__(self, responses: list[ModelResponse]):
        self.responses = list(responses)
        self.calls: list[list[ModelMessage]] = []

    async def complete(self, messages, **kwargs):
        self.calls.append(messages)
        if not self.responses:
            raise AssertionError("Ran out of scripted responses")
        return self.responses.pop(0)
```

Use this to drive the orchestrator through specific decision paths without flakiness.

### MCP tool tests
Each MCP tool gets:
1. Direct unit tests (call the function, assert result)
2. A round-trip test: start the MCP server in a subprocess, connect a client, invoke the tool, validate the response.

### Approval flow test
```python
async def test_approval_flow(orchestrator, scripted_model):
    scripted_model.queue([
        ai_message_with_tool_call("shell.exec", {"command": ["ls"]}),
        ai_message("Done."),
    ])

    events = []
    async for ev in orchestrator.start_run("List files", thread_id="t1"):
        events.append(ev)
        if ev.type == "approval_required":
            break

    assert events[-1].type == "approval_required"

    # Resume with approval
    async for ev in orchestrator.resume_run("t1", approval="approved"):
        events.append(ev)

    assert events[-1].type == "run_complete"
```

## Coverage Targets (PoC)
- **Unit tests**: 80%+ on `packages/*` business logic. Don't chase 100%; coverage on glue code and main.py is wasted effort.
- **Integration tests**: Cover the critical paths in spec 10 (acceptance demo).
- **Don't** measure coverage on the frontend in v1.

## Test Data
- Fixtures in `tests/fixtures/` for sample messages, tool specs, etc.
- No real production data. Workspace dir for tool tests is a `tmp_path` fixture.

## Performance Tests (defer)
None in PoC. Note in spec that load-testing the SSE endpoint is a v2 task before adding multi-user support.

## Acceptance Criteria
- [ ] `make test` runs all non-integration tests in <30s.
- [ ] `pytest -m integration` runs against local Ollama and passes.
- [ ] Every spec (02–07) has a test file or directory with at least the happy-path test it claims in its own acceptance criteria.
- [ ] CI configuration in `.github/workflows/ci.yml` runs unit tests; integration tests are skipped.
- [ ] Test failures produce useful output (no bare `assert x`; use `pytest`'s rich assertion or messages).

## Anti-Goals
- No mutation testing, no property-based testing in PoC.
- No Selenium/Playwright in PoC.
- No load testing in PoC.
