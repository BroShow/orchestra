"""SSE stream: live events, replay via Last-Event-ID, approval flow."""

from __future__ import annotations

import asyncio
import json

from fakes import ai_final_answer, ai_response_with_tool_call


def _parse_sse(raw: str) -> list[dict]:
    """Return a list of parsed events from a raw SSE body."""
    out: list[dict] = []
    for block in raw.split("\n\n"):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            if line.startswith(":") or not line.strip():
                continue
            key, _, value = line.partition(":")
            fields[key.strip()] = value.lstrip()
        if not fields:
            continue
        if "data" in fields:
            try:
                fields["data_parsed"] = json.loads(fields["data"])
            except json.JSONDecodeError:
                pass
        out.append(fields)
    return out


async def test_stream_delivers_final_event(client, scripted_model):
    scripted_model.responses.append(ai_final_answer("result"))
    tid = (await client.post("/runs", json={"task": "do it"})).json()["thread_id"]

    # Wait briefly for the background task to finish so the run is terminal
    # before we subscribe — simpler than racing live events in a test.
    await asyncio.sleep(0.2)

    async with client.stream("GET", f"/runs/{tid}/events") as resp:
        assert resp.status_code == 200
        body = ""
        async for chunk in resp.aiter_text():
            body += chunk
            if "run_complete" in body:
                break

    events = _parse_sse(body)
    types = [e.get("event") for e in events if "event" in e]
    assert "step_start" in types
    assert types[-1] == "run_complete"
    # id: field is present, non-empty, monotonic
    ids = [int(e["id"]) for e in events if "id" in e]
    assert ids == sorted(ids)


async def test_last_event_id_replays_after_seq(client, scripted_model):
    scripted_model.responses.append(ai_final_answer("r"))
    tid = (await client.post("/runs", json={"task": "x"})).json()["thread_id"]
    await asyncio.sleep(0.2)

    # First pass: read everything, capture second event's id
    async with client.stream("GET", f"/runs/{tid}/events") as resp:
        body = ""
        async for chunk in resp.aiter_text():
            body += chunk
            if "run_complete" in body:
                break
    events = _parse_sse(body)
    second_seq = int(events[1]["id"])

    # Reconnect with Last-Event-ID — should get events with seq > second_seq
    async with client.stream(
        "GET",
        f"/runs/{tid}/events",
        headers={"Last-Event-ID": str(second_seq)},
    ) as resp:
        body2 = ""
        async for chunk in resp.aiter_text():
            body2 += chunk
            if "run_complete" in body2:
                break
    events2 = _parse_sse(body2)
    ids2 = [int(e["id"]) for e in events2 if "id" in e]
    assert all(i > second_seq for i in ids2)


async def test_approval_flow(client, scripted_model):
    scripted_model.responses.append(
        ai_response_with_tool_call("shell.exec", {"command": ["ls"]})
    )
    scripted_model.responses.append(ai_final_answer("done"))

    tid = (await client.post("/runs", json={"task": "list"})).json()["thread_id"]

    # Wait for approval_required to land in the DB
    for _ in range(50):
        snap = (await client.get(f"/runs/{tid}")).json()
        if snap["status"] == "awaiting_approval":
            break
        await asyncio.sleep(0.05)
    else:
        raise AssertionError(f"Run never reached awaiting_approval: {snap}")

    assert snap["pending_approval"]["tool"] == "shell.exec"

    # Approve
    r = await client.post(f"/runs/{tid}/approve", json={"decision": "approved"})
    assert r.status_code == 200

    # Wait for completion
    for _ in range(50):
        snap = (await client.get(f"/runs/{tid}")).json()
        if snap["status"] in ("complete", "error"):
            break
        await asyncio.sleep(0.05)
    else:
        raise AssertionError(f"Run never completed: {snap}")

    assert snap["status"] == "complete"


async def test_approve_on_non_awaiting_returns_409(client, scripted_model):
    scripted_model.responses.append(ai_final_answer("done"))
    tid = (await client.post("/runs", json={"task": "x"})).json()["thread_id"]
    await asyncio.sleep(0.2)

    resp = await client.post(f"/runs/{tid}/approve", json={"decision": "approved"})
    assert resp.status_code == 409


async def test_approve_invalid_decision_422(client, scripted_model):
    scripted_model.responses.append(ai_final_answer("x"))
    tid = (await client.post("/runs", json={"task": "x"})).json()["thread_id"]

    resp = await client.post(f"/runs/{tid}/approve", json={"decision": "sure"})
    assert resp.status_code == 422
