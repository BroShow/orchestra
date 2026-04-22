"""/runs endpoints — create, list, snapshot, stream, approve, cancel."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from orchestra_api.deps import get_manager
from orchestra_api.run_manager import ConflictError, RunManager
from orchestra_api.schemas import (
    ApprovalRequest,
    ApprovalResponse,
    CreateRunRequest,
    CreateRunResponse,
    RunListItem,
    RunListResponse,
    RunSnapshot,
)
from orchestra_api.sse import sse_response

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=CreateRunResponse, status_code=201)
async def create_run(
    body: CreateRunRequest,
    manager: RunManager = Depends(get_manager),
) -> CreateRunResponse:
    thread_id = await manager.create_run(body.task)
    return CreateRunResponse(thread_id=thread_id, status="running")


@router.get("", response_model=RunListResponse)
async def list_runs(
    limit: int = 50,
    offset: int = 0,
    manager: RunManager = Depends(get_manager),
) -> RunListResponse:
    rows, total = await manager.list_runs(limit=limit, offset=offset)
    return RunListResponse(
        runs=[
            RunListItem(
                thread_id=r.id,
                task=r.task,
                status=r.status,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ],
        total=total,
    )


@router.get("/{thread_id}", response_model=RunSnapshot)
async def get_run(
    thread_id: str,
    manager: RunManager = Depends(get_manager),
) -> RunSnapshot:
    try:
        snap = await manager.snapshot(thread_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Run not found: {thread_id}")
    return RunSnapshot.model_validate(snap)


@router.get("/{thread_id}/events")
async def stream_events(
    thread_id: str,
    request: Request,
    manager: RunManager = Depends(get_manager),
):
    last_event_id_header = request.headers.get("last-event-id")
    last_event_id: int | None = None
    if last_event_id_header is not None:
        try:
            last_event_id = int(last_event_id_header)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Last-Event-ID header")

    try:
        sub_ctx = manager.subscribe(thread_id, last_event_id=last_event_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Run not found: {thread_id}")

    # We can't `async with` here and also return a StreamingResponse, because
    # the context needs to stay open while the stream runs. Instead we open
    # it manually and close on a wrapper around the iterator.
    entered = await sub_ctx.__aenter__()

    async def iterator():
        try:
            async for item in entered:
                yield item
        finally:
            await sub_ctx.__aexit__(None, None, None)

    return sse_response(iterator(), request)


@router.post("/{thread_id}/approve", response_model=ApprovalResponse)
async def approve(
    thread_id: str,
    body: ApprovalRequest,
    manager: RunManager = Depends(get_manager),
) -> ApprovalResponse:
    try:
        await manager.approve(thread_id, body.decision)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Run not found: {thread_id}")
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return ApprovalResponse(thread_id=thread_id, status="running")


@router.delete("/{thread_id}")
async def cancel_run(
    thread_id: str,
    manager: RunManager = Depends(get_manager),
):
    try:
        await manager.cancel(thread_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Run not found: {thread_id}")
    return JSONResponse({"thread_id": thread_id, "status": "cancelled"})
