"""Tests for core/config.py — Settings singleton."""

from __future__ import annotations

import os
from unittest import mock

import pytest

from backend.foundation.core.config import Settings, _env_choice, _env_port, _env_str


# ─── Default values ────────────────────────────────────────

def test_default_port():
    """Default PIXIU_API_PORT is 8765 when env var is not set."""
    with mock.patch.dict(os.environ, {}, clear=True):
        s = Settings()
        assert s.api_port == 8765


def test_default_embedding_is_auto():
    """Default prefers Kylin SDK and permits portable Debian fallback."""
    with mock.patch.dict(os.environ, {}, clear=True):
        s = Settings()
        assert s.embedding == "auto"


def test_default_db_path():
    """Default PIXIU_DB_PATH is './pixiu.db'."""
    with mock.patch.dict(os.environ, {}, clear=True):
        s = Settings()
        assert s.db_path == "./pixiu.db"


def test_default_sync_domain_and_device_name():
    with mock.patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        assert settings.sync_domain == "shared:home"
        assert settings.sync_device_name


def test_sync_passphrase_is_required_only_when_sync_is_used():
    with mock.patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        with pytest.raises(ValueError, match="PIXIU_SYNC_KEY_PASSPHRASE"):
            _ = settings.sync_key_passphrase


def test_sync_configuration_from_environment():
    with mock.patch.dict(
        os.environ,
        {
            "PIXIU_SYNC_DEVICE_NAME": "客厅一体机",
            "PIXIU_SYNC_DOMAIN": "shared:family",
            "PIXIU_SYNC_KEY_PASSPHRASE": "a-secure-test-passphrase",
        },
        clear=True,
    ):
        settings = Settings()
        assert settings.sync_device_name == "客厅一体机"
        assert settings.sync_domain == "shared:family"
        assert settings.sync_key_passphrase == "a-secure-test-passphrase"


def test_sync_domain_rejects_private_scope():
    with mock.patch.dict(os.environ, {"PIXIU_SYNC_DOMAIN": "user:alice"}):
        with pytest.raises(ValueError, match="PIXIU_SYNC_DOMAIN"):
            Settings()


def test_default_sync_domain_and_device_name():
    with mock.patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        assert settings.sync_domain == "shared:home"
        assert settings.sync_device_name


def test_sync_passphrase_is_required_only_when_sync_is_used():
    with mock.patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        with pytest.raises(ValueError, match="PIXIU_SYNC_KEY_PASSPHRASE"):
            _ = settings.sync_key_passphrase


def test_sync_configuration_from_environment():
    with mock.patch.dict(
        os.environ,
        {
            "PIXIU_SYNC_DEVICE_NAME": "客厅一体机",
            "PIXIU_SYNC_DOMAIN": "shared:family",
            "PIXIU_SYNC_KEY_PASSPHRASE": "a-secure-test-passphrase",
        },
        clear=True,
    ):
        settings = Settings()
        assert settings.sync_device_name == "客厅一体机"
        assert settings.sync_domain == "shared:family"
        assert settings.sync_key_passphrase == "a-secure-test-passphrase"


def test_sync_domain_rejects_private_scope():
    with mock.patch.dict(os.environ, {"PIXIU_SYNC_DOMAIN": "user:alice"}):
        with pytest.raises(ValueError, match="PIXIU_SYNC_DOMAIN"):
            Settings()


# ─── Env var reading ─────────────────────────────────────

def test_embedding_mock_rejected():
    """PIXIU_EMBEDDING=mock 已废弃，必须拒绝（无 mock 降级）。"""
    with mock.patch.dict(os.environ, {"PIXIU_EMBEDDING": "mock"}):
        with pytest.raises(ValueError, match="PIXIU_EMBEDDING"):
            Settings()


def test_embedding_kylin():
    """PIXIU_EMBEDDING=kylin should be read correctly."""
    with mock.patch.dict(os.environ, {"PIXIU_EMBEDDING": "kylin"}):
        s = Settings()
        assert s.embedding == "kylin"


