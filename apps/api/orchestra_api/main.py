"""FastAPI app entry point. Routes land in spec 05."""
from fastapi import FastAPI

app = FastAPI(title="orchestra-api", version="0.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
