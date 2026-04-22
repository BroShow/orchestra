"""MemoryStore — Qdrant-backed vector memory.

The orchestrator does NOT call this in v1 (spec 07 anti-goal). It exists
standalone with tests so the abstraction is proven and the v2 work of
adding a memory-retrieval node is purely additive.

Embedding is injected, not built-in: the store takes vectors and leaves
embedding-provider choice to the caller. That keeps the dependency surface
small and lets us later embed via Ollama (`nomic-embed-text`) or a hosted
provider without rewriting the store.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal, Protocol


class _QdrantLike(Protocol):
    """Minimal Qdrant-client surface we rely on. Makes mocking trivial."""

    def upsert(self, collection_name: str, points: list[Any]) -> Any: ...
    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        query_filter: Any = None,
        limit: int = 5,
    ) -> list[Any]: ...
    def recreate_collection(self, collection_name: str, vectors_config: Any) -> Any: ...


@dataclass
class MemoryRecord:
    id: str
    run_id: str
    kind: Literal["task", "observation", "summary"]
    text: str
    score: float | None = None


class MemoryStore:
    """Tiny wrapper over qdrant-client. The caller supplies embeddings."""

    def __init__(
        self,
        client: _QdrantLike,
        collection: str = "agent_memory",
        vector_size: int = 768,  # nomic-embed-text
    ) -> None:
        self.client = client
        self.collection = collection
        self.vector_size = vector_size

    def ensure_collection(self) -> None:
        """Create the collection if missing. Idempotent."""
        # Late import so unit tests can avoid pulling qdrant-client if they mock
        # the client interface via _QdrantLike.
        from qdrant_client.models import Distance, VectorParams

        self.client.recreate_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
        )

    def add(
        self,
        run_id: str,
        kind: Literal["task", "observation", "summary"],
        text: str,
        vector: list[float],
    ) -> str:
        from qdrant_client.models import PointStruct

        point_id = str(uuid.uuid4())
        self.client.upsert(
            collection_name=self.collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"run_id": run_id, "kind": kind, "text": text},
                )
            ],
        )
        return point_id

    def search(
        self,
        query_vector: list[float],
        run_id: str | None = None,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        flt = None
        if run_id is not None:
            flt = Filter(
                must=[FieldCondition(key="run_id", match=MatchValue(value=run_id))]
            )
        hits = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            query_filter=flt,
            limit=limit,
        )
        return [
            MemoryRecord(
                id=str(h.id),
                run_id=h.payload.get("run_id", ""),
                kind=h.payload.get("kind", "observation"),
                text=h.payload.get("text", ""),
                score=getattr(h, "score", None),
            )
            for h in hits
        ]
