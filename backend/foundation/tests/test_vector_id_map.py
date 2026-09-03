"""Persistent mapping tests for Kylin Vector Engine integer primary keys."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite
import pytest

from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.storage.vector_id_map import SqliteVectorIdMap


async def _open(path: Path) -> aiosqlite.Connection:
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    return db


@pytest.mark.asyncio
async def test_mapping_is_stable_and_resolvable_after_database_reopen(
    tmp_path: Path,
) -> None:
    path = tmp_path / "mapping.db"
    sync_db = sqlite3.connect(path)
    init_db_on_connection(sync_db)
    sync_db.close()

    first_db = await _open(path)
    first_map = SqliteVectorIdMap(first_db)
    vector_id = await first_map.get_or_create("knw_01KYSVDG0739TWR7179BEYETVT")
    await first_db.close()

    second_db = await _open(path)
    second_map = SqliteVectorIdMap(second_db)
    try:
        assert await second_map.get_or_create(
            "knw_01KYSVDG0739TWR7179BEYETVT"
        ) == vector_id
        assert await second_map.resolve([vector_id, vector_id + 1]) == {
            vector_id: "knw_01KYSVDG0739TWR7179BEYETVT"
        }
    finally:
        await second_db.close()
