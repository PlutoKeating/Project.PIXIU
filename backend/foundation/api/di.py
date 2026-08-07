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
from backend.engine.kylin import get_embedder
from backend.engine.preference import PreferenceService
from backend.engine.security import SecurityService

from ..core.config import settings
from ..core.logger import get_logger
from ..retrieval import RetrievalService
from ..storage.migrations import apply_pending
from ..storage.repository import (
    SqliteConflictRepo,
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
    SqlitePreferenceRepo,
)

_log = get_logger(__name__)

_db: aiosqlite.Connection | None = None


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
        embedder=get_embedder(),
    )


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
        embedder=get_embedder(),
    )
