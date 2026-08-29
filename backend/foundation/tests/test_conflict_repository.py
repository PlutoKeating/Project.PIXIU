"""Tests for storage/repository.py — SqliteConflictRepo（含 row 读取回归）。"""

from __future__ import annotations

import time
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.core.models import ConflictRecord, ConflictResolution
from backend.foundation.storage.repository import SqliteConflictRepo
from backend.foundation.storage.schema import init_db_on_connection

NOW = int(time.time())


def _cfl_id(tag: str) -> str:
    body = (tag + "0" * 26)[:26]
    return f"cfl_{body}"


def _cfl(**kwargs) -> ConflictRecord:
    defaults = {
        "id": _cfl_id("main"),
        "target_knowledge": "knw_AAAAAAAAAAAAAAAAAAAAAAAAAA",
        "field": "body.items[2].amount",
        "old_value": 156,
        "new_value": 186,
        "resolution": ConflictResolution.NEW_WINS,
        "created_at": NOW,
    }
    return ConflictRecord(**(defaults | kwargs))


@pytest_asyncio.fixture
async def repo(tmp_path: Path) -> SqliteConflictRepo:
    db_path = str(tmp_path / "test.db")
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")

    import sqlite3 as _sync_sqlite3
    sync_conn = _sync_sqlite3.connect(db_path)
    init_db_on_connection(sync_conn)
    sync_conn.close()

    r = SqliteConflictRepo(db)
    yield r
    await db.close()


@pytest.mark.asyncio
async def test_save_and_get_roundtrip(repo):
    """回归：_row_to_conflict 不能使用 row.get()（sqlite3.Row 无此方法）。"""
    rec = _cfl()
    saved = await repo.save(rec)
    assert saved == rec.id

    fetched = await repo.get(rec.id)
    assert fetched is not None
    assert fetched.field == "body.items[2].amount"
    assert fetched.old_value == 156
    assert fetched.new_value == 186
    assert fetched.resolution == ConflictResolution.NEW_WINS
    assert fetched.source == "write"  # 默认来源


@pytest.mark.asyncio
async def test_source_roundtrip_sync_marker(repo):
    """SN-3：同步分叉转人工的 ConflictRecord source="sync" 需持久化回读。"""
    rec = _cfl(source="sync")
    await repo.save(rec)

    fetched = await repo.get(rec.id)
    assert fetched is not None
    assert fetched.source == "sync"


@pytest.mark.asyncio
async def test_list_orders_by_created_at_desc(repo):
    older = _cfl(id=_cfl_id("old"), created_at=NOW - 100)
    newer = _cfl(id=_cfl_id("new"), created_at=NOW)
    await repo.save(older)
    await repo.save(newer)

    records = await repo.list()
    assert [r.id for r in records] == [newer.id, older.id]


@pytest.mark.asyncio
async def test_resolve_updates_resolution(repo):
    rec = _cfl()
    await repo.save(rec)

    await repo.resolve(rec.id, "MERGE")

    fetched = await repo.get(rec.id)
    assert fetched is not None
    assert fetched.resolution == ConflictResolution.MERGE
