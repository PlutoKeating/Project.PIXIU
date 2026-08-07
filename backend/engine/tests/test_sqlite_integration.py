"""引擎 × SQLite 仓储全链路集成测试。

验证五个引擎 Service 在 foundation 的 SQLite 仓储上可端到端运行：
ingest → knowledge（建图/向量/FTS）→ preference（版本化）→ conflict → security。
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.engine.conflict import ConflictService
from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.kylin import MockEmbedding
from backend.engine.preference import PreferenceService
from backend.engine.security import SecurityService
from backend.foundation.core.models import KnowledgeStatus
from backend.foundation.storage.repository import (
    SqliteConflictRepo,
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
    SqlitePreferenceRepo,
)
from backend.foundation.storage.schema import init_db_on_connection


@pytest_asyncio.fixture
async def stack(tmp_path: Path):
    """临时 SQLite 数据库 + 全部仓储 + 引擎服务。"""
    db_path = str(tmp_path / "pixiu.db")
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")

    import sqlite3 as _sync_sqlite3
    sync_conn = _sync_sqlite3.connect(db_path)
    init_db_on_connection(sync_conn)
    sync_conn.close()

    repos = {
        "evidence": SqliteEvidenceRepo(db),
        "knowledge": SqliteKnowledgeRepo(db),
        "preference": SqlitePreferenceRepo(db),
        "entity": SqliteEntityRepo(db),
        "conflict": SqliteConflictRepo(db),
    }
    services = {
        "ingestion": IngestionService(evidence_repo=repos["evidence"]),
        "knowledge": KnowledgeService(
            knw_repo=repos["knowledge"],
            entity_repo=repos["entity"],
            embedder=MockEmbedding(dim=32),
        ),
        "preference": PreferenceService(pref_repo=repos["preference"]),
        "conflict": ConflictService(
            knw_repo=repos["knowledge"], conflict_repo=repos["conflict"]
        ),
        "security": SecurityService(
            knw_repo=repos["knowledge"], entity_repo=repos["entity"]
        ),
    }
    yield {"db": db, "repos": repos, "services": services}
    await db.close()


@pytest.mark.asyncio
async def test_full_write_pipeline_on_sqlite(stack):
    db = stack["db"]
    repos = stack["repos"]
    services = stack["services"]

    # 1) ingest：OCR 支出清单落 evidence
    evidence = await services["ingestion"].ingest(
        "OCR",
        {
            "title": "2026年4月家庭支出清单",
            "body": {
                "items": [
                    {"category": "水电燃气", "vendor": "国家电网", "amount": 210.0}
                ]
            },
        },
        scope="shared:home",
    )
    assert evidence.id.startswith("evd_")
    stored_evd = await repos["evidence"].get(evidence.id)
    assert stored_evd is not None

    # 2) knowledge：结构化 + 建图 + 向量/外键可用
    item = await services["knowledge"].structure(evidence)
    assert item.id.startswith("knw_")
    assert item.embedding_ref == f"vec_{item.id}"
    assert await repos["knowledge"].get(item.id) is not None

    relations = await repos["entity"].list_relations()
    assert relations
    assert all(r.src.startswith("ent_") and r.dst.startswith("ent_") for r in relations)

    vec_rows = await db.execute_fetchall(
        "SELECT dim, vec FROM knowledge_vec WHERE knowledge_id = ?", (item.id,)
    )
    assert len(vec_rows) == 1
    assert vec_rows[0]["dim"] == 32
    assert len(vec_rows[0]["vec"]) == 32

    # 3) preference：OCR 财务清单 → SECURITY_POLICY，重复提取版本递增
    prefs = await services["preference"].extract(evidence)
    assert any(p.category.value == "SECURITY_POLICY" for p in prefs)
    prefs2 = await services["preference"].extract(evidence)
    assert prefs2[0].version == 2
    history = await repos["preference"].get_history(prefs2[0].id)
    assert [s.version for s in history] == [1, 2]

    # 4) conflict：同标题金额变化 → 冲突记录 + 旧版 SUPERSEDED
    ev2 = await services["ingestion"].ingest(
        "OCR",
        {
            "title": "2026年4月家庭支出清单",
            "body": {
                "items": [
                    {"category": "水电燃气", "vendor": "国家电网", "amount": 186.0}
                ]
            },
        },
        scope="shared:home",
    )
    new_item = await services["knowledge"].structure(ev2)
    record = await services["conflict"].arbitrate(new_item)
    assert record is not None
    assert "amount" in record.field
    fetched_rec = await repos["conflict"].get(record.id)
    assert fetched_rec is not None  # 回归保护：冲突记录可读（row 读取修复）

    # 5) security：自然语言遗忘（pending → confirmed）
    pending = await services["security"].forget("忘记那张4月支出清单", confirm=False)
    assert pending.status == "pending"
    assert pending.cascade.get("evidence_count", 0) >= 1

    done = await services["security"].forget("忘记那张4月支出清单", confirm=True)
    assert done.status == "forgotten"
    forgotten = await repos["knowledge"].get(new_item.id)
    assert forgotten is not None
    assert forgotten.status == KnowledgeStatus.FORGOTTEN
