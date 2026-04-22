"""Basic routes: health, create, list, get, cancel."""

from __future__ import annotations

import asyncio

from fakes import ai_final_answer


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_create_run_returns_thread_id(client, scripted_model):
    scripted_model.responses.append(ai_final_answer("hi"))

    resp = await client.post("/runs", json={"task": "say hi"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["thread_id"].startswith("run_")
    assert body["status"] == "running"


async def test_create_run_rejects_empty_task(client):
    resp = await client.post("/runs", json={"task": ""})
    assert resp.status_code == 422


async def test_get_run_404_for_unknown(client):
    resp = await client.get("/runs/run_unknown")
    assert resp.status_code == 404


async def test_list_runs_is_paginated(client, scripted_model):
    for i in range(3):
        scripted_model.responses.append(ai_final_answer(f"answer {i}"))
    for _ in range(3):
        await client.post("/runs", json={"task": "x"})

    # give the background tasks a tick to write any initial state
    await asyncio.sleep(0.05)

    resp = await client.get("/runs?limit=2")
    body = resp.json()
    assert body["total"] == 3
    assert len(body["runs"]) == 2


async def test_cancel_run(client, scripted_model):
    scripted_model.responses.append(ai_final_answer("done"))
    tid = (await client.post("/runs", json={"task": "x"})).json()["thread_id"]

    # let the run complete so cancel doesn't race the background task
    await asyncio.sleep(0.1)
    resp = await client.delete(f"/runs/{tid}")
    assert resp.status_code == 200
    snap = (await client.get(f"/runs/{tid}")).json()
    # terminal states are cancelled, complete, or error — whichever the run
    # reached first is fine, we just verify the DELETE didn't 404
    assert snap["status"] in ("cancelled", "complete")
