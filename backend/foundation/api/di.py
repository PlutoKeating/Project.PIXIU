"""PIXIU Foundation — 依赖注入容器

本文件是模块 C api/ 层对引擎 Service 的唯一 import 点：
引擎 Service 与 foundation SQLite 仓储在此组装，供 http_app 路由注入。
"""

from __future__ import annotations

import sqlite3 as _sqlite3

import aiosqlite
from fastapi import Depends

from backend.engine.conflict import ConflictService
from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.kylin import get_embedder, get_ocr
from backend.engine.preference import PreferenceService
from backend.engine.security import SecurityService

from ..core.config import settings
from ..core.logger import get_logger
from .dbus_service import PixiuMemoryHandler
from ..flow import FlowService, SqliteFlowStore
from ..retrieval import RetrievalService
from ..storage.migrations import apply_pending
from ..storage.repository import (
    SqliteConflictRepo,
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
    SqlitePreferenceRepo,
)
from ..sync import SqliteSyncStore, SyncService
from ..sync.runtime import SyncRuntime, create_sync_runtime
from ..sync.materializer import FoundationMaterializer

_log = get_logger(__name__)

_db: aiosqlite.Connection | None = None
_sync_runtime: SyncRuntime | None = None


async def get_db() -> aiosqlite.Connection:
    """获取 aiosqlite 数据库连接（惰性初始化 + schema 迁移）。

    数据库路径由 PIXIU_DB_PATH 环境变量控制，默认 ./pixiu.db。
    """
    global _db
    if _db is None:
        _db = await aiosqlite.connect(settings.db_path)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
        await _db.execute("PRAGMA busy_timeout=5000")

        # 迁移骨架面向同步 sqlite3.Connection，此处用同步连接执行后关闭
        sync_conn = _sqlite3.connect(settings.db_path)
        try:
            apply_pending(sync_conn)
            sync_conn.commit()
        finally:
            sync_conn.close()

        _log.info("Database connected: %s", settings.db_path)
    return _db


async def get_ingestion_service(
    db: aiosqlite.Connection = Depends(get_db),
) -> IngestionService:
    return IngestionService(evidence_repo=SqliteEvidenceRepo(db))


async def get_evidence_repo(
    db: aiosqlite.Connection = Depends(get_db),
) -> SqliteEvidenceRepo:
    return SqliteEvidenceRepo(db)


async def get_ocr_service():
    """OCR 后端：PIXIU_OCR 控制 auto/kylin/portable，与 embedding 同构。"""
    return get_ocr(settings.ocr)


async def get_preference_service(
    db: aiosqlite.Connection = Depends(get_db),
) -> PreferenceService:
    return PreferenceService(pref_repo=SqlitePreferenceRepo(db))


async def get_preference_repo(
    db: aiosqlite.Connection = Depends(get_db),
) -> SqlitePreferenceRepo:
    return SqlitePreferenceRepo(db)


async def get_knowledge_service(
    db: aiosqlite.Connection = Depends(get_db),
) -> KnowledgeService:
    return KnowledgeService(
        knw_repo=SqliteKnowledgeRepo(db),
        entity_repo=SqliteEntityRepo(db),
        embedder=get_embedder(settings.embedding),
    )



async def get_knowledge_repo(
    db: aiosqlite.Connection = Depends(get_db),
) -> SqliteKnowledgeRepo:
    return SqliteKnowledgeRepo(db)


async def get_conflict_service(
    db: aiosqlite.Connection = Depends(get_db),
) -> ConflictService:
    return ConflictService(
        knw_repo=SqliteKnowledgeRepo(db),
        conflict_repo=SqliteConflictRepo(db),
    )


async def get_conflict_repo(
    db: aiosqlite.Connection = Depends(get_db),
) -> SqliteConflictRepo:
    return SqliteConflictRepo(db)


async def get_security_service(
    db: aiosqlite.Connection = Depends(get_db),
) -> SecurityService:
    return SecurityService(
        knw_repo=SqliteKnowledgeRepo(db),
        entity_repo=SqliteEntityRepo(db),
    )


async def get_retrieval_service(
    db: aiosqlite.Connection = Depends(get_db),
) -> RetrievalService:
    return RetrievalService(
        knw_repo=SqliteKnowledgeRepo(db),
        entity_repo=SqliteEntityRepo(db),
        evidence_repo=SqliteEvidenceRepo(db),
        embedder=get_embedder(settings.embedding),
    )


async def get_flow_service(
    db: aiosqlite.Connection = Depends(get_db),
    ingestion: IngestionService = Depends(get_ingestion_service),
    knowledge: KnowledgeService = Depends(get_knowledge_service),
) -> FlowService:
    """组装短/中期持久化与长期知识沉淀流水线。"""
    store = SqliteFlowStore(db)

    async def _promote_context(context):
        payload = dict(context.payload)
        source_type = str(payload.pop("source_type", "MANUAL_CONFIG"))
        raw = payload.pop("raw", payload)
        if not isinstance(raw, dict):
            raise ValueError("flow context raw payload must be an object")
        evidence = await ingestion.ingest(source_type, raw, context.scope)
        item = await knowledge.structure(evidence)
        return item.id

    return FlowService(
        store,
        _promote_context,
        knowledge_repo=SqliteKnowledgeRepo(db),
    )


async def get_sync_service(
    db: aiosqlite.Connection = Depends(get_db),
) -> SyncService:
    return SyncService(
        SqliteSyncStore(db),
        device_name=settings.sync_device_name,
        domain=settings.sync_domain,
        key_passphrase=settings.sync_key_passphrase,
        materializer=FoundationMaterializer(
            evidence_repo=SqliteEvidenceRepo(db),
            knowledge_repo=SqliteKnowledgeRepo(db),
            preference_repo=SqlitePreferenceRepo(db),
        ),
    )



async def get_optional_sync_service(
    db: aiosqlite.Connection = Depends(get_db),
) -> SyncService | None:
    try:
        return await get_sync_service(db)
    except ValueError:
        return None



async def start_sync_runtime() -> SyncRuntime | None:
    """Start LAN synchronization only after explicit opt-in configuration."""
    global _sync_runtime
    if not settings.sync_network_enabled:
        return None
    if _sync_runtime is None:
        db = await get_db()
        service = await get_sync_service(db)
        _sync_runtime = await create_sync_runtime(
            service, SqliteSyncStore(db), settings
        )
        await _sync_runtime.start()
        _log.info("Sync networking started on port %s", settings.sync_port)
    return _sync_runtime


async def stop_sync_runtime() -> None:
    global _sync_runtime
    if _sync_runtime is not None:
        await _sync_runtime.stop()
        _sync_runtime = None
        _log.info("Sync networking stopped")


async def get_dbus_handler(
    db: aiosqlite.Connection = Depends(get_db),
) -> PixiuMemoryHandler:
    """组装 D-Bus 业务 handler（复用与 HTTP 相同的 Service 实例注入）。"""
    ingestion = await get_ingestion_service(db)
    knowledge = await get_knowledge_service(db)
    preference = await get_preference_service(db)
    conflict = await get_conflict_service(db)
    security = await get_security_service(db)
    retrieval = await get_retrieval_service(db)
    sync = await get_optional_sync_service(db)
    return PixiuMemoryHandler(
        ingestion=ingestion,
        knowledge=knowledge,
        preference=preference,
        conflict=conflict,
        security=security,
        retrieval=retrieval,
        sync_status=sync.status if sync is not None else None,
    )
