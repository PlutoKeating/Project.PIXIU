"""Contract tests for the system Vector Engine store adapter."""

from __future__ import annotations

import pytest

from backend.engine.kylin.vector_store import KylinVectorStore


class _FakeClient:
    def __init__(self, *, exists: bool = False) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.exists = exists

    def has_collection(self, name: str) -> bool:
        self.calls.append(("has_collection", name))
        return self.exists

    def create_collection(
        self, name: str, dim: int, auto_id: bool, dynamic: bool
    ) -> None:
        self.calls.append(("create_collection", name, dim, auto_id, dynamic))

    def load_collection(self, name: str) -> None:
        self.calls.append(("load_collection", name))

    def upsert(
        self, name: str, vectors: list[list[float]], ids: list[int]
    ) -> int:
        self.calls.append(("upsert", name, vectors, ids))
        return len(ids)

    def search(self, name: str, query: list[float], top_k: int):
        self.calls.append(("search", name, query, top_k))
        return [{"id": 77, "score": 0.9}, {"id": 99, "score": 0.8}]

    def delete(self, name: str, ids: list[int]) -> int:
        self.calls.append(("delete", name, ids))
        return len(ids)


class _FakeIdMap:
    def __init__(self) -> None:
        self.bindings: dict[str, int] = {"knw_test": 77}
        self.removed: list[str] = []

    async def get_or_create(self, knowledge_id: str) -> int:
        return self.bindings[knowledge_id]

    async def resolve(self, vector_ids: list[int]) -> dict[int, str]:
        return {77: "knw_test"}

    async def get(self, knowledge_id: str) -> int | None:
        return self.bindings.get(knowledge_id)

    async def remove(self, knowledge_id: str) -> None:
        self.removed.append(knowledge_id)
        self.bindings.pop(knowledge_id, None)


@pytest.mark.asyncio
async def test_upsert_creates_and_loads_collection_with_explicit_id() -> None:
    client = _FakeClient()
    store = KylinVectorStore(client, _FakeIdMap(), collection="pixiu_memory")

    await store.upsert("knw_test", [0.1, 0.2])

    assert store.runtime == "kylin"
    assert client.calls == [
        ("has_collection", "pixiu_memory"),
        ("create_collection", "pixiu_memory", 2, False, True),
        ("load_collection", "pixiu_memory"),
        ("upsert", "pixiu_memory", [[0.1, 0.2]], [77]),
    ]


@pytest.mark.asyncio
async def test_search_resolves_only_known_canonical_ids() -> None:
    client = _FakeClient(exists=True)
    store = KylinVectorStore(client, _FakeIdMap(), collection="pixiu_memory")

    matches = await store.search([0.2, 0.8], limit=2)

    assert [(match.knowledge_id, match.score) for match in matches] == [
        ("knw_test", 0.9)
    ]
    assert client.calls == [
        ("has_collection", "pixiu_memory"),
        ("load_collection", "pixiu_memory"),
        ("search", "pixiu_memory", [0.2, 0.8], 2),
    ]


@pytest.mark.asyncio
async def test_delete_removes_remote_vector_before_mapping() -> None:
    client = _FakeClient(exists=True)
    id_map = _FakeIdMap()
    store = KylinVectorStore(client, id_map, collection="pixiu_memory")

    await store.delete("knw_test")

    assert client.calls == [("delete", "pixiu_memory", [77])]
    assert id_map.removed == ["knw_test"]
