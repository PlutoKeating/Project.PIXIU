"""PIXIU Foundation — 统一日志配置

提供两种 logger 获取方式：
  - get_logger(name)          普通 logger，request_id 显示 [-]
  - get_request_logger(name, request_id)  请求级 logger，注入 request_id

敏感信息过滤（SensitiveFilter）：
  - password, token, secret, api_key → ***
  - PRIVATE KEY 块 → [REDACTED PRIVATE KEY]
  - 连续 16 位数字（卡号）→ [REDACTED CARD]
"""

from __future__ import annotations

import logging
import re
import sys

from .config import settings

# ─── 敏感信息检测正则 ─────────────────────────────────────

_SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # password=xxx 或 "password": "xxx"
    (re.compile(r'(?i)(password["\s:=]+)(\S+)'), r"\1***"),
    # token=xxx 或 "token": "xxx"
    (re.compile(r'(?i)(token["\s:=]+)(\S+)'), r"\1***"),
    # secret=xxx 或 "secret": "xxx"
    (re.compile(r'(?i)(secret["\s:=]+)(\S+)'), r"\1***"),
    # api_key=xxx
    (re.compile(r'(?i)(api_key["\s:=]+)(\S+)'), r"\1***"),
    # -----BEGIN ... PRIVATE KEY----- 整块
    (re.compile(r"-----BEGIN\s+.*?PRIVATE\s+KEY-----[^-]*-----END\s+.*?PRIVATE\s+KEY-----", re.DOTALL),
     "[REDACTED PRIVATE KEY]"),
    # 连续 16 位数字（信用卡号）
    (re.compile(r"\b\d{16}\b"), "[REDACTED CARD]"),
]

# ─── 格式 ────────────────────────────────────────────────

_LOG_FORMAT = "%(asctime)s.%(msecs)03d | %(levelname)-7s | %(name)s | [%(request_id)s] | %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class SafeFormatter(logging.Formatter):
    """自定义 Formatter，确保 request_id 字段存在。"""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return super().format(record)


class SensitiveFilter(logging.Filter):
    """过滤敏感信息：password, token, secret, private key, card number。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in _SENSITIVE_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        return True


# ─── 模块级 Logger 缓存 ──────────────────────────────────

_loggers: dict[str, logging.Logger] = {}

_fmt = SafeFormatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
_sensitive_filter = SensitiveFilter()


def _ensure_root_configured(level: str | None = None) -> None:
    if _loggers:
        return  # 已配置
    root = logging.getLogger()
    root.setLevel(level or settings.log_level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_fmt)
    handler.addFilter(_sensitive_filter)
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """获取普通 Logger（request_id 显示 [-]）。

    首次调用时配置根 logger（级别由 PIXIU_LOG_LEVEL 控制，默认 INFO）。
    """
    cache_key = f"{name}__"
    if cache_key in _loggers:
        return _loggers[cache_key]

    _ensure_root_configured(level)
    logger = logging.getLogger(name)
    logger = logging.LoggerAdapter(logger, {"request_id": "-"})  # type: ignore[assignment]
    _loggers[cache_key] = logger  # type: ignore[assignment]
    return logger  # type: ignore[return-value]


def get_request_logger(name: str, request_id: str) -> logging.LoggerAdapter:
    """获取请求级 Logger，注入 request_id 用于链路追踪。

    Usage:
        log = get_request_logger(__name__, request_id)
        log.info("query submitted")
    """
    _ensure_root_configured()
    logger = logging.getLogger(name)
    return logging.LoggerAdapter(logger, {"request_id": request_id})
