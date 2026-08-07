"""Tests for core/logger.py — structured logging with request_id and sensitive filtering."""

from __future__ import annotations

import io
import logging

import pytest

from backend.foundation.core.logger import (
    SensitiveFilter,
    get_logger,
    get_request_logger,
)


def _capture_log(name: str, request_id: str | None, msg: str) -> str:
    """创建一个独立 logger，捕获到 StringIO，返回输出文本。"""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | [%(request_id)s] | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    handler.addFilter(SensitiveFilter())

    logger = logging.getLogger(f"test_{name}")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    extra = {"request_id": request_id or "-"}
    logger.info(msg, extra=extra)

    for h in logger.handlers:
        h.flush()
    return stream.getvalue()


# ═══════════════════════════════════════════════════════
# Group 1: normal logger outputs correctly
# ═══════════════════════════════════════════════════════

def test_normal_logger_has_dash_request_id():
    """Normal logger outputs [-] as request_id."""
    log = get_logger("test.module")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        logging.Formatter(
            "%(levelname)s | [%(request_id)s] | %(message)s"
        )
    )
    # Attach to the underlying logger (get_logger returns LoggerAdapter)
    base = logging.getLogger("test.module")
    base.handlers.clear()
    base.addHandler(handler)
    base.setLevel(logging.DEBUG)

    log.info("hello world")

    output = stream.getvalue()
    assert "[-]" in output
    assert "hello world" in output


# ═══════════════════════════════════════════════════════
# Group 2: request logger outputs request_id
# ═══════════════════════════════════════════════════════

def test_request_logger_has_request_id():
    """Request logger outputs the given request_id."""
    output = _capture_log("req_test", "req_01KYSVDG0739T", "query submitted")
    assert "[req_01KYSVDG0739T]" in output
    assert "query submitted" in output


# ═══════════════════════════════════════════════════════
# Group 3: sensitive info filtering
# ═══════════════════════════════════════════════════════

def test_password_filtered():
    output = _capture_log("pwd", None, "password=abc123 and done")
    assert "password=***" in output
    assert "abc123" not in output


def test_password_json_filtered():
    output = _capture_log("pwd_json", None, 'user login with "password": "abc123"')
    assert '"password": "***' in output
    assert "abc123" not in output


def test_token_filtered():
    output = _capture_log("tok", None, "token=eyJhbGciOiJIUzI1NiJ9 and more")
    assert "token=***" in output
    assert "eyJhbGci" not in output


def test_secret_filtered():
    output = _capture_log("sec", None, "secret=my-secret-key-123")
    assert "secret=***" in output
    assert "my-secret-key-123" not in output


def test_api_key_filtered():
    output = _capture_log("key", None, "api_key=sk-abcdef123456")
    assert "api_key=***" in output
    assert "sk-abcdef123456" not in output


def test_private_key_block_filtered():
    output = _capture_log(
        "pk",
        None,
        "key material:\n-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----",
    )
    assert "[REDACTED PRIVATE KEY]" in output
    assert "MIIEpA" not in output


def test_card_number_filtered():
    output = _capture_log("card", None, "paid with 1234567890123456 today")
    assert "[REDACTED CARD]" in output
    assert "1234567890123456" not in output


def test_clean_message_passes_through():
    """Non-sensitive messages are unchanged."""
    output = _capture_log("clean", None, "user alice performed action view")
    assert "user alice performed action view" in output


# ═══════════════════════════════════════════════════════
# Group 4: SensitiveFilter units
# ═══════════════════════════════════════════════════════

def test_sensitive_filter_replaces_multiple():
    f = SensitiveFilter()
    record = logging.LogRecord("x", logging.INFO, "", 0, "password=xxx and token=yyy", (), None)
    f.filter(record)
    assert "password=***" in record.msg
    assert "token=***" in record.msg
    assert "xxx" not in record.msg
    assert "yyy" not in record.msg
