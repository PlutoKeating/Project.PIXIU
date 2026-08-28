"""PIXIU Foundation — monitor 运行时装配（最小可用路径，BE-2）

watcher / ingest_bridge 不是请求作用域组件，无法靠 FastAPI Depends 注入；
本模块提供 ``create_monitor_runtime`` 工厂：复用 foundation/api/di 的
Service 组装（同进程直调，不经过 HTTP），产出可直接 start() 的
DirectoryWatcher。

di.py 的 ``_lifespan`` 正式接线（start/stop 挂到 http_app 生命周期、
按 PIXIU_MONITOR_ENABLED 启停）由 BE-3 完成；本任务只保证「最小可用
装配路径」+ 供集成测试直连。
"""

from __future__ import annotations

from typing import Any, Callable

from ..core.logger import get_logger
from .ingest_bridge import IngestBridge
from .watcher import DirectoryWatcher

log = get_logger(__name__)


async def create_monitor_runtime(
    config_store: Any,
    *,
    db: Any | None = None,
    ocr: Any | None = None,
    scope: str = "user:local",
    debounce_ms: float = 500,
    callbacks: list[Callable[..., Any]] | None = None,
) -> DirectoryWatcher:
    """组装 DirectoryWatcher + IngestBridge（未 start）。

    依赖默认从 foundation/api/di 的 Service 组装获取（同一进程直调既有
    IngestionService / KnowledgeService / SecurityService / OCR adapter）；
    测试可显式注入 db / ocr。

    参数:
        config_store: MonitorConfigStore 实例（配置来源 + 热生效订阅）。
        db: 显式 aiosqlite 连接（缺省用 di.get_db 单例）。
        ocr: 显式 OCR 适配器（缺省用 di 的 get_ocr_service）。
        scope: 捕获落库 scope，默认本机 user:local（敏感条目仅落本机域）。
        debounce_ms: 防抖窗口毫秒。
        callbacks: 初始 on_capture 回调列表。
    """
    from backend.foundation.api.di import (  # 延迟导入，避免 monitor 包初始化拉重依赖
        get_db,
        get_ingestion_service,
        get_knowledge_service,
        get_ocr_service,
        get_security_service,
    )

    conn = db if db is not None else await get_db()
    ingestion = await get_ingestion_service(conn)
    knowledge = await get_knowledge_service(conn)
    security = await get_security_service(conn)
    ocr_adapter = ocr if ocr is not None else await get_ocr_service()

    bridge = IngestBridge(
        ingestion,
        knowledge,
        security=security,
        ocr=ocr_adapter,
        scope=scope,
    )
    watcher = DirectoryWatcher(
        config_store, bridge, debounce_ms=debounce_ms, callbacks=callbacks
    )
    log.info("monitor runtime created (scope=%s)", scope)
    return watcher


__all__ = ["create_monitor_runtime"]