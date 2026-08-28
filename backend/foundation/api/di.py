"""PIXIU Foundation — 依赖注入容器

本文件是模块 C api/ 层对引擎 Service 的唯一 import 点：
引擎 Service 与 foundation SQLite 仓储在此组装，供 http_app 路由注入。
"""

from __future__ import annotations

import asyncio
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
from ..monitor.config_store import MonitorConfigStore
from ..monitor.watcher import DirectoryWatcher
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
from .monitor_log import (
    MonitorLogStore,
    broadcast_capture_event,
)

_log = get_logger(__name__)

_db: aiosqlite.Connection | None = None
_sync_runtime: SyncRuntime | None = None
_monitor_config_store: MonitorConfigStore | None = None
_monitor_log_store: MonitorLogStore | None = None
_monitor_runtime: DirectoryWatcher | None = None
#: watcher 回调（watch 线程）把 capture_event 广播调度回的主事件循环；
#: 由 start_monitor_runtime（_lifespan，主循环）注册。
_main_loop: asyncio.AbstractEventLoop | None = None


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


# ─── 监视服务（批次② BE-3：配置/日志存储单例 + runtime 生命周期）──────

def get_monitor_config_store() -> MonitorConfigStore:
    """监视配置存储单例（惰性；db 路径取自 settings，测试 monkeypatch 后置 None）。"""
    global _monitor_config_store
    if _monitor_config_store is None:
        _monitor_config_store = MonitorConfigStore(db_path=settings.db_path)
    return _monitor_config_store


def get_monitor_log_store() -> MonitorLogStore:
    """monitor_log 活动日志存储单例（惰性；同上）。"""
    global _monitor_log_store
    if _monitor_log_store is None:
        _monitor_log_store = MonitorLogStore(db_path=settings.db_path)
    return _monitor_log_store


def _schedule_capture_broadcast(
    *,
    source: str,
    status: str,
    summary: str,
    evidence_id: str | None,
    knowledge_id: str | None,
    ts: int,
) -> None:
    """把 capture_event 广播调度回主事件循环（watcher 回调运行在 watch 线程）。

    WebSocket 连接绑定主循环，跨线程直发不安全；主循环未注册（测试直连）
    时静默跳过广播，日志已由调用方落库。
    """
    loop = _main_loop
    if loop is None or not loop.is_running():
        return

    def _run() -> None:
        try:
            asyncio.ensure_future(
                broadcast_capture_event(
                    source=source,
                    status=status,
                    summary=summary,
                    evidence_id=evidence_id,
                    knowledge_id=knowledge_id,
                    ts=ts,
                )
            )
        except Exception:
            _log.exception("capture_event broadcast scheduling failed")

    try:
        loop.call_soon_threadsafe(_run)
    except RuntimeError:
        _log.exception("monitor main loop unavailable, skip capture_event broadcast")


def _make_capture_callback(log_store: MonitorLogStore):
    """watcher on_capture 回调：短同步写 monitor_log + 调度广播回主循环。

    回调在 watch 线程的 asyncio 循环上执行（watcher._emit），必须快速返回：
    日志写为单行短连接 INSERT；广播经 call_soon_threadsafe 调度。
    """

    def _on_capture(
        *,
        source: str,
        status: str,
        summary: str,
        evidence_id: str | None = None,
        knowledge_id: str | None = None,
        ts: int | None = None,
    ) -> None:
        try:
            log_store.write_event(
                source=source,
                status=status,
                summary=summary,
                evidence_id=evidence_id,
                knowledge_id=knowledge_id,
                ts=ts,
            )
        except Exception:
            _log.exception("monitor_log write failed (source=%s)", source)
        try:
            _schedule_capture_broadcast(
                source=source,
                status=status,
                summary=summary,
                evidence_id=evidence_id,
                knowledge_id=knowledge_id,
                ts=ts,
            )
        except Exception:
            _log.exception("capture_event broadcast failed (source=%s)", source)

    return _on_capture


async def get_monitor_runtime() -> DirectoryWatcher:
    """监视运行时（懒创建、未 start）；端点不直接使用，由 _lifespan 启停。"""
    global _monitor_runtime
    if _monitor_runtime is None:
        from ..monitor.runtime import create_monitor_runtime

        store = get_monitor_config_store()
        log_store = get_monitor_log_store()
        _monitor_runtime = await create_monitor_runtime(
            store,
            callbacks=[_make_capture_callback(log_store)],
        )
        _log.info("Monitor runtime created")
    return _monitor_runtime


async def start_monitor_runtime() -> DirectoryWatcher | None:
    """_lifespan 启动：PIXIU_MONITOR_ENABLED 时创建并 start watcher。

    启动仅受环境总闸控制；config.enabled=false 时 watcher 照常运行、
    effective=false 不捕获（热生效由 store.subscribe 驱动）。
    """
    global _main_loop
    if not settings.monitor_enabled:
        return None
    _main_loop = asyncio.get_running_loop()
    watcher = await get_monitor_runtime()
    watcher.start()
    _log.info("Monitor runtime started")
    return watcher


async def stop_monitor_runtime() -> None:
    global _monitor_runtime, _main_loop
    if _monitor_runtime is not None:
        try:
            _monitor_runtime.stop()
        finally:
            _monitor_runtime = None
            _main_loop = None
        _log.info("Monitor runtime stopped")


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
