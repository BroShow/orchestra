# 10 — Acceptance Demo

## Goal
A scripted, repeatable demo that proves the PoC works end-to-end. If this demo passes start-to-finish, the PoC is "done" for the purposes of moving to v2 planning.

## Setup
1. Fresh machine state: stop and remove docker volumes, clear `./workspace`.
2. `make setup && docker compose up -d && make migrate && make dev`
3. Open `http://localhost:3000`.

## Demo Script

### Demo 1 — Multi-step research task (no approval)
**Input:** "Search for the latest LangGraph release notes, fetch the page, and write a 5-bullet summary to `./workspace/langgraph-summary.md`."

**Expected behavior:**
- Run starts; first event is `step_start` for step 1.
- Agent calls `web.search` → tool result streams in.
- Agent calls `web.fetch` on a result URL → cleaned text returned.
- Agent calls `fs.write_file` (or equivalent — if not implemented, agent calls `shell.exec` for `cat > file`, which triggers the approval gate; for this demo, we want the no-approval path, so add a `fs.write_file` MCP tool to the v1 set).
- Final answer: brief confirmation referencing the file path.

**Pass criteria:**
- File exists at the expected path with sensible content.
- Total steps ≤ 8.
- All events rendered correctly in UI.
- Total wall-clock time < 3 minutes on Mac Studio with `qwen2.5:14b`.

### Demo 2 — Approval gate
**Input:** "List the running processes on this machine."

**Expected behavior:**
- Agent reasons that `shell.exec` is needed.
- `approval_required` event fires; UI shows the proposed command (e.g., `["ps", "aux"]`).
- User clicks Approve.
- Run resumes, command executes, output appears in tool_result event.
- Agent provides a summary of the output.

**Pass criteria:**
- UI clearly displays the exact command before approval.
- Denying instead of approving causes the agent to gracefully end the run with an explanation.

### Demo 3 — Resume after crash
**Input:** Start Demo 1 again. After step 2 (when `web.fetch` is in flight or just completed), `kill -9` the API process.

**Expected behavior:**
- Restart the API: `make dev`.
- Reopen the run page in the UI.
- Stream reconnects. Past events replay (from `run_events` table). Run resumes from the last completed checkpoint.

**Pass criteria:**
- No duplicate tool executions (check `run_events` for `tool_result` count).
- Final output is identical or equivalent to a clean run.

### Demo 4 — Provider swap (proves the abstraction)
**Setup:** Have an OpenAI API key (or use a local vLLM server with the OpenAI-compatible endpoint to avoid spend).
**Action:** Stop services, change `MODEL_PROVIDER=openai_compat` and `OPENAI_BASE_URL` in `.env`. Restart. Run Demo 1 again.

**Pass criteria:**
- Zero code changes between runs.
- Demo 1 completes successfully.
- (If using OpenAI) the run completes faster and with fewer steps than the local model run, which is itself useful telemetry.

## Demo Recording
Record a single screencast walking through Demos 1–3. This becomes the deliverable for showing the PoC to anyone (collaborators, potential users, future-you trying to remember how it works).

## What This Demo Doesn't Prove
Be honest in any writeup that follows:
- Multi-user concurrency is untested.
- Long-running agents (>30 minutes) are untested.
- Recovery from Postgres downtime is untested.
- Tool sandbox is path-check only; not a real security boundary.
- Local model quality varies dramatically by task; the demo tasks are chosen to play to local model strengths.

These are the v2 planning inputs.
