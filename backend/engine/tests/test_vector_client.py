"""Public contract tests for the Kylin Vector Engine adapter."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest

from backend.engine.kylin.vector import VectorEngineClient


class _FakeNativeClient:
    calls: list[tuple[object, ...]] = []

    def __init__(self, app_id: str, host: str, port: int) -> None:
        type(self).calls = [("connect", app_id, host, port)]

    def load_collection(self, name: str) -> None:
        type(self).calls.append(("load_collection", name))

    def upsert(
        self, name: str, vectors: list[list[float]], ids: list[int]
    ) -> int:
        type(self).calls.append(("upsert", name, vectors, ids))
        return len(ids)

    def delete(self, name: str, ids: list[int]) -> int:
        type(self).calls.append(("delete", name, ids))
        return len(ids)


def _install_fake_native(monkeypatch) -> ModuleType:
    module = ModuleType("backend.engine.kylin._kylin_vector_client")
    module.VectorEngineClient = _FakeNativeClient  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules, "backend.engine.kylin._kylin_vector_client", module
    )
    return module


def test_load_collection_delegates_to_system_client(monkeypatch) -> None:
    _install_fake_native(monkeypatch)

    client = VectorEngineClient(app_id="test", host="vector.local", port=19531)
    client.load_collection("pixiu_memory")

    assert _FakeNativeClient.calls == [
        ("connect", "test", "vector.local", 19531),
        ("load_collection", "pixiu_memory"),
    ]


def test_upsert_replaces_vectors_by_explicit_id(monkeypatch) -> None:
    _install_fake_native(monkeypatch)
    client = VectorEngineClient()

    count = client.upsert("pixiu_memory", [[0.1, 0.2]], [42])

    assert count == 1
    assert _FakeNativeClient.calls[-1] == (
        "upsert",
        "pixiu_memory",
        [[0.1, 0.2]],
        [42],
    )


def test_delete_accepts_ids_instead_of_raw_filter_expressions(monkeypatch) -> None:
    _install_fake_native(monkeypatch)
    client = VectorEngineClient()

    count = client.delete("pixiu_memory", [7, 11])

    assert count == 2
    assert _FakeNativeClient.calls[-1] == ("delete", "pixiu_memory", [7, 11])


def test_upsert_rejects_vector_id_count_mismatch(monkeypatch) -> None:
    _install_fake_native(monkeypatch)
    client = VectorEngineClient()

    with pytest.raises(ValueError, match="vector and id counts must match"):
        client.upsert("pixiu_memory", [[0.1], [0.2]], [42])


def test_empty_mutations_are_noops(monkeypatch) -> None:
    _install_fake_native(monkeypatch)
    client = VectorEngineClient()

    assert client.upsert("pixiu_memory", [], []) == 0
    assert client.delete("pixiu_memory", []) == 0
    assert _FakeNativeClient.calls == [("connect", "pixiu", "127.0.0.1", 19530)]
