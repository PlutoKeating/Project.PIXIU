"""Tests for B3-3 — 冲突 severity 分级（后端）。

[S3.1] 把冲突打扰从「一刀切」升级为按风险分级：
- MERGE     → low（自动合并静默）
- NEW_WINS  → medium（自动裁决但用户应知晓）
- MANUAL    → high（需人工确认）

覆盖：映射函数、模型向后兼容默认、Arbiter 三态构造、
ConflictService 端到端、SqliteConflictRepo 持久化/回读（含旧行派生）。
API 序列化与 WS 广播用例在 test_api.py（复用其 client fixture）；
迁移 #8 旧库补列的 schema 级用例在 test_schema.py。
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.core.idgen import gen_knowledge_id
from backend.foundation.core.models import (
    ConflictRecord,
    ConflictResolution,
    KnowledgeItem,
    conflict_severity_for,
)
from backend.engine.conflict import ConflictService
from backend.engine.conflict.arbiter import Arbiter
from backend.foundation.storage.repository import SqliteConflictRepo
from backend.foundation.storage.schema import init_db_on_connection

NOW = int(time.time())

CFL_ID = "cfl_" + "a" * 26
KNW_ID = "knw_" + "a" * 26


def _item(
    *,
    title: str,
    body: dict[str, Any],
    entities: list[str] | None = None,
    scope: str = "user:alice",
) -> KnowledgeItem:
    return KnowledgeItem(
        id=gen_knowledge_id(),
        kind="FACT",
        title=title,
        body=body,
        entities=list(entities or []),
        relations=[],
        status="ACTIVE",
        version=1,
        evidence_ids=[],
        scope=scope,
        created_at=NOW,
        updated_at=NOW,
    )


# ═══════════════════════════════════════════════════════
# 1. 三态映射（models.conflict_severity_for）
# ═══════════════════════════════════════════════════════

def test_severity_mapping_table():
    assert conflict_severity_for(ConflictResolution.MERGE) == "low"
    assert conflict_severity_for(ConflictResolution.NEW_WINS) == "medium"
    assert conflict_severity_for(ConflictResolution.MANUAL) == "high"
    # 字符串输入（DB 回读路径 row["resolution"] 是 str）
    assert conflict_severity_for("MERGE") == "low"
    assert conflict_severity_for("NEW_WINS") == "medium"
    assert conflict_severity_for("MANUAL") == "high"
    # 未知值保守回落 high（宁可打扰不漏报）
    assert conflict_severity_for("UNKNOWN") == "high"


def test_conflict_record_severity_default_high_backward_compatible():
    """旧代码构造 ConflictRecord 不带 severity → 默认 high（最保守）。"""
    c = ConflictRecord(
        id=CFL_ID,
        target_knowledge=KNW_ID,
        field="x",
        old_value=1,
        new_value=2,
        created_at=NOW,
    )
    assert c.severity == "high"
    # /conflicts 序列化依赖 model_dump 带出 severity
    assert c.model_dump(mode="json")["severity"] == "high"


# ═══════════════════════════════════════════════════════
# 2. Arbiter 三态构造
# ═══════════════════════════════════════════════════════

def test_arbiter_records_carry_severity_per_resolution():
    arb = Arbiter()
    old = _item(
        title="冲突场景-10",
        body={"items": [{"vendor": "Alpha", "amount": 110.0}]},
        entities=["冲突实体-10"],
    )

    # NEW_WINS：同实体同字段数值矛盾 → medium
    new_wins = _item(
        title="冲突场景-10",
        body={"items": [{"vendor": "Alpha", "amount": 210.0}]},
        entities=["冲突实体-10"],
    )
    rec = arb.detect(new_wins, old)
    assert rec is not None
    assert rec.resolution == ConflictResolution.NEW_WINS
    assert rec.severity == "medium"

    # MERGE：同实体互补扩展、无字段冲突 → low
    merge = _item(
        title="冲突场景-10",
        body={
            "items": [
                {"vendor": "Alpha", "amount": 110.0},
                {"vendor": "Beta", "amount": 60.0},
            ]
        },
        entities=["冲突实体-10"],
    )
    rec = arb.detect(merge, old)
    assert rec is not None
    assert rec.resolution == ConflictResolution.MERGE
    assert rec.severity == "low"

    # MANUAL：数值矛盾 + 标题带人工确认标记 → high
    manual = _item(
        title="冲突场景-10（人工确认）",
        body={"items": [{"vendor": "Alpha", "amount": 210.0}]},
        entities=["冲突实体-10"],
    )
    rec = arb.detect(manual, old)
    assert rec is not None
    assert rec.resolution == ConflictResolution.MANUAL
    assert rec.severity == "high"


# ═══════════════════════════════════════════════════════
# 3. ConflictService 端到端（内存 fake 仓储）
# ═══════════════════════════════════════════════════════

class _FakeKnowledgeRepo:
    def __init__(self) -> None:
        self.items: dict[str, KnowledgeItem] = {}

    async def save(self, item: KnowledgeItem) -> str:
        self.items[item.id] = item
        return item.id

    async def get(self, id: str) -> Optional[KnowledgeItem]:
        return self.items.get(id)

    async def list_active(self) -> list[KnowledgeItem]:
        return [i for i in self.items.values() if i.status == "ACTIVE"]


class _FakeConflictRepo:
    def __init__(self) -> None:
        self.records: list[ConflictRecord] = []

    async def save(self, record: ConflictRecord) -> str:
        self.records.append(record)
        return record.id

    async def get(self, id: str) -> Optional[ConflictRecord]:
        for r in self.records:
            if r.id == id:
                return r
        return None

    async def list(self) -> list[ConflictRecord]:
        return list(self.records)


@pytest.mark.asyncio
async def test_service_arbitrate_new_wins_severity_medium():
    knw = _FakeKnowledgeRepo()
    cfl = _FakeConflictRepo()
    service = ConflictService(knw_repo=knw, conflict_repo=cfl)

    old = _item(
        title="bill",
        body={"items": [{"vendor": "Alpha", "amount": 156}]},
        entities=["Alpha"],
    )
    new = _item(
        title="bill",
        body={"items": [{"vendor": "Alpha", "amount": 186}]},
        entities=["Alpha"],
    )
    await knw.save(old)

    record = await service.arbitrate(new)
    assert record is not None
    assert record.resolution == ConflictResolution.NEW_WINS
    assert record.severity == "medium"
    assert cfl.records[0].severity == "medium"


# ═══════════════════════════════════════════════════════
# 4. SqliteConflictRepo 持久化 / 回读
# ═══════════════════════════════════════════════════════

@pytest_asyncio.fixture
async def repo(tmp_path: Path) -> SqliteConflictRepo:
    db_path = str(tmp_path / "test.db")
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")

    sync_conn = sqlite3.connect(db_path)
    init_db_on_connection(sync_conn)
    sync_conn.close()

    yield SqliteConflictRepo(db)
    await db.close()


@pytest.mark.asyncio
async def test_repo_severity_roundtrip(repo):
    cases = [
        ("cfl_" + "1" * 26, ConflictResolution.MERGE, "low"),
        ("cfl_" + "2" * 26, ConflictResolution.NEW_WINS, "medium"),
        ("cfl_" + "3" * 26, ConflictResolution.MANUAL, "high"),
    ]
    for cfl_id, resolution, expected in cases:
        rec = ConflictRecord(
            id=cfl_id,
            target_knowledge=KNW_ID,
            field="x",
            old_value=1,
            new_value=2,
            resolution=resolution,
            created_at=NOW,
            severity=conflict_severity_for(resolution),
        )
        await repo.save(rec)
        fetched = await repo.get(cfl_id)
        assert fetched is not None
        assert fetched.resolution == resolution
        assert fetched.severity == expected


@pytest.mark.asyncio
async def test_repo_legacy_row_severity_derived_from_resolution(tmp_path):
    """迁移 #8 后旧行（SQL 默认 'high'）回读按 resolution 派生，避免一律高打扰。"""
    db_path = str(tmp_path / "legacy.db")
    sync = sqlite3.connect(db_path)
    sync.execute(
        """CREATE TABLE conflict_records (
            id               TEXT PRIMARY KEY,
            target_knowledge TEXT NOT NULL,
            field            TEXT NOT NULL DEFAULT '',
            old_value        TEXT NOT NULL DEFAULT 'null',
            new_value        TEXT NOT NULL DEFAULT 'null',
            resolution       TEXT NOT NULL DEFAULT 'NEW_WINS',
            created_at       INTEGER NOT NULL,
            source           TEXT NOT NULL DEFAULT 'write'
        )"""
    )
    sync.execute(
        "INSERT INTO conflict_records (id, target_knowledge, resolution, created_at) "
        "VALUES (?, ?, ?, ?)",
        (CFL_ID, KNW_ID, "NEW_WINS", 1),
    )
    # 迁移 #8 补列（SQL 默认 high）
    sync.execute(
        "ALTER TABLE conflict_records ADD COLUMN severity TEXT NOT NULL DEFAULT 'high'"
    )
    sync.commit()
    raw = sync.execute(
        "SELECT severity FROM conflict_records WHERE id = ?", (CFL_ID,)
    ).fetchone()
    assert raw[0] == "high"  # 列级兜底
    sync.close()

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")
    try:
        fetched = await SqliteConflictRepo(db).get(CFL_ID)
        assert fetched is not None
        assert fetched.resolution == ConflictResolution.NEW_WINS
        # 回读派生：NEW_WINS → medium（而非列默认 high）
        assert fetched.severity == "medium"
    finally:
        await db.close()
