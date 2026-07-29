"""PIXIU Foundation — 统一日志配置"""

from __future__ import annotations

import logging
import sys

_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """获取或创建命名 Logger，输出到 stdout。

    首次调用时配置根 logger（按环境变量 PIXIU_LOG_LEVEL 设置级别，
    默认 INFO），后续调用复用已注册的 logger。
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)

    if not _loggers:
        root = logging.getLogger()
        root.setLevel(level or "INFO")
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        root.handlers.clear()
        root.addHandler(handler)

    _loggers[name] = logger
    return logger
