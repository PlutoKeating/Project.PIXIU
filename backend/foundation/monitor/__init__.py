"""PIXIU Foundation — 监视模块（批次② 目录监视闭环）

BE-1: MonitorConfigStore 配置存储与热生效（持久化 + 校验 + 订阅）。
BE-2: DirectoryWatcher 目录监视采集器 + IngestBridge 入库桥接
      （本任务；API 端点 BE-3 后续在此包扩展）。
"""

from .config_store import (
    DEFAULT_MONITOR_CONFIG,
    SOURCE_WHITELIST,
    InvalidMonitorConfig,
    MonitorConfigStore,
)
from .ingest_bridge import (
    CaptureResult,
    IMAGE_SUFFIXES,
    STATUS_IGNORED,
    STATUS_INGESTED,
    STATUS_SENSITIVE_QUARANTINED,
    TEXT_SUFFIXES,
    IngestBridge,
)
from .watcher import DirectoryWatcher, _is_ignored

__all__ = [
    "CaptureResult",
    "IMAGE_SUFFIXES",
    "IngestBridge",
    "InvalidMonitorConfig",
    "MonitorConfigStore",
    "SOURCE_WHITELIST",
    "STATUS_IGNORED",
    "STATUS_INGESTED",
    "STATUS_SENSITIVE_QUARANTINED",
    "TEXT_SUFFIXES",
    "DEFAULT_MONITOR_CONFIG",
    "DirectoryWatcher",
    "_is_ignored",
]
