"""PIXIU Foundation — 依赖注入容器

本文件是模块 C api/ 层对引擎 Service 的唯一 import 点：
引擎 Service 与 foundation SQLite 仓储在此组装，供 http_app 路由注入。
"""

from __future__ import annotations

import asyncio
import sqlite3 as _sqlite3
import time

import aiosqlite
from fastapi import Depends

from backend.engine.conflict import ConflictService
from backend.engine.delivery import DeliveryDigestService, DeliveryInsightsService
from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.kylin import (
    KylinVectorStore,
    VectorEngineClient,
    get_embedder,
    get_ocr,
)
from backend.engine.preference import PreferenceService
from backend.engine.security import SecurityService

from ..agent_context import AgentContextService
from ..core.config import settings
from ..core.logger import get_logger
from ..core.vector_store import VectorStore
from .dbus_service import PixiuMemoryHandler
from ..flow import FlowService, SqliteFlowStore
from ..monitor.behavior import BehaviorCollector
from ..monitor.config_store import MonitorConfigStore
from ..monitor.watcher import DirectoryWatcher
from ..retrieval import RetrievalService
from ..storage.idempotency import AgentIngestReceiptStore
from ..storage.migrations import apply_pending
from ..storage.repository import (
    SqliteConflictRepo,
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
    SqlitePreferenceRepo,
)
from ..storage.vector_store import SqliteVectorStore
from ..storage.vector_id_map import SqliteVectorIdMap
from ..sync import Mainline, SqliteSyncStore, SyncService
from ..sync.discovery import MdnsDiscovery
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
_behavior_collector: BehaviorCollector | None = None
_delivery_service: DeliveryInsightsService | None = None
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


async def get_vector_store(
    db: aiosqlite.Connection = Depends(get_db),
) -> VectorStore:
    """Select the system vector engine or the explicit portable adapter."""
    if settings.vector_store == "portable":
        return SqliteVectorStore(db)
    try:
        client = VectorEngineClient(app_id=settings.vector_app_id)
    except Exception:
        if settings.vector_store == "kylin":
            raise
        _log.warning(
            "Kylin Vector Engine unavailable; using explicit portable fallback"
        )
        return SqliteVectorStore(db)
    return KylinVectorStore(
        client,
        SqliteVectorIdMap(db),
        collection=settings.vector_collection,
    )


async def get_evidence_repo(
    db: aiosqlite.Connection = Depends(get_db),
) -> SqliteEvidenceRepo:
    return SqliteEvidenceRepo(db)


async def get_agent_ingest_receipt_store(
    db: aiosqlite.Connection = Depends(get_db),
) -> AgentIngestReceiptStore:
    return AgentIngestReceiptStore(db)


async def get_ocr_service():
    """OCR 后端：PIXIU_OCR 控制 auto/kylin/portable，与 embedding 同构。"""
    return get_ocr(settings.ocr)


async def get_text_embedder():
    """Return the actual configured embedding runtime for services and evidence."""
    return get_embedder(settings.embedding)


async def get_runtime_settings():
    """Expose the active settings object through the dependency seam."""
    return settings


async def preflight_strict_capabilities() -> None:
    """Fail application startup when a strict SDK runtime cannot initialize."""
    if settings.embedding == "kylin":
        await get_text_embedder()
    if settings.vector_store == "kylin":
        db = await get_db()
        await get_vector_store(db)


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
        vector_store=await get_vector_store(db),
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
        vector_store=await get_vector_store(db),
    )


async def get_retrieval_service(
    db: aiosqlite.Connection = Depends(get_db),
) -> RetrievalService:
    return RetrievalService(
        knw_repo=SqliteKnowledgeRepo(db),
        entity_repo=SqliteEntityRepo(db),
        evidence_repo=SqliteEvidenceRepo(db),
        embedder=get_embedder(settings.embedding),
        vector_store=await get_vector_store(db),
    )


