"""FastAPI app entrypoint. Run with:
    uv run uvicorn orchestra_api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from orchestra_api.config import ApiSettings
from orchestra_api.deps import lifespan
from orchestra_api.routes import runs

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("orchestra_api")


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    s = settings or ApiSettings()
    app = FastAPI(title="orchestra-api", version="0.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlation_id(request: Request, call_next):
        cid = request.headers.get("x-correlation-id") or uuid.uuid4().hex[:12]
        request.state.correlation_id = cid
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(runs.router)
    return app


app = create_app()
