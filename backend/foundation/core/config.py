"""PIXIU Foundation — 配置单例

从环境变量读取配置，提供默认值与类型校验。
变量名与 backend/.env.example 完全一致，本模块不 hardcode 个人路径。
"""

from __future__ import annotations

import ipaddress
import os
import socket

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


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key, str(default)).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{key} must be a boolean, got '{raw}'")



def _env_lan_host(key: str, default: str) -> str:
    raw = _env_str(key, default)
    try:
        address = ipaddress.ip_address(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an IP address") from exc
    if (
        address.is_unspecified
        or address.is_multicast
        or not (address.is_private or address.is_link_local or address.is_loopback)
    ):
        raise ValueError(f"{key} must be a specific LAN or loopback address")
    return str(address)

def _env_choice(key: str, default: str, valid: frozenset[str]) -> str:
    val = os.getenv(key, default)
    if val not in valid:
        raise ValueError(f"{key} must be one of {sorted(valid)}, got '{val}'")
    return val


def _env_shared_scope(key: str, default: str) -> str:
    value = _env_str(key, default)
    if not value.startswith("shared:") or len(value) == len("shared:"):
        raise ValueError(f"{key} must use shared:<domain> format")
    return value


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
        self._sync_device_name = _env_str(
            "PIXIU_SYNC_DEVICE_NAME", socket.gethostname()
        )
        self._sync_domain = _env_shared_scope("PIXIU_SYNC_DOMAIN", "shared:home")
        self._sync_key_passphrase = os.getenv("PIXIU_SYNC_KEY_PASSPHRASE")
        self._sync_network_enabled = _env_bool("PIXIU_SYNC_NETWORK_ENABLED")
        self._sync_bind_host = _env_lan_host("PIXIU_SYNC_BIND_HOST", "127.0.0.1")
        self._sync_port = _env_port("PIXIU_SYNC_PORT", 8766)
        self._sync_server_name = _env_str(
            "PIXIU_SYNC_SERVER_NAME", socket.gethostname()
        )
        self._sync_advertise_addresses = tuple(
            value.strip()
            for value in os.getenv("PIXIU_SYNC_ADVERTISE_ADDRESSES", "").split(",")
            if value.strip()
        )
        self._sync_certfile = os.getenv("PIXIU_SYNC_CERTFILE")
        self._sync_keyfile = os.getenv("PIXIU_SYNC_KEYFILE")
        self._sync_cafile = os.getenv("PIXIU_SYNC_CAFILE")
        self._sync_tls_key_password = os.getenv("PIXIU_SYNC_TLS_KEY_PASSWORD")
        if self._sync_network_enabled:
            if not self._sync_advertise_addresses:
                raise ValueError(
                    "PIXIU_SYNC_ADVERTISE_ADDRESSES is required when sync networking is enabled"
                )
            for key, value in self._sync_tls_values().items():
                if not value:
                    raise ValueError(f"{key} is required when sync networking is enabled")

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

    @property
    def sync_device_name(self) -> str:
        return self._sync_device_name

    @property
    def sync_domain(self) -> str:
        return self._sync_domain

    @property
    def sync_key_passphrase(self) -> str:
        if self._sync_key_passphrase is None or len(self._sync_key_passphrase) < 16:
            raise ValueError(
                "PIXIU_SYNC_KEY_PASSPHRASE must contain at least 16 characters"
            )
        return self._sync_key_passphrase

    @property
    def sync_network_enabled(self) -> bool:
        return self._sync_network_enabled

    @property
    def sync_bind_host(self) -> str:
        return self._sync_bind_host

    @property
    def sync_port(self) -> int:
        return self._sync_port

    @property
    def sync_server_name(self) -> str:
        return self._sync_server_name

    @property
    def sync_advertise_addresses(self) -> tuple[str, ...]:
        return self._sync_advertise_addresses

    def _sync_tls_values(self) -> dict[str, str | None]:
        return {
            "PIXIU_SYNC_CERTFILE": self._sync_certfile,
            "PIXIU_SYNC_KEYFILE": self._sync_keyfile,
            "PIXIU_SYNC_CAFILE": self._sync_cafile,
        }

    @property
    def sync_certfile(self) -> str:
        return self._required_sync_tls_value("PIXIU_SYNC_CERTFILE")

    @property
    def sync_keyfile(self) -> str:
        return self._required_sync_tls_value("PIXIU_SYNC_KEYFILE")

    @property
    def sync_cafile(self) -> str:
        return self._required_sync_tls_value("PIXIU_SYNC_CAFILE")

    @property
    def sync_tls_key_password(self) -> str | None:
        return self._sync_tls_key_password

    def _required_sync_tls_value(self, key: str) -> str:
        value = self._sync_tls_values()[key]
        if not value:
            raise ValueError(f"{key} is required for sync networking")
        return value


# ─── 模块级单例 ──────────────────────────────────────────

settings = Settings()