async def get_agent_context_service(
    db: aiosqlite.Connection = Depends(get_db),
    retrieval: RetrievalService = Depends(get_retrieval_service),
) -> AgentContextService:
    return AgentContextService(
        retrieval=retrieval,
        evidence_repo=SqliteEvidenceRepo(db),
        conflict_repo=SqliteConflictRepo(db),
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
    store = SqliteSyncStore(db)
    # SN-3 mainline：注入 ConflictService（arbitrate 在调用时才解析，
    # 无循环依赖）。同步分叉且判 MANUAL 的 op 转人工仲裁（source="sync"）。
    conflict_service = await get_conflict_service(db)
    return SyncService(
        store,
        device_name=settings.sync_device_name,
        domain=settings.sync_domain,
        key_passphrase=settings.sync_key_passphrase,
        materializer=FoundationMaterializer(
            evidence_repo=SqliteEvidenceRepo(db),
            knowledge_repo=SqliteKnowledgeRepo(db),
            preference_repo=SqlitePreferenceRepo(db),
        ),
        mainline=Mainline(store, conflict_service),
        # SN-4：KV 未写时 enabled 回 env 默认（di 注入 settings 值，
        # 使测试/生产各自的 settings 替身生效）。
        runtime_enabled_default=settings.sync_network_enabled,
    )



async def get_optional_sync_service(
    db: aiosqlite.Connection = Depends(get_db),
) -> SyncService | None:
    try:
        return await get_sync_service(db)
    except ValueError:
        return None



async def start_sync_runtime() -> SyncRuntime | None:
    """Start LAN synchronization per runtime settings (KV overrides env).

    SN-4 默认开启：enabled 以 KV（sync_runtime:enabled）覆盖 env 默认；装配失败
    （缺证书/口令/端口占用等）降级为 log warning 并返回 None，不阻塞 API 启动，
    后续 PUT /sync/settings enabled=true 可重试。
    """
    global _sync_runtime
    if _sync_runtime is not None:
        return _sync_runtime
    try:
        db = await get_db()
        service = await get_sync_service(db)
        runtime_settings = await service._runtime_settings()
        if not runtime_settings["enabled"]:
            return None
        runtime = await create_sync_runtime(
            service,
            SqliteSyncStore(db),
            settings,
            paused=runtime_settings["paused"],
        )
        await runtime.start()
    except Exception as exc:
        # exc_info=True：装配失败既可能是预期降级（缺证书/口令/端口占用），
        # 也可能是编程错误（AttributeError/TypeError）；统一带 traceback 便于诊断。
        _log.warning(
            "sync runtime not started (degraded): %s", exc, exc_info=True
        )
        return None
    _sync_runtime = runtime
    _log.info("Sync networking started on port %s", settings.sync_port)
    return _sync_runtime


async def apply_sync_runtime_settings(*, enabled: bool, paused: bool) -> None:
    """PUT /sync/settings 热生效：enabled 变更启停 runtime；paused 转发 runtime。"""
    global _sync_runtime
    if enabled:
        await start_sync_runtime()
    else:
        await stop_sync_runtime()
    runtime = _sync_runtime
    if runtime is not None:
        runtime.set_paused(paused)


async def get_sync_discovery() -> MdnsDiscovery:
    """返回共享的 mDNS 发现实例（随 sync runtime 启动注册）。

    runtime 未启动（KV sync_runtime:enabled 关闭、env 默认关闭或装配降级）时
    返回空实例：list_advertisements 不打开 socket，直接返回空列表。
    """
    runtime = _sync_runtime
    if runtime is None:
        return MdnsDiscovery()
    return runtime.discovery


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


def _reclaim_broadcast_task(task: asyncio.Future) -> None:
    """fire-and-forget 广播任务收尾：取回异常（防 unretrieved warning）并记录。"""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        _log.warning("capture_event broadcast task failed: %s", exc)


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
    时 debug 记录并跳过广播（日志已由调用方落库）。
    """
    loop = _main_loop
    if loop is None or not loop.is_running():
        _log.debug(
            "monitor main loop not registered/running, skip capture_event "
            "broadcast (source=%s)",
            source,
        )
        return

    def _run() -> None:
        try:
            task = asyncio.ensure_future(
                broadcast_capture_event(
                    source=source,
                    status=status,
                    summary=summary,
                    evidence_id=evidence_id,
                    knowledge_id=knowledge_id,
                    ts=ts,
                )
            )
            # 不保留外部引用（fire-and-forget）：done 回调取回并记录异常，
            # 避免 unretrieved task exception 警告或异常被静默吞掉。
            task.add_done_callback(_reclaim_broadcast_task)
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
        # 统一 ts：日志与广播共用同一时间戳，避免两者各自取 time.time() 差 1 秒
        if ts is None:
            ts = int(time.time())
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


# ─── 行为采集器（批次③ B3-1：随 monitor runtime 生命周期启停）────

async def get_behavior_collector() -> BehaviorCollector:
    """行为采集器单例（惰性装配，复用 /memory/write 同进程管线服务）。

    security 可选注入：提供时标题经既有 detector 判定，sensitivity>0 不落库
    （B3-1 规格比 ingest_bridge 更严格：直接丢弃，不写 evidence）。
    """
    global _behavior_collector
    if _behavior_collector is None:
        db = await get_db()
        _behavior_collector = BehaviorCollector(
            config_store=get_monitor_config_store(),
            ingestion=await get_ingestion_service(db),
            knowledge=await get_knowledge_service(db),
            security=await get_security_service(db),
        )
        _log.info("Behavior collector created")
    return _behavior_collector


async def start_behavior_collector() -> None:
    """_lifespan 启动：PIXIU_MONITOR_ENABLED 时启动行为采集轮询线程。

    装配失败（embedding/DB 等）降级为 log warning 并返回，不阻塞 API 启动
    （对齐 sync runtime 的降级先例）；config enabled && sources.behavior
    门控在采集器内部按轮询周期生效。
    """
    if not settings.monitor_enabled:
        return
    try:
        collector = await get_behavior_collector()
        collector.start()
        _log.info("Behavior collector started")
    except Exception as exc:
        _log.warning(
            "behavior collector not started (degraded): %s", exc, exc_info=True
        )


async def stop_behavior_collector() -> None:
    global _behavior_collector
    if _behavior_collector is not None:
        try:
            _behavior_collector.stop()
        finally:
            _behavior_collector = None
        _log.info("Behavior collector stopped")


# ─── 递送服务（批次④ B4-1：洞察流单例，复用 knowledge/conflict/evidence 仓储）────

async def get_delivery_service() -> DeliveryInsightsService:
    """洞察流服务单例（惰性装配）。

    质量分/敏感度需从关联 Evidence 解析（KnowledgeItem 不携带），
    故注入 evidence_repo；复用 get_db 的单例连接。
    """
    global _delivery_service
    if _delivery_service is None:
        db = await get_db()
        _delivery_service = DeliveryInsightsService(
            knowledge_repo=SqliteKnowledgeRepo(db),
            conflict_repo=SqliteConflictRepo(db),
            evidence_repo=SqliteEvidenceRepo(db),
        )
        _log.info("Delivery insights service created")
    return _delivery_service


def get_delivery_digest_service() -> DeliveryDigestService:
    """定时简报服务（B4-2）：monitor_log 按日聚合。

    MonitorLogStore 为同步短连接单例（get_monitor_log_store），服务层 async
    digest 内部以 asyncio.to_thread 包装同步查询；每次请求轻量组装新实例
    （仅持 store 引用，无跨请求状态，无需单例化）。
    """
    return DeliveryDigestService(monitor_log=get_monitor_log_store())


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
