"""PIXIU Foundation — API 网关

导出 FastAPI 应用实例和 WebSocket 管理器。
"""

from .http_app import app
from .ws_manager import ws_manager

__all__ = ["app", "ws_manager"]
