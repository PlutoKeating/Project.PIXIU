"""Behavior tests for the portable vector store interface."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.core.models import KnowledgeItem, KnowledgeKind
from backend.foundation.storage.repository import SqliteKnowledgeRepo
from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.storage.vector_store import SqliteVectorStore


def _item(tag: str) -> KnowledgeItem:
    now = int(time.time())
    return KnowledgeItem(
        id=f"knw_{(tag + '0' * 26)[:26]}",
        kind=KnowledgeKind.FACT,
        title=tag,
        scope="user:test",
        created_at=now,
        updated_at=now,
    )


@pytest_asyncio.fixture
async def vector_store(tmp_path: Path):
    db_path = tmp_path / "vectors.db"
    sync_db = sqlite3.connect(db_path)
    init_db_on_connection(sync_db)
    sync_db.close()

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    repo = SqliteKnowledgeRepo(db)
    first = _item("first")
    second = _item("second")
    await repo.save(first)
    await repo.save(second)
    yield SqliteVectorStore(db), first, second
    await db.close()


@pytest.mark.asyncio
async def test_search_returns_nearest_knowledge_id(vector_store) -> None:
    store, first, second = vector_store
    await store.upsert(first.id, [1.0, 0.0])
    await store.upsert(second.id, [0.0, 1.0])

    matches = await store.search([0.9, 0.1], limit=1)

    assert store.runtime == "portable"
    assert [match.knowledge_id for match in matches] == [first.id]
    assert matches[0].score > 0.9


@pytest.mark.asyncio
async def test_delete_removes_vector_from_future_searches(vector_store) -> None:
    store, first, _ = vector_store
    await store.upsert(first.id, [1.0, 0.0])

    await store.delete(first.id)

    assert await store.search([1.0, 0.0], limit=5) == []
