"""Tests for storage/repository.py — SqliteEvidenceRepository."""

from __future__ import annotations

import json
import time
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.core.models import AgentProvenance, Evidence, SourceType
from backend.foundation.storage.repository import SqliteEvidenceRepo
from backend.foundation.storage.schema import init_db_on_connection

NOW = int(time.time())


@pytest_asyncio.fixture
async def repo(tmp_path: Path) -> SqliteEvidenceRepo:
    """创建临时数据库并返回 SqliteEvidenceRepo 实例。"""
    db_path = str(tmp_path / "test.db")
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")

    # 使用 schema 模块的 DDL
    import sqlite3 as _sync_sqlite3
    sync_conn = _sync_sqlite3.connect(db_path)
    init_db_on_connection(sync_conn)
    sync_conn.close()

    r = SqliteEvidenceRepo(db)
    yield r
    await db.close()


def _id(tag: str) -> str:
    """生成符合 evd_ 前缀 + 26 字符 ULID 正则的测试 ID。"""
    body = (tag + "0" * 26)[:26]
    return f"evd_{body}"


def _evd(**kwargs) -> Evidence:
    defaults = {
        "id": _id("main"),
        "source_type": SourceType.OCR,
        "scope": "user:alice",
        "created_at": NOW,
    }
    return Evidence(**(defaults | kwargs))


# ═══════════════════════════════════════════════════════
# Group 1: save — basic
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_save_returns_id(repo: SqliteEvidenceRepo):
    evd = _evd()
    result = await repo.save(evd)
    assert result == evd.id


@pytest.mark.asyncio
async def test_save_persists_all_fields(repo: SqliteEvidenceRepo):
    evd = _evd(
        source_type=SourceType.TOOL_RESULT,
        raw={"items": [1, 2, 3], "note": "test"},
        quality_score=0.95,
        sensitivity=3,
        scope="shared:lab",
        created_at=1700000000,
    )
    await repo.save(evd)

    row = await repo._db.execute_fetchall("SELECT * FROM evidence WHERE id = ?", (evd.id,))
    assert len(row) == 1
    r = row[0]
    assert r["source_type"] == "TOOL_RESULT"
    assert json.loads(r["raw"]) == {"items": [1, 2, 3], "note": "test"}
    assert r["quality_score"] == 0.95
    assert r["sensitivity"] == 3
    assert r["scope"] == "shared:lab"
    assert r["created_at"] == 1700000000


@pytest.mark.asyncio
async def test_save_enum_source_type_serialized_as_string(repo: SqliteEvidenceRepo):
    """Enum values must be stored as strings (not enum objects)."""
    evd = _evd(source_type=SourceType.MANUAL_CONFIG)
    await repo.save(evd)

    row = await repo._db.execute_fetchall(
        "SELECT source_type FROM evidence WHERE id = ?", (evd.id,)
    )
    assert row[0]["source_type"] == "MANUAL_CONFIG"
    assert isinstance(row[0]["source_type"], str)


# ═══════════════════════════════════════════════════════
# Group 2: get — happy path and not found
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_returns_saved_evidence(repo: SqliteEvidenceRepo):
    evd = _evd(source_type=SourceType.USER_BEHAVIOR, raw={"action": "click"})
    await repo.save(evd)

    fetched = await repo.get(evd.id)
    assert fetched is not None
    assert fetched.id == evd.id
    assert fetched.source_type == SourceType.USER_BEHAVIOR
    assert fetched.raw == {"action": "click"}


@pytest.mark.asyncio
async def test_conversation_provenance_roundtrips(repo: SqliteEvidenceRepo):
    evd = _evd(
        source_type=SourceType.CONVERSATION,
        raw={"user": "hello", "assistant": "hi"},
        provenance=AgentProvenance(
            session_id="session-1",
            run_id="run-1",
            turn_id="turn-1",
            occurred_at=1_700_000_000,
        ),
    )
    await repo.save(evd)

    fetched = await repo.get(evd.id)
    assert fetched is not None
    assert fetched.provenance is not None
    assert fetched.provenance.session_id == "session-1"
    row = await repo._db.execute_fetchall(
        "SELECT provenance FROM evidence WHERE id = ?", (evd.id,)
    )
    assert json.loads(row[0]["provenance"])["turn_id"] == "turn-1"


@pytest.mark.asyncio
async def test_get_returns_none_for_missing_id(repo: SqliteEvidenceRepo):
    result = await repo.get("evd_" + "Z" * 26)
    assert result is None


