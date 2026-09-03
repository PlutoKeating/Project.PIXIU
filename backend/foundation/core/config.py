"""PIXIU Foundation — 配置单例

从环境变量读取配置，提供默认值与类型校验。
变量名与 backend/.env.example 完全一致，本模块不 hardcode 个人路径。
"""

from __future__ import annotations

import ipaddress
import os
import re
import socket

_VALID_EMBEDDING = frozenset({"auto", "kylin", "portable"})
_VALID_OCR = frozenset({"auto", "kylin", "portable"})
_VALID_VECTOR_STORE = frozenset({"auto", "kylin", "portable"})
_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})
# 公开占位符/示例值：转公开 repo 后这些常量会暴露，禁止被用作 Ed25519
# 加密口令（否则攻击者可解密任意用户的同步私钥）。仅当显式设置了这些值
# 才拒绝；None（未设置）不受影响。
_PLACEHOLDER_PASSPHRASES = frozenset(
    {
        "change-me-before-production",
        "pixiu-local-sync-change-me-2026",
    }
)


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


def _env_identifier(key: str, default: str) -> str:
    value = _env_str(key, default)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,127}", value):
        raise ValueError(f"{key} must be a safe identifier")
    return value


def _is_placeholder_passphrase(value: str | None) -> bool:
    return (
        value is not None
        and value.strip().casefold() in _PLACEHOLDER_PASSPHRASES
    )


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
        self._embedding = _env_choice("PIXIU_EMBEDDING", "auto", _VALID_EMBEDDING)
        self._vector_store = _env_choice(
            "PIXIU_VECTOR_STORE", "auto", _VALID_VECTOR_STORE
        )
        self._vector_host = _env_lan_host("PIXIU_VECTOR_HOST", "127.0.0.1")
        self._vector_port = _env_port("PIXIU_VECTOR_PORT", 19530)
        self._vector_app_id = _env_identifier("PIXIU_VECTOR_APP_ID", "pixiu")
        self._vector_collection = _env_identifier(
            "PIXIU_VECTOR_COLLECTION", "pixiu_memory"
        )
        self._ocr = _env_choice("PIXIU_OCR", "auto", _VALID_OCR)
        self._log_level = _env_choice("PIXIU_LOG_LEVEL", "INFO", _VALID_LOG_LEVELS)
        self._data_dir = _env_str("PIXIU_DATA_DIR", "./data")
        self._sync_device_name = _env_str(
            "PIXIU_SYNC_DEVICE_NAME", socket.gethostname()
        )
        self._sync_domain = _env_shared_scope("PIXIU_SYNC_DOMAIN", "shared:home")
        self._sync_key_passphrase = os.getenv("PIXIU_SYNC_KEY_PASSPHRASE")
        # 同步服务装配时由 sync_key_passphrase 属性拒绝公开占位符。Settings
        # 构造本身保持可用，使无同步配置或升级迁移失败时核心 API 仍可降级启动。
        # SN-4 默认开启：运行时开关（PUT /sync/settings）以 KV 覆盖 env 默认。
        self._sync_network_enabled = _env_bool("PIXIU_SYNC_NETWORK_ENABLED", True)
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
        # 监视服务环境总闸（代码默认关，产品默认开由打包 pixiu.env 置 1，
        # 对齐 PIXIU_SYNC_NETWORK_ENABLED 先例；config.enabled 独立门控捕获）。
        self._monitor_enabled = _env_bool("PIXIU_MONITOR_ENABLED")
        # SN-4 默认开启：advertise 地址与 TLS 证书均允许缺省，避免无配置机器
        # 启动即崩溃。空 advertise 由 runtime 层自动取本机 LAN IP（回退
        # 127.0.0.1 告警）；缺证书由 di 层降级（log warning，不阻塞 API）。
        # TLS 文件路径的要求保留在 sync_certfile/sync_keyfile/sync_cafile
        # 属性级校验，于 runtime 装配期触发。

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
    def vector_store(self) -> str:
        return self._vector_store

    @property
    def vector_host(self) -> str:
        return self._vector_host

    @property
    def vector_port(self) -> int:
        return self._vector_port

    @property
    def vector_app_id(self) -> str:
        return self._vector_app_id

    @property
    def vector_collection(self) -> str:
        return self._vector_collection

    @property
    def ocr(self) -> str:
        return self._ocr

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
        # 防御性复查：公开占位符/示例值禁止用作加密口令。
        if _is_placeholder_passphrase(self._sync_key_passphrase):
            raise ValueError(
                "PIXIU_SYNC_KEY_PASSPHRASE must be changed from the public placeholder"
            )
        if self._sync_key_passphrase is None or len(self._sync_key_passphrase) < 16:
            raise ValueError(
                "PIXIU_SYNC_KEY_PASSPHRASE must contain at least 16 characters"
            )
        return self._sync_key_passphrase

    @property
    def sync_network_enabled(self) -> bool:
        return self._sync_network_enabled

    @property
    def monitor_enabled(self) -> bool:
        return self._monitor_enabled

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
