"""Tests for storage/repository.py — SqlitePreferenceRepo（版本化语义）。"""

from __future__ import annotations

import time
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.core.models import Preference, PreferenceCategory
from backend.foundation.storage.repository import SqlitePreferenceRepo
from backend.foundation.storage.schema import init_db_on_connection

NOW = int(time.time())


def _pref_id(tag: str) -> str:
    body = (tag + "0" * 26)[:26]
    return f"pref_{body}"


def _pref(**kwargs) -> Preference:
    defaults = {
        "id": _pref_id("main"),
        "category": PreferenceCategory.OUTPUT_STYLE,
        "key": "output_style.compact",
        "value": {"enabled": True},
        "confidence": 0.9,
        "version": 1,
        "scope": "user:alice",
        "created_at": NOW,
        "updated_at": NOW,
    }
    return Preference(**(defaults | kwargs))


@pytest_asyncio.fixture
async def repo(tmp_path: Path) -> SqlitePreferenceRepo:
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

    r = SqlitePreferenceRepo(db)
    yield r
    await db.close()


@pytest.mark.asyncio
async def test_save_and_get_by_key(repo):
    pref = _pref()
    saved_id = await repo.save(pref)
    assert saved_id == pref.id

    found = await repo.get_by_key(pref.key, pref.scope)
    assert found is not None
    assert found.id == pref.id
    assert found.version == 1


@pytest.mark.asyncio
async def test_versioning_reuses_stable_id_and_bumps(repo):
    first = _pref()
    saved_id = await repo.save(first)

    # 同一 key+scope 的新对象（新随机 id、version=1）应复用稳定 id 并递增版本
    second = _pref(id=_pref_id("other"), value={"enabled": True, "detail_level": "high"})
    second_id = await repo.save(second)

    assert second_id == saved_id
    stored = await repo.get(second_id)
    assert stored is not None
    assert stored.version == 2
    assert stored.value == {"enabled": True, "detail_level": "high"}
    assert stored.created_at == first.created_at


@pytest.mark.asyncio
async def test_history_contains_old_and_current_versions(repo):
    first = _pref()
    await repo.save(first)
    await repo.save(_pref(id=_pref_id("b"), value={"enabled": False}))
    await repo.save(_pref(id=_pref_id("c"), value={"enabled": True, "detail_level": "low"}))

    history = await repo.get_history(first.id)
    versions = [s.version for s in history]
    assert versions == [1, 2, 3]
    assert history[0].value == {"enabled": True}
    assert history[-1].value == {"enabled": True, "detail_level": "low"}


@pytest.mark.asyncio
async def test_get_history_empty_when_missing(repo):
    history = await repo.get_history(_pref_id("missing"))
    assert history == []