# ═══════════════════════════════════════════════════════
# Group 3: duplicate ID — overwrite semantics
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_save_duplicate_id_overwrites(repo: SqliteEvidenceRepo):
    dup_id = _id("dup")
    first = _evd(
        id=dup_id,
        source_type=SourceType.OCR,
        raw={"v": 1},
        created_at=1000,
    )
    second = _evd(
        id=dup_id,
        source_type=SourceType.TOOL_RESULT,
        raw={"v": 2},
        created_at=2000,
    )

    await repo.save(first)
    await repo.save(second)

    fetched = await repo.get(dup_id)
    assert fetched is not None
    assert fetched.source_type == SourceType.TOOL_RESULT
    assert fetched.raw == {"v": 2}
    assert fetched.created_at == 2000


@pytest.mark.asyncio
async def test_save_duplicate_does_not_create_extra_rows(repo: SqliteEvidenceRepo):
    dup_id = _id("dupcount")
    await repo.save(_evd(id=dup_id, raw={"n": 1}))
    await repo.save(_evd(id=dup_id, raw={"n": 2}))

    rows = await repo._db.execute_fetchall(
        "SELECT COUNT(*) AS c FROM evidence WHERE id = ?",
        (dup_id,),
    )
    assert rows[0]["c"] == 1


# ═══════════════════════════════════════════════════════
# Group 4: JSON round-trip
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_json_roundtrip_nested(repo: SqliteEvidenceRepo):
    original = _evd(raw={
        "nested": {"deep": [None, 1, "str", True, 3.14]},
        "unicode": "中文测试",
    })
    await repo.save(original)
    fetched = await repo.get(original.id)
    assert fetched is not None
    assert fetched.raw == original.raw


@pytest.mark.asyncio
async def test_json_roundtrip_empty(repo: SqliteEvidenceRepo):
    original = _evd(raw={})
    await repo.save(original)
    fetched = await repo.get(original.id)
    assert fetched is not None
    assert fetched.raw == {}


# ═══════════════════════════════════════════════════════
# Group 5: list_by_scope
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_by_scope_returns_matching(repo: SqliteEvidenceRepo):
    await repo.save(_evd(id=_id("alice1"), scope="user:alice", created_at=1000))
    await repo.save(_evd(id=_id("alice2"), scope="user:alice", created_at=2000))
    await repo.save(_evd(id=_id("bob1"), scope="user:bob", created_at=1500))

    results = await repo.list_by_scope("user:alice", 10)
    assert len(results) == 2
    assert {r.id for r in results} == {_id("alice1"), _id("alice2")}


@pytest.mark.asyncio
async def test_list_by_scope_ordered_by_created_at_desc(repo: SqliteEvidenceRepo):
    await repo.save(_evd(id=_id("old"), scope="user:alice", created_at=1000))
    await repo.save(_evd(id=_id("new"), scope="user:alice", created_at=3000))
    await repo.save(_evd(id=_id("mid"), scope="user:alice", created_at=2000))

    results = await repo.list_by_scope("user:alice", 10)
    ids = [r.id for r in results]
    assert ids == [_id("new"), _id("mid"), _id("old")]


@pytest.mark.asyncio
async def test_list_by_scope_respects_limit(repo: SqliteEvidenceRepo):
    for i in range(5):
        await repo.save(_evd(
            id=_id(f"list{i}"),
            scope="user:alice",
            created_at=1000 + i,
        ))

    results = await repo.list_by_scope("user:alice", 3)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_list_by_scope_returns_empty_for_no_match(repo: SqliteEvidenceRepo):
    await repo.save(_evd(scope="user:alice"))
    results = await repo.list_by_scope("user:noone", 10)
    assert results == []


# ═══════════════════════════════════════════════════════
# Group 6: exception rollback
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_save_exception_rolls_back(repo: SqliteEvidenceRepo, tmp_path: Path):
    """If save fails mid-flight, previous data must not be lost."""
    db_path = str(tmp_path / "test.db")

    # First, save something successfully
    evd1 = _evd(id=_id("rollback1"), raw={"v": 1})
    await repo.save(evd1)

    # Verify it's there
    assert (await repo.get(evd1.id)) is not None

    # Close the DB connection to force an error on next save
    await repo._db.close()

    # Attempting to save on a closed connection should raise
    with pytest.raises(Exception):
        await repo.save(_evd(id=_id("rollback2")))

    # Reopen and verify the first record is intact
    db2 = await aiosqlite.connect(db_path)
    db2.row_factory = aiosqlite.Row
    repo2 = SqliteEvidenceRepo(db2)
    fetched = await repo2.get(evd1.id)
    assert fetched is not None
    assert fetched.raw == {"v": 1}

    # The failed record must not exist
    not_found = await repo2.get(_id("rollback2"))
    assert not_found is None
    await db2.close()
