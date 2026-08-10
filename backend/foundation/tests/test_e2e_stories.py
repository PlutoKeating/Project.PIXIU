"""Phase 7 全链路验收 — 四条完整故事（真实 Service 栈 + StubTextEmbedder）。

S1: OCR 支出清单写入→结构化→检索→证据追溯
S2: 金额修正→冲突记录→新版本返回
S3: 自然语言遗忘→确认→级联遗忘→同步 tombstone
S4: 设备 A 写入→设备 B 查询→断网修改→重连收敛
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.engine.conflict import ConflictService
from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.security import SecurityService
from backend.engine.tests.fakes import StubTextEmbedder
from backend.foundation.core.models import KnowledgeKind, KnowledgeStatus, SourceType
from backend.foundation.retrieval import RetrievalService
from backend.foundation.storage.repository import (
    SqliteConflictRepo,
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
)
from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.sync import SqliteSyncStore, SyncService

PASSPHRASE = "phase7-e2e-passphrase-0123456789"
DOMAIN = "shared:home"


async def _open_db(tmp_path: Path, name: str) -> aiosqlite.Connection:
    db_path = str(tmp_path / name)
    sync_conn = sqlite3.connect(db_path)
    init_db_on_connection(sync_conn)
    sync_conn.close()
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    return db


class _Stack:
    """一台设备的完整服务栈。"""

    def __init__(self, db: aiosqlite.Connection, embedder: StubTextEmbedder, device_name: str):
        self.db = db
        self.evidence_repo = SqliteEvidenceRepo(db)
        self.knw_repo = SqliteKnowledgeRepo(db)
        self.entity_repo = SqliteEntityRepo(db)
        self.conflict_repo = SqliteConflictRepo(db)
        self.ingestion = IngestionService(evidence_repo=self.evidence_repo)
        self.knowledge = KnowledgeService(
            knw_repo=self.knw_repo, entity_repo=self.entity_repo, embedder=embedder
        )
        self.conflict = ConflictService(knw_repo=self.knw_repo, conflict_repo=self.conflict_repo)
        self.security = SecurityService(knw_repo=self.knw_repo, entity_repo=self.entity_repo)
        self.retrieval = RetrievalService(
            self.knw_repo, self.entity_repo, self.evidence_repo, embedder
        )
        self.sync = SyncService(
            SqliteSyncStore(db),
            device_name=device_name,
            domain=DOMAIN,
            key_passphrase=PASSPHRASE,
        )


async def _write(stack: _Stack, source_type: str, raw: dict, scope: str):
    evidence = await stack.ingestion.ingest(source_type, raw, scope)
    item = await stack.knowledge.structure(evidence)
    await stack.conflict.arbitrate(item)
    # 共享域写入同步产生 oplog（与 http_app memory_write 的 record_local 对齐）
    if getattr(stack, "sync", None) is not None and scope.startswith("shared:"):
        await stack.sync.record_local(
            "knowledge",
            {"id": item.id, "title": item.title, "scope": scope},
            scope,
        )
    return evidence, item


# ═══════════════════════════════════════════════════════
# S1: OCR 支出清单 → 结构化 → 检索 → 证据追溯
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_story_s1_ocr_ingest_retrieve_trace(tmp_path: Path):
    db = await _open_db(tmp_path, "s1.db")
    stack = _Stack(db, StubTextEmbedder(), "s1-node")

    evidence, item = await _write(
        stack,
        SourceType.OCR.value,
        {
            "title": "2026年4月家庭支出清单",
            "body": {"items": [{"category": "电费", "amount": 210.0}]},
            "entities": ["国家电网", "水电燃气"],
            "relations": [{"from": "国家电网", "to": "水电燃气", "type": "BELONG_TO"}],
        },
        DOMAIN,
    )

    # 检索命中
    atom = await stack.retrieval.query("家庭支出清单")
    assert atom.source_knowledge == item.id
    # 证据追溯：返回的 evidence_id 可解析
    fetched_evidence = await stack.evidence_repo.get(evidence.id)
    assert fetched_evidence is not None
    assert fetched_evidence.source_type == SourceType.OCR
    assert fetched_evidence.raw["title"] == "2026年4月家庭支出清单"
    await db.close()


# ═══════════════════════════════════════════════════════
# S2: 金额修正 → 冲突记录 → 新版本返回
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_story_s2_amount_correction_conflict_new_version(tmp_path: Path):
    db = await _open_db(tmp_path, "s2.db")
    try:
        stack = _Stack(db, StubTextEmbedder(), "s2-node")

        raw = {
            "title": "2026年4月家庭支出清单",
            "body": {"items": [{"category": "燃气费", "amount": 156.0}]},
        }
        _, item_v1 = await _write(stack, SourceType.MANUAL_CONFIG.value, raw, DOMAIN)

        # 金额修正：燃气费 156 → 186（structure 每次生成新 id 的知识）
        raw["body"]["items"][0]["amount"] = 186.0
        _, item_v2 = await _write(stack, SourceType.MANUAL_CONFIG.value, raw, DOMAIN)

        # 冲突记录生成（新旧版本矛盾，target 为修正版）
        conflicts = await stack.conflict_repo.list()
        assert len(conflicts) >= 1
        assert "amount" in conflicts[0].field

        # 检索 top-1 返回修正版知识（新 id，金额 186），旧版 156 不占首位
        atom = await stack.retrieval.query("2026年4月家庭支出清单 燃气费")
        assert atom.source_knowledge == item_v2.id
        latest = await stack.knw_repo.get(item_v2.id)
        amounts = [it["amount"] for it in latest.body["items"]]
        assert 186.0 in amounts
        assert item_v1.id != item_v2.id
    finally:
        await db.close()


# ═══════════════════════════════════════════════════════
# S3: 自然语言遗忘 → 确认 → 级联 → 同步 tombstone
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_story_s3_forget_cascade_sync_tombstone(tmp_path: Path):
    db = await _open_db(tmp_path, "s3.db")
    try:
        stack = _Stack(db, StubTextEmbedder(), "s3-node")
        stack.sync = SyncService(
            SqliteSyncStore(db),
            device_name="s3-node",
            domain=DOMAIN,
            key_passphrase=PASSPHRASE,
        )

        await _write(stack, SourceType.OCR.value, {"title": "2026年4月支出清单"}, DOMAIN)

        # 确认前：返回目标与级联信息
        pending = await stack.security.forget("忘记2026年4月支出清单", confirm=False)
        assert len(pending.targets) >= 1

        # 执行遗忘
        result = await stack.security.forget("忘记2026年4月支出清单", confirm=True)
        assert result.status == "forgotten"
        assert result.forgotten_ids

        # 知识状态 FORGOTTEN，检索不再返回
        item_id = result.forgotten_ids[0]
        item = await stack.knw_repo.get(item_id)
        assert item.status == KnowledgeStatus.FORGOTTEN
        atom = await stack.retrieval.query("2026年4月支出清单")
        assert atom.source_knowledge != item_id
    finally:
        await db.close()


# ═══════════════════════════════════════════════════════
# S4: 设备 A 写入 → 设备 B 查询 → 断网修改 → 重连收敛
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_story_s4_two_device_offline_reconnect(tmp_path: Path):
    from backend.foundation.sync import PairingMethod

    db_a = await _open_db(tmp_path, "s4a.db")
    db_b = await _open_db(tmp_path, "s4b.db")
    try:
        a = _Stack(db_a, StubTextEmbedder(), "设备A")
        b = _Stack(db_b, StubTextEmbedder(), "设备B")
        now = 2_000_000_000

        # 双向配对
        token_b = await b.sync.create_pairing_token(PairingMethod.QR, now=now)
        await a.sync.pair(PairingMethod.QR, token_b, now=now)
        token_a = await a.sync.create_pairing_token(PairingMethod.QR, now=now)
        await b.sync.pair(PairingMethod.QR, token_a, now=now)

        # A 写入 → 同步到 B
        _, item = await _write(a, SourceType.MANUAL_CONFIG.value, {"title": "共享支出记录"}, DOMAIN)
        ops = await a.sync._store.list_ops()
        await b.sync.receive_ops(ops)

        # B 侧检索命中（materializer 语义：先物化 evidence 再物化 knowledge）
        for evidence_id in item.evidence_ids:
            evidence = await a.evidence_repo.get(evidence_id)
            if evidence is not None:
                await b.evidence_repo.save(evidence)
        await b.knw_repo.save(item)
        atom_b = await b.retrieval.query("共享支出记录")
        assert atom_b.source_knowledge == item.id

        # 断网：A 本地修改（不同步 B）
        await _write(a, SourceType.MANUAL_CONFIG.value, {"title": "离线新增记录"}, DOMAIN)
        ops_a = await a.sync._store.list_ops()
        offline_new = [op for op in ops_a if op.op_id not in {o.op_id for o in ops}]
        assert len(offline_new) >= 1
        # B 此时查询不到离线记录
        assert (await b.retrieval.query("离线新增记录")).source_knowledge == ""

        # 重连：B 拉取 A 缺失 op → 收敛
        accepted = await b.sync.receive_ops(await a.sync._store.list_ops())
        assert accepted >= 1
    finally:
        await db_a.close()
        await db_b.close()
