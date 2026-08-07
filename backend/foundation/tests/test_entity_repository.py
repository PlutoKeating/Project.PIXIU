"""Tests for storage/repository.py — SqliteEntityRepo (实体-关系图)."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.core.models import Entity, Relation
from backend.foundation.storage.repository import SqliteEntityRepo
from backend.foundation.storage.schema import init_db_on_connection


def _ent_id(tag: str) -> str:
    body = (tag + "0" * 26)[:26]
    return f"ent_{body}"


def _ent(**kwargs) -> Entity:
    defaults = {
        "id": _ent_id("main"),
        "name": "国家电网",
        "norm_name": "国家电网",
        "type": "ORG",
    }
    return Entity(**(defaults | kwargs))


@pytest_asyncio.fixture
async def repo(tmp_path: Path) -> SqliteEntityRepo:
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

    r = SqliteEntityRepo(db)
    yield r
    await db.close()


@pytest.mark.asyncio
async def test_save_and_get_entity(repo):
    ent = _ent()
    saved_id = await repo.save_entity(ent)
    assert saved_id == ent.id

    fetched = await repo.get_entity(ent.id)
    assert fetched is not None
    assert fetched.name == "国家电网"
    assert fetched.norm_name == "国家电网"


@pytest.mark.asyncio
async def test_find_entity_by_name(repo):
    await repo.save_entity(
        _ent(id=_ent_id("a"), name="国家电网", norm_name="国家电网", type="ORG")
    )
    await repo.save_entity(
        _ent(id=_ent_id("b"), name="国家电网公司", norm_name="国家电网公司", type="ORG")
    )

    found = await repo.find_entity_by_name("国家电网")
    assert found is not None
    assert found.id == _ent_id("a")


@pytest.mark.asyncio
async def test_save_relation_and_get_relations(repo):
    a = _ent_id("a")
    b = _ent_id("b")
    await repo.save_entity(_ent(id=a, name="国家电网", norm_name="国家电网", type="ORG"))
    await repo.save_entity(_ent(id=b, name="水电燃气", norm_name="水电燃气", type="CATEGORY"))

    await repo.save_relation(a, b, "BELONG_TO")

    rels = await repo.get_relations(a)
    assert len(rels) == 1
    assert rels[0].src == a
    assert rels[0].dst == b
    assert rels[0].type == "BELONG_TO"


@pytest.mark.asyncio
async def test_list_relations(repo):
    a = _ent_id("a")
    b = _ent_id("b")
    c = _ent_id("c")
    await repo.save_entity(_ent(id=a, name="国家电网", norm_name="国家电网", type="ORG"))
    await repo.save_entity(_ent(id=b, name="水电燃气", norm_name="水电燃气", type="CATEGORY"))
    await repo.save_entity(_ent(id=c, name="新奥燃气", norm_name="新奥燃气", type="ORG"))

    await repo.save_relation(a, b, "BELONG_TO")
    await repo.save_relation(c, b, "BELONG_TO")

    rels = await repo.list_relations()
    assert len(rels) == 2
    assert isinstance(rels[0], Relation)


@pytest.mark.asyncio
async def test_relation_fk_requires_existing_entity_ids(repo):
    """关系表外键指向 entities(id)，写入不存在的 id 必须报错。"""
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        await repo.save_relation(
            "ent_AAAAAAAAAAAAAAAAAAAAAAAAAA", "ent_BBBBBBBBBBBBBBBBBBBBBBBBBB", "BELONG_TO"
        )
