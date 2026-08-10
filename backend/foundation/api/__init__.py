"""PIXIU Foundation — API 网关

导出 FastAPI 应用实例、WebSocket 管理器与 D-Bus 服务。
"""

from .dbus_service import (
    BUS_NAME,
    OBJECT_PATH,
    PixiuDBusInterface,
    PixiuDBusService,
    PixiuError,
    PixiuMemoryHandler,
)
from .http_app import app
from .ws_manager import ws_manager

__all__ = [
    "BUS_NAME",
    "OBJECT_PATH",
    "PixiuDBusInterface",
    "PixiuDBusService",
    "PixiuError",
    "PixiuMemoryHandler",
    "app",
    "ws_manager",
]
