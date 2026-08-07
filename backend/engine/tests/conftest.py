"""Engine 测试公共夹具：SQLite 临时库 + 仓储。

生产代码不含 mock；测试统一落在真实 SQLite 仓储上。
embedding 相关测试使用 tests/fakes.py 的 StubTextEmbedder（仅测试用）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite
import pytest_asyncio

from backend.foundation.storage.repository import (
    SqliteConflictRepo,
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
    SqlitePreferenceRepo,
)
from backend.foundation.storage.schema import init_db_on_connection


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> aiosqlite.Connection:
    """临时 SQLite 数据库（已建表，WAL + 外键）。"""
    db_path = str(tmp_path / "pixiu.db")
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")

    sync_conn = sqlite3.connect(db_path)
    init_db_on_connection(sync_conn)
    sync_conn.close()

    yield db
    await db.close()


@pytest_asyncio.fixture
async def repos(db):
    """真实 SQLite 仓储集合。"""
    return {
        "evidence": SqliteEvidenceRepo(db),
        "knowledge": SqliteKnowledgeRepo(db),
        "preference": SqlitePreferenceRepo(db),
        "entity": SqliteEntityRepo(db),
        "conflict": SqliteConflictRepo(db),
    }
