"""PIXIU Foundation — 监视配置存储（MonitorConfigStore）

批次②「目录监视闭环」的配置地基：持久化 + 校验 + 热生效订阅。
只做配置存储本身（get/put/subscribe），不做目录监视、OCR、API 端点
（分别属于 BE-2 / BE-3）。

存储形态：SQLite KV（storage.schema.MONITOR_CONFIG_DDL 表）+ JSON 序列化，
单行 key="main" 保存整份配置。每次操作使用短连接，天然线程安全
（BE-2 的 watchdog 工作线程可直接同步调用 get()）。
"""

from __future__ import annotations

import inspect
import json
import os
import sqlite3
import time
from typing import Any, Callable

from ..core.config import settings
from ..core.logger import get_logger
from ..storage.schema import MONITOR_CONFIG_DDL

log = get_logger(__name__)

#: sources 白名单（MonitorConfig 契约中的四个采集源键）。
SOURCE_WHITELIST = ("directory", "clipboard", "behavior", "screenshot")

#: 默认配置：总闸关、全源关、无监视目录。
DEFAULT_MONITOR_CONFIG: dict[str, Any] = {
    "enabled": False,
    "sources": {name: False for name in SOURCE_WHITELIST},
    "directories": [],
}

#: monitor_config 表内保存配置的单行 key。
_MONITOR_CONFIG_KEY = "main"


class InvalidMonitorConfig(ValueError):
    """监视配置非法：白名单外 source、非 bool enabled、相对目录等。"""


def _normalize(config: dict[str, Any]) -> dict[str, Any]:
    """校验并归一化 MonitorConfig，非法时抛 InvalidMonitorConfig。

    - enabled 必须是 bool（缺省 False）；
    - sources 只接受白名单键、值必须是 bool（缺省全 False）；
    - directories 丢弃空串/纯空白、按原序去重、拒绝相对路径（缺省 []）。
    未知顶层键静默忽略（归一化到契约三键形状）。
    """
    if not isinstance(config, dict):
        raise InvalidMonitorConfig("monitor config must be a dict")

    enabled = config.get("enabled", False)
    if not isinstance(enabled, bool):
        raise InvalidMonitorConfig(
            f"enabled must be a bool, got {type(enabled).__name__}"
        )

    raw_sources = config.get("sources") or {}
    if not isinstance(raw_sources, dict):
        raise InvalidMonitorConfig("sources must be a dict")
    unknown = sorted(set(raw_sources) - set(SOURCE_WHITELIST))
    if unknown:
        raise InvalidMonitorConfig(
            f"unknown source(s): {', '.join(unknown)}; allowed: "
            f"{', '.join(SOURCE_WHITELIST)}"
        )
    sources: dict[str, bool] = {}
    for name in SOURCE_WHITELIST:
        value = raw_sources.get(name, False)
        if not isinstance(value, bool):
            raise InvalidMonitorConfig(
                f"sources.{name} must be a bool, got {type(value).__name__}"
            )
        sources[name] = value

    raw_directories = config.get("directories") or []
    if not isinstance(raw_directories, list):
        raise InvalidMonitorConfig("directories must be a list")
    directories: list[str] = []
    seen: set[str] = set()
    for entry in raw_directories:
        if not isinstance(entry, str):
            raise InvalidMonitorConfig(
                f"directory entries must be strings, got {type(entry).__name__}"
            )
        if not entry.strip():
            continue  # 丢弃空串/纯空白
        if entry in seen:
            continue  # 按原序去重
        if not os.path.isabs(entry):
            raise InvalidMonitorConfig(
                f"directories must be absolute paths, got '{entry}'"
            )
        seen.add(entry)
        directories.append(entry)

    return {
        "enabled": enabled,
        "sources": sources,
        "directories": directories,
    }


class MonitorConfigStore:
    """监视配置存储：get / put / subscribe 三能力 + 校验 + SQLite 持久化。

    用法：
        store = MonitorConfigStore()          # 默认 PIXIU_DB_PATH
        store = MonitorConfigStore("/x.db")   # 显式 db 路径（测试用 tmp_path）
        cfg = store.get()
        new_cfg = await store.put({...})      # 校验通过才持久化并触发回调
        store.subscribe(on_change)            # 热生效回调（同步/异步均可）
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or settings.db_path
        self._callbacks: list[Callable[[dict], Any]] = []
        # 幂等建表 + 启用 WAL（对齐 storage.create_connection 风格）
        with self._open() as conn:
            conn.execute("PRAGMA journal_mode=WAL")

    # ─── 内部：短连接（线程安全） ─────────────────────────

    def _open(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(MONITOR_CONFIG_DDL)
        conn.commit()
        return conn

    # ─── 读取 ─────────────────────────────────────────────

    def get(self) -> dict:
        """读取当前配置；未写入过返回 DEFAULT_MONITOR_CONFIG。"""
        with self._open() as conn:
            row = conn.execute(
                "SELECT value FROM monitor_config WHERE key = ?",
                (_MONITOR_CONFIG_KEY,),
            ).fetchone()
        if row is None:
            raw: dict = {}
        else:
            try:
                raw = json.loads(row[0])
            except (json.JSONDecodeError, TypeError) as exc:
                raise InvalidMonitorConfig(
                    f"stored monitor config is corrupted: {exc}"
                ) from exc
        return _normalize(raw)

    # ─── 写入 + 热生效 ────────────────────────────────────

    async def put(self, config: dict) -> dict:
        """校验、归一化并持久化配置；成功后逐个通知订阅回调。

        回调可以是普通函数或异步函数：普通函数直接调用，
        异步函数 await 其结果。单个回调异常会被记录且不影响其它回调。
        返回归一化后的完整配置。
        """
        normalized = _normalize(config)
        payload = json.dumps(normalized, ensure_ascii=False)
        with self._open() as conn:
            conn.execute(
                """INSERT INTO monitor_config (key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                       value = excluded.value,
                       updated_at = excluded.updated_at""",
                (_MONITOR_CONFIG_KEY, payload, int(time.time())),
            )
            conn.commit()
        for callback in list(self._callbacks):
            await self._notify(callback, normalized)
        return normalized

    async def _notify(self, callback: Callable[[dict], Any], config: dict) -> None:
        try:
            result = callback(config)
            if inspect.isawaitable(result):
                await result
        except Exception:
            log.exception("monitor config callback failed")

    # ─── 订阅 ─────────────────────────────────────────────

    def subscribe(self, callback: Callable[[dict], Any]) -> None:
        """注册热生效回调（MVP：无需取消订阅）。"""
        self._callbacks.append(callback)