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


def test_default_embedding_is_kylin():
    """Default PIXIU_EMBEDDING is 'kylin'（生产仅支持真实麒麟 SDK）。"""
    with mock.patch.dict(os.environ, {}, clear=True):
        s = Settings()
        assert s.embedding == "kylin"


def test_default_db_path():
    """Default PIXIU_DB_PATH is './pixiu.db'."""
    with mock.patch.dict(os.environ, {}, clear=True):
        s = Settings()
        assert s.db_path == "./pixiu.db"


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