def test_embedding_portable():
    """PIXIU_EMBEDDING=portable forces the Debian-compatible implementation."""
    with mock.patch.dict(os.environ, {"PIXIU_EMBEDDING": "portable"}):
        s = Settings()
        assert s.embedding == "portable"


# ─── Invalid values are rejected ─────────────────────────

def test_invalid_embedding_rejected():
    """PIXIU_EMBEDDING=openai should raise ValueError."""
    with mock.patch.dict(os.environ, {"PIXIU_EMBEDDING": "openai"}):
        with pytest.raises(ValueError, match="PIXIU_EMBEDDING"):
            Settings()


def test_invalid_port_zero():
    """PIXIU_API_PORT=0 should raise ValueError."""
    with mock.patch.dict(os.environ, {"PIXIU_API_PORT": "0"}):
        with pytest.raises(ValueError, match="PIXIU_API_PORT"):
            Settings()


def test_invalid_port_too_high():
    """PIXIU_API_PORT=70000 should raise ValueError."""
    with mock.patch.dict(os.environ, {"PIXIU_API_PORT": "70000"}):
        with pytest.raises(ValueError, match="PIXIU_API_PORT"):
            Settings()


def test_invalid_port_not_int():
    """PIXIU_API_PORT=abc should raise ValueError."""
    with mock.patch.dict(os.environ, {"PIXIU_API_PORT": "abc"}):
        with pytest.raises(ValueError, match="PIXIU_API_PORT"):
            Settings()


def test_port_boundary_low():
    """PIXIU_API_PORT=1 should be accepted."""
    with mock.patch.dict(os.environ, {"PIXIU_API_PORT": "1"}):
        s = Settings()
        assert s.api_port == 1


def test_port_boundary_high():
    """PIXIU_API_PORT=65535 should be accepted."""
    with mock.patch.dict(os.environ, {"PIXIU_API_PORT": "65535"}):
        s = Settings()
        assert s.api_port == 65535


# ─── Path customization ──────────────────────────────────

def test_db_path_custom():
    """PIXIU_DB_PATH=/tmp/test.db should be read correctly."""
    with mock.patch.dict(os.environ, {"PIXIU_DB_PATH": "/tmp/test.db"}):
        s = Settings()
        assert s.db_path == "/tmp/test.db"


def test_empty_db_path_rejected():
    """PIXIU_DB_PATH='' should raise ValueError."""
    with mock.patch.dict(os.environ, {"PIXIU_DB_PATH": ""}):
        with pytest.raises(ValueError, match="PIXIU_DB_PATH"):
            Settings()


# ─── Log level ────────────────────────────────────────────

def test_log_level_default():
    """Default PIXIU_LOG_LEVEL is INFO."""
    with mock.patch.dict(os.environ, {}, clear=True):
        s = Settings()
        assert s.log_level == "INFO"


def test_log_level_custom():
    """PIXIU_LOG_LEVEL=DEBUG should be accepted."""
    with mock.patch.dict(os.environ, {"PIXIU_LOG_LEVEL": "DEBUG"}):
        s = Settings()
        assert s.log_level == "DEBUG"


def test_invalid_log_level_rejected():
    """PIXIU_LOG_LEVEL=TRACE should raise ValueError."""
    with mock.patch.dict(os.environ, {"PIXIU_LOG_LEVEL": "TRACE"}):
        with pytest.raises(ValueError, match="PIXIU_LOG_LEVEL"):
            Settings()


# ─── Unit-level helpers ───────────────────────────────────

def test_env_str_honors_env():
    with mock.patch.dict(os.environ, {"FOO": "bar"}):
        assert _env_str("FOO", "default") == "bar"


def test_env_port_from_env():
    with mock.patch.dict(os.environ, {"FOO": "8080"}):
        assert _env_port("FOO", 3000) == 8080


