"""PIXIU Foundation — 配置单例

从环境变量读取配置，提供默认值与类型校验。
变量名与 backend/.env.example 完全一致，本模块不 hardcode 个人路径。
"""

from __future__ import annotations

import os

_VALID_EMBEDDING = frozenset({"kylin"})
_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})


# ─── 内部辅助函数 ────────────────────────────────────────

def _env_str(key: str, default: str) -> str:
    val = os.getenv(key, default)
    if not val:
        raise ValueError(f"{key} must not be empty")
    return val


def _env_port(key: str, default: int) -> int:
    raw = os.getenv(key, str(default))
    try:
        port = int(raw)
    except ValueError:
        raise ValueError(f"{key} must be an integer, got '{raw}'") from None
    if port < 1 or port > 65535:
        raise ValueError(f"{key} must be 1-65535, got {port}")
    return port


def _env_choice(key: str, default: str, valid: frozenset[str]) -> str:
    val = os.getenv(key, default)
    if val not in valid:
        raise ValueError(f"{key} must be one of {sorted(valid)}, got '{val}'")
    return val


# ─── Settings ────────────────────────────────────────────

class Settings:
    """PIXIU 全局配置（环境变量 → 校验 → 属性）。

    使用方式（模块级单例）：
        from backend.foundation.core.config import settings
        db = aiosqlite.connect(settings.db_path)
    """

    def __init__(self):
        self._db_path = _env_str("PIXIU_DB_PATH", "./pixiu.db")
        self._api_host = _env_str("PIXIU_API_HOST", "127.0.0.1")
        self._api_port = _env_port("PIXIU_API_PORT", 8765)
        self._embedding = _env_choice("PIXIU_EMBEDDING", "kylin", _VALID_EMBEDDING)
        self._log_level = _env_choice("PIXIU_LOG_LEVEL", "INFO", _VALID_LOG_LEVELS)
        self._data_dir = _env_str("PIXIU_DATA_DIR", "./data")

    @property
    def db_path(self) -> str:
        return self._db_path

    @property
    def api_host(self) -> str:
        return self._api_host

    @property
    def api_port(self) -> int:
        return self._api_port

    @property
    def embedding(self) -> str:
        return self._embedding

    @property
    def log_level(self) -> str:
        return self._log_level

    @property
    def data_dir(self) -> str:
        return self._data_dir


# ─── 模块级单例 ──────────────────────────────────────────

settings = Settings()
