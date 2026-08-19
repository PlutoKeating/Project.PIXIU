"""Tests for api/dbus_service.py — com.kylin.pixiu.Memory。

覆盖：业务方法复用现有 Service、bus name 冲突处理、无 SDK 明确失败、
dbus-next 接口方法注册（不连真实总线）。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.engine.conflict import ConflictService
from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.preference import PreferenceService
from backend.engine.security import SecurityService
from backend.engine.tests.fakes import StubTextEmbedder
from backend.foundation.api.dbus_service import (
    BUS_NAME,
    OBJECT_PATH,
    PixiuDBusInterface,
    PixiuDBusService,
    PixiuError,
    PixiuMemoryHandler,
)
from backend.foundation.retrieval import RetrievalService
from backend.foundation.storage.repository import (
    SqliteConflictRepo,
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
    SqlitePreferenceRepo,
)
from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.sync import SqliteSyncStore, SyncService

PASSPHRASE = "dbus-test-passphrase-0123456789"


async def _make_db(tmp_path: Path, name: str = "dbus.db"):
    db_path = str(tmp_path / name)
    sync_conn = sqlite3.connect(db_path)
    init_db_on_connection(sync_conn)
    sync_conn.close()
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    return db


@pytest_asyncio.fixture
async def handler(tmp_path: Path) -> PixiuMemoryHandler:
    db = await _make_db(tmp_path)
    embedder = StubTextEmbedder(dim=32)
    knw_repo = SqliteKnowledgeRepo(db)
    ent_repo = SqliteEntityRepo(db)
    evd_repo = SqliteEvidenceRepo(db)

    sync_service = SyncService(
        SqliteSyncStore(db),
        device_name="dbus-node",
        domain="shared:home",
        key_passphrase=PASSPHRASE,
    )

    h = PixiuMemoryHandler(
        ingestion=IngestionService(evidence_repo=evd_repo),
        knowledge=KnowledgeService(knw_repo=knw_repo, entity_repo=ent_repo, embedder=embedder),
        preference=PreferenceService(pref_repo=SqlitePreferenceRepo(db)),
        conflict=ConflictService(knw_repo=knw_repo, conflict_repo=SqliteConflictRepo(db)),
        security=SecurityService(knw_repo=knw_repo, entity_repo=ent_repo),
        retrieval=RetrievalService(knw_repo, ent_repo, evd_repo, embedder),
        sync_status=sync_service.status,
    )
    yield h
    await db.close()


# ═══════════════════════════════════════════════════════
# Handler 业务方法（复用 Service）
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_write_reuses_ingestion_pipeline(handler):
    result = await handler.write(
        "OCR",
        {"title": "家庭支出清单", "body": {"items": [{"category": "电费", "amount": 210.0}]}},
        "shared:home",
    )
    assert result["status"] == "accepted"
    assert result["evidence_id"].startswith("evd_")
    assert result["quality_score"] is not None
    assert "conflict_detected" in result


@pytest.mark.asyncio
async def test_query_reuses_retrieval(handler):
    # 先写入一条知识，随后检索命中
    await handler.write(
        "MANUAL_CONFIG",
        {"title": "2026年4月水电燃气支出", "body": {"items": [{"category": "燃气费", "amount": 156.0}]}},
        "shared:home",
    )
    result = await handler.query("水电燃气支出", {"top_k": 5, "scope": "shared:home"})
    assert result["source_knowledge"]
    assert "latency_ms" in result


@pytest.mark.asyncio
async def test_forget_two_phase(handler):
    await handler.write("MANUAL_CONFIG", {"title": "待遗忘清单"}, "shared:home")

    pending = await handler.forget("忘记待遗忘清单", confirm=False)
    assert "targets" in pending

    executed = await handler.forget("忘记待遗忘清单", confirm=True)
    assert executed["status"] == "forgotten"


@pytest.mark.asyncio
async def test_sync_status_reuses_sync_service(handler):
    result = await handler.sync_status()
    assert "domain" in result
    assert result["domain"] == "shared:home"


# ═══════════════════════════════════════════════════════
# 无 SDK 自动降级；严格模式明确失败
# ═══════════════════════════════════════════════════════

def test_production_embedder_falls_back_without_sdk():
    from backend.engine.kylin import PortableTextEmbedding, get_embedder

    assert isinstance(get_embedder(), PortableTextEmbedding)


def test_strict_kylin_embedder_fails_clearly_without_sdk():
    from backend.engine.kylin import get_embedder
    from backend.engine.kylin.errors import KylinSDKUnavailableError

    with pytest.raises(KylinSDKUnavailableError):
        get_embedder("kylin")


# ═══════════════════════════════════════════════════════
# bus name 冲突处理
# ═══════════════════════════════════════════════════════

def test_bus_name_conflict_raises(monkeypatch):
    class FakeRequestReply:
        PRIMARY_OWNER = 1
        IN_QUEUE = 2
        EXISTS = 3
        ALREADY_OWNER = 4

    class FakeBus:
        async def connect(self):
            return self

        def export(self, path, interface):
            pass

        async def request_name(self, name):
            return FakeRequestReply.EXISTS  # 模拟 name 已被占用

        def disconnect(self):
            pass

    monkeypatch.setattr("backend.foundation.api.dbus_service.MessageBus", lambda: FakeBus())
    monkeypatch.setattr("backend.foundation.api.dbus_service.RequestNameReply", FakeRequestReply)

    service = PixiuDBusService(PixiuMemoryHandler())
    with pytest.raises(PixiuError) as exc_info:
        import asyncio

        asyncio.run(service.start())

    assert exc_info.value.error == "BUS_NAME_CONFLICT"
    assert BUS_NAME in exc_info.value.message


# ═══════════════════════════════════════════════════════
# dbus-next 接口方法注册（不连真实总线）
# ═══════════════════════════════════════════════════════

def test_interface_attaches_four_methods():
    from dbus_next.service import ServiceInterface

    interface = PixiuDBusInterface(PixiuMemoryHandler()).create()
    assert isinstance(interface, ServiceInterface)
    methods = interface._get_methods(interface)
    by_name = {m.name: m for m in methods}
    assert set(by_name) == {"Write", "Query", "Forget", "SyncStatus"}
    # 签名：Write/Query (s,s,s)/(s,s)→s，Forget (s,b)→s，SyncStatus ()→s
    assert by_name["Write"].in_signature == "sss"
    assert by_name["Forget"].in_signature == "sb"
    assert by_name["SyncStatus"].in_signature == ""
    assert all(m.out_signature == "s" for m in methods)


@pytest.mark.asyncio
async def test_interface_write_validates_json(handler):
    """非法 JSON 在接口 Write 包装层被拒绝（经总线调用；此处验证 handler 契约前置）。"""
    # handler.write 要求 raw 为 dict：非 dict 输入应明确失败而非静默
    with pytest.raises(TypeError):
        await handler.write("OCR", "not-a-dict", "shared:home")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_interface_query_roundtrip(handler):
    await handler.write(
        "MANUAL_CONFIG",
        {"title": "界面查询测试知识"},
        "shared:home",
    )
    result = await handler.query("界面查询", {"top_k": 5})
    assert result["source_knowledge"]


# ═══════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════

def test_bus_constants():
    assert BUS_NAME == "com.kylin.pixiu.Memory"
    assert OBJECT_PATH == "/com/kylin/pixiu/Memory"