def test_env_port_default():
    with mock.patch.dict(os.environ, {}, clear=True):
        assert _env_port("FOO", 3000) == 3000


def test_env_choice_from_env():
    with mock.patch.dict(os.environ, {"FOO": "opt"}):
        assert _env_choice("FOO", "default", frozenset({"opt", "alt"})) == "opt"


def test_env_choice_invalid():
    with mock.patch.dict(os.environ, {"FOO": "bad"}):
        with pytest.raises(ValueError, match="FOO"):
            _env_choice("FOO", "default", frozenset({"opt", "alt"}))


def test_sync_network_is_enabled_by_default():
    with mock.patch.dict(os.environ, {}, clear=True):
        configured = Settings()
        assert configured.sync_network_enabled is True
        assert configured.sync_advertise_addresses == ()


def test_sync_network_rejects_invalid_boolean():
    with mock.patch.dict(
        os.environ, {"PIXIU_SYNC_NETWORK_ENABLED": "sometimes"}, clear=True
    ):
        with pytest.raises(ValueError, match="boolean"):
            Settings()


def test_sync_network_enabled_allows_missing_advertise_and_tls():
    # SN-4 默认开启：advertise 地址与 TLS 证书均允许缺省（runtime 装配期
    # 自动取本机 LAN IP / di 层降级），无配置机器不得在启动期崩溃。
    base = {
        "PIXIU_SYNC_NETWORK_ENABLED": "true",
        "PIXIU_SYNC_KEY_PASSPHRASE": "phase3-config-test-passphrase",
    }
    with mock.patch.dict(os.environ, base, clear=True):
        configured = Settings()
    assert configured.sync_network_enabled is True
    assert configured.sync_advertise_addresses == ()
    # TLS 文件路径仍由属性级校验要求（runtime 装配期触发，di 层降级处理）
    with pytest.raises(ValueError, match="PIXIU_SYNC_CERTFILE"):
        configured.sync_certfile


def test_sync_network_explicit_configuration():
    values = {
        "PIXIU_SYNC_NETWORK_ENABLED": "yes",
        "PIXIU_SYNC_KEY_PASSPHRASE": "phase3-config-test-passphrase",
        "PIXIU_SYNC_ADVERTISE_ADDRESSES": "192.168.1.20, 127.0.0.1",
        "PIXIU_SYNC_BIND_HOST": "192.168.1.20",
        "PIXIU_SYNC_PORT": "9876",
        "PIXIU_SYNC_SERVER_NAME": "study.pixiu.local",
        "PIXIU_SYNC_CERTFILE": "device.crt",
        "PIXIU_SYNC_KEYFILE": "device.key",
        "PIXIU_SYNC_CAFILE": "peers-ca.crt",
    }
    with mock.patch.dict(os.environ, values, clear=True):
        configured = Settings()
        assert configured.sync_network_enabled is True
        assert configured.sync_port == 9876
        assert configured.sync_advertise_addresses == (
            "192.168.1.20",
            "127.0.0.1",
        )
        assert configured.sync_certfile == "device.crt"
        assert configured.sync_keyfile == "device.key"
        assert configured.sync_cafile == "peers-ca.crt"

def test_sync_network_rejects_wildcard_or_public_bind_host():
    base = {
        "PIXIU_SYNC_NETWORK_ENABLED": "true",
        "PIXIU_SYNC_KEY_PASSPHRASE": "phase3-config-test-passphrase",
        "PIXIU_SYNC_ADVERTISE_ADDRESSES": "192.168.1.20",
        "PIXIU_SYNC_CERTFILE": "device.crt",
        "PIXIU_SYNC_KEYFILE": "device.key",
        "PIXIU_SYNC_CAFILE": "peers-ca.crt",
    }
    for host in ("0.0.0.0", "8.8.8.8"):
        with mock.patch.dict(
            os.environ, {**base, "PIXIU_SYNC_BIND_HOST": host}, clear=True
        ):
            with pytest.raises(ValueError, match="BIND_HOST"):
                Settings()
