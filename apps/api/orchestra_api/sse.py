"""SSE formatting + response helper.

Emits `id:`, `event:`, and `data:` fields. `id:` is the run_events.seq value
so browser EventSource / fetch-event-source clients automatically send
Last-Event-ID on reconnect.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import Request
from starlette.responses import StreamingResponse

from orchestrator import RunEvent


HEARTBEAT_INTERVAL_SECONDS = 15


def format_event(seq: int, ev: RunEvent) -> bytes:
    data = json.dumps(
        {"thread_id": ev.thread_id, "seq": seq, "payload": ev.payload},
        default=str,
    )
    return (
        f"id: {seq}\n"
        f"event: {ev.type}\n"
        f"data: {data}\n\n"
    ).encode("utf-8")


def _heartbeat() -> bytes:
    return b": keepalive\n\n"


async def _with_heartbeat(
    source: AsyncIterator[tuple[int, RunEvent]],
    request: Request,
) -> AsyncIterator[bytes]:
    """Wrap an event stream so it emits heartbeats every HEARTBEAT_INTERVAL_SECONDS
    of quiet and checks for client disconnect."""
    queue: asyncio.Queue = asyncio.Queue()

    async def pump():
        async for seq, ev in source:
            await queue.put((seq, ev))
        await queue.put(None)  # sentinel

    pump_task = asyncio.create_task(pump())
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                yield _heartbeat()
                continue
            if item is None:
                return
            seq, ev = item
            yield format_event(seq, ev)
    finally:
        pump_task.cancel()


def sse_response(
    source: AsyncIterator[tuple[int, RunEvent]],
    request: Request,
) -> StreamingResponse:
    resp = StreamingResponse(
        _with_heartbeat(source, request),
        media_type="text/event-stream",
    )
    # nginx / other buffering proxies
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp
