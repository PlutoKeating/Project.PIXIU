"""Tests for api/di.py — 依赖注入与数据库初始化。"""

from __future__ import annotations

import pytest

import backend.foundation.api.di as di_module
from backend.engine.conflict import ConflictService
from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.preference import PreferenceService
from backend.engine.security import SecurityService
from backend.foundation.api.di import (
    get_conflict_repo,
    get_conflict_service,
    get_db,
    get_evidence_repo,
    get_flow_service,
    get_ingestion_service,
    get_knowledge_service,
    get_preference_repo,
    get_preference_service,
    get_retrieval_service,
    get_security_service,
    get_sync_service,
    get_vector_store,
    preflight_strict_capabilities,
)
from backend.foundation.core.idgen import gen_evidence_id
from backend.foundation.core.models import Evidence, SourceType
from backend.foundation.flow import FlowService
from backend.foundation.sync import SyncService
from backend.foundation.storage.migrations import latest_version
from backend.foundation.storage.repository import (
    SqliteConflictRepo,
    SqliteEvidenceRepo,
    SqlitePreferenceRepo,
    SqliteKnowledgeRepo,
)
from backend.foundation.storage.vector_store import SqliteVectorStore


class _FakeSettings:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.embedding = "portable"
        self.vector_store = "portable"
        self.vector_app_id = "pixiu-test"
        self.vector_collection = "pixiu_test"
        self.sync_device_name = "test-device"
        self.sync_domain = "shared:test"
        self.sync_key_passphrase = "phase3-di-test-passphrase"
        self.sync_network_enabled = False


@pytest.fixture()
def fresh_di(tmp_path, monkeypatch):
    """替换 settings.db_path 并重置 get_db 单例。"""
    monkeypatch.setattr(di_module, "settings", _FakeSettings(str(tmp_path / "pixiu.db")))
    di_module._db = None
    yield
    di_module._db = None


@pytest.mark.asyncio
async def test_get_db_runs_migrations(fresh_di, tmp_path):
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence'"
        )
        assert len(rows) == 1
        version_rows = await db.execute_fetchall(
            "SELECT MAX(version) FROM _schema_version"
        )
        assert version_rows[0][0] == latest_version()
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_service_factories_return_real_services(fresh_di):
    db = await get_db()
    try:
        assert isinstance(await get_ingestion_service(db), IngestionService)
        assert isinstance(await get_preference_service(db), PreferenceService)
        assert isinstance(await get_conflict_service(db), ConflictService)
        assert isinstance(await get_security_service(db), SecurityService)
        assert isinstance(await get_knowledge_service(db), KnowledgeService)
        assert isinstance(await get_vector_store(db), SqliteVectorStore)
        assert isinstance(await get_evidence_repo(db), SqliteEvidenceRepo)
        assert isinstance(await get_preference_repo(db), SqlitePreferenceRepo)
        assert isinstance(await get_conflict_repo(db), SqliteConflictRepo)
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_strict_kylin_vector_store_fails_closed(fresh_di, monkeypatch):
    db = await get_db()
    di_module.settings.vector_store = "kylin"

    def _unavailable(**kwargs):
        raise RuntimeError("vector engine unavailable")

    monkeypatch.setattr(di_module, "VectorEngineClient", _unavailable)
    try:
        with pytest.raises(RuntimeError, match="vector engine unavailable"):
            await get_vector_store(db)
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_kylin_vector_store_uses_official_local_connection(
    fresh_di, monkeypatch
):
    db = await get_db()
    di_module.settings.vector_store = "kylin"
    received = {}

    class _Client:
        def __init__(self, **kwargs):
            received.update(kwargs)

    monkeypatch.setattr(di_module, "VectorEngineClient", _Client)
    try:
        await get_vector_store(db)
        assert received == {"app_id": "pixiu-test"}
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_auto_vector_store_reports_portable_fallback(fresh_di, monkeypatch):
    db = await get_db()
    di_module.settings.vector_store = "auto"

    def _unavailable(**kwargs):
        raise RuntimeError("vector engine unavailable")

    monkeypatch.setattr(di_module, "VectorEngineClient", _unavailable)
    try:
        store = await get_vector_store(db)
        assert store.runtime == "portable"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_startup_preflight_fails_when_strict_embedding_is_unavailable(
    fresh_di, monkeypatch
):
    di_module.settings.embedding = "kylin"

    def _unavailable(_backend):
        raise RuntimeError("embedding unavailable")

    monkeypatch.setattr(di_module, "get_embedder", _unavailable)

    with pytest.raises(RuntimeError, match="embedding unavailable"):
        await preflight_strict_capabilities()


@pytest.mark.asyncio
async def test_startup_preflight_fails_when_strict_vector_store_is_unavailable(
    fresh_di, monkeypatch
):
    di_module.settings.vector_store = "kylin"

    async def _unavailable(_db):
        raise RuntimeError("vector unavailable")

    monkeypatch.setattr(di_module, "get_vector_store", _unavailable)

    try:
        with pytest.raises(RuntimeError, match="vector unavailable"):
            await preflight_strict_capabilities()
    finally:
        if di_module._db is not None:
            await di_module._db.close()
            di_module._db = None


@pytest.mark.asyncio
async def test_production_di_writes_and_queries_through_vector_store(
    fresh_di, monkeypatch
):
    db = await get_db()
    try:
        knowledge = await get_knowledge_service(db)
        retrieval = await get_retrieval_service(db)
        evidence = Evidence(
            id=gen_evidence_id(),
            source_type=SourceType.MANUAL_CONFIG,
            raw={"title": "向量存储组合根", "body": {"description": "生产接线验证"}},
            quality_score=1.0,
            scope="user:test",
            created_at=1,
        )
        await SqliteEvidenceRepo(db).save(evidence)
        item = await knowledge.structure(evidence)

        async def _legacy_path_must_not_run(self):
            raise AssertionError("legacy KnowledgeRepository vector scan was used")

        monkeypatch.setattr(SqliteKnowledgeRepo, "list_vectors", _legacy_path_must_not_run)
        result = await retrieval.query("向量存储组合根", {"top_k": 1})

        assert result.source_knowledge == item.id
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_flow_factory_composes_real_service(fresh_di):
    db = await get_db()
    try:
        ingestion = await get_ingestion_service(db)
        # 避免在无麒麟 SDK 的测试机调用默认 get_knowledge_service；这里只验证装配边界。
        class _Knowledge:
            async def structure(self, evidence):
                raise AssertionError("not called during composition")

        flow = await get_flow_service(db, ingestion, _Knowledge())
        assert isinstance(flow, FlowService)
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_sync_factory_composes_real_service(fresh_di):
    db = await get_db()
    try:
        sync = await get_sync_service(db)
        assert isinstance(sync, SyncService)
        identity = await sync.initialize()
        assert identity.domain == "shared:test"
    finally:
        await db.close()
