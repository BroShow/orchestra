"""MemoryStore against a mocked Qdrant client — proves the abstraction
without needing a live Qdrant (spec 07 acceptance criterion)."""

from __future__ import annotations

from typing import Any

from orchestrator.persistence import MemoryStore


class FakeHit:
    def __init__(self, id: str, payload: dict, score: float) -> None:
        self.id = id
        self.payload = payload
        self.score = score


class FakeQdrant:
    def __init__(self) -> None:
        self.upserts: list[dict[str, Any]] = []
        self.search_calls: list[dict[str, Any]] = []
        self.next_hits: list[FakeHit] = []
        self.recreated: bool = False

    def upsert(self, collection_name, points):
        for p in points:
            self.upserts.append(
                {
                    "collection": collection_name,
                    "id": p.id,
                    "vector": p.vector,
                    "payload": p.payload,
                }
            )

    def search(self, collection_name, query_vector, query_filter=None, limit=5):
        self.search_calls.append(
            {
                "collection": collection_name,
                "vector": query_vector,
                "filter": query_filter,
                "limit": limit,
            }
        )
        return self.next_hits[:limit]

    def recreate_collection(self, collection_name, vectors_config):
        self.recreated = True


def test_ensure_collection():
    store = MemoryStore(FakeQdrant())
    store.ensure_collection()
    assert store.client.recreated is True


def test_add_stores_payload_fields():
    fake = FakeQdrant()
    store = MemoryStore(fake)
    point_id = store.add(
        run_id="run_001",
        kind="observation",
        text="user said hi",
        vector=[0.1] * 768,
    )
    assert point_id
    assert len(fake.upserts) == 1
    u = fake.upserts[0]
    assert u["payload"] == {"run_id": "run_001", "kind": "observation", "text": "user said hi"}
    assert len(u["vector"]) == 768


def test_search_without_filter():
    fake = FakeQdrant()
    fake.next_hits = [
        FakeHit("p1", {"run_id": "r", "kind": "task", "text": "hi"}, 0.9),
    ]
    store = MemoryStore(fake)
    hits = store.search([0.0] * 768)
    assert len(hits) == 1
    assert hits[0].id == "p1"
    assert hits[0].score == 0.9
    assert fake.search_calls[0]["filter"] is None


def test_search_with_run_filter():
    fake = FakeQdrant()
    fake.next_hits = []
    store = MemoryStore(fake)
    store.search([0.0] * 768, run_id="run_x", limit=3)
    call = fake.search_calls[0]
    assert call["filter"] is not None  # a qdrant Filter object, not asserting shape
    assert call["limit"] == 3
