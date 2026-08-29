"""PIXIU Foundation — 监控活动日志（monitor_log）与 capture_event 广播

BE-3：每次捕获（watcher on_capture 回调）写 monitor_log 表 + WS 广播
capture_event；GET /monitor/log 分页查询。

线程语义：写路径为「短同步 sqlite」——watch 线程（或请求协程）可直接调用，
单行 INSERT 微秒级完成，不阻塞监视循环；对齐 MonitorConfigStore 的
短连接模式（每次操作新建连接，天然线程安全）。广播为 async，经 di 的
主循环调度器回到主事件循环执行（WebSocket 连接绑定主循环，跨线程直发不安全）。
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta
from typing import Any

from ..core.config import settings
from ..core.logger import get_logger
from ..monitor.ingest_bridge import (
    STATUS_IGNORED,
    STATUS_INGESTED,
    STATUS_SENSITIVE_QUARANTINED,
)
from ..storage.schema import MONITOR_LOG_DDL, create_connection
from .ws_manager import ws_manager

log = get_logger(__name__)

#: 事件状态（契约 §2）：采集器三态（ingest_bridge 定义）+ 配置变更状态。
STATUS_STATE_CHANGED = "state_changed"

#: source 额外枚举（契约 §2）：system 承载监控自身状态变更。
SOURCE_SYSTEM = "system"

#: 分页契约（§2 验收）：limit 缺省 100、上限 500。
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500


def _parse_day(date: str) -> datetime:
    """严格解析 YYYY-MM-DD（strptime 宽松接受 2026-1-1，round-trip 收紧）。

    非法（非 YYYY-MM-DD 格式 / 无效日历日如 2026-02-30）→ ValueError。
    """
    parsed = datetime.strptime(date, "%Y-%m-%d")
    if parsed.strftime("%Y-%m-%d") != date:
        raise ValueError(f"invalid date format: {date!r}")
    return parsed


def day_range(date: str) -> tuple[int, int]:
    """YYYY-MM-DD → 本地时区 [当日 00:00, 次日 00:00) 的 Unix 秒区间。

    naive datetime.timestamp() 按进程本地时区解释（无显式 tz 依赖），满足
    「本地时区日边界」语义；供 digest 按日过滤与 API 层日期校验复用。
    """
    start = _parse_day(date)
    end = start + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())


class MonitorLogStore:
    """monitor_log 活动日志存储：写 + 分页查询。

    用法：
        store = MonitorLogStore()          # 默认 PIXIU_DB_PATH
        store = MonitorLogStore("/x.db")   # 显式 db 路径（测试用 tmp_path）
        store.write_event(source="directory", status="ingested",
                          summary="记住文件 x", ts=..., evidence_id=...)
        events = store.list_events(limit=100, offset=0)
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or settings.db_path
        # 幂等建表一次性 bootstrap（独立短连接 + try/finally 显式关闭，
        # 对齐 MonitorConfigStore.__init__ 先例）。
        conn = create_connection(self._db_path)
        try:
            conn.execute(MONITOR_LOG_DDL)
            conn.commit()
        finally:
            conn.close()

    # ─── 内部：短连接（线程安全，watch 线程可直接调用） ─────

    def _open(self) -> sqlite3.Connection:
        return create_connection(self._db_path)

    # ─── 写入 ─────────────────────────────────────────────

    def write_event(
        self,
        *,
        source: str,
        status: str,
        summary: str,
        evidence_id: str | None = None,
        knowledge_id: str | None = None,
        ts: int | None = None,
    ) -> int:
        """写入一条活动日志（短同步写）。返回自增 id。"""
        if ts is None:
            ts = int(time.time())
        with closing(self._open()) as conn, conn:
            cursor = conn.execute(
                """INSERT INTO monitor_log
                       (ts, source, status, summary, evidence_id, knowledge_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (int(ts), source, status, summary, evidence_id, knowledge_id),
            )
            return int(cursor.lastrowid)

    # ─── 分页查询 ─────────────────────────────────────────

    def list_events(self, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0) -> list[dict]:
        """按时间倒序分页查询（最新在前）。

        limit 钳制到 [1, MAX_PAGE_SIZE]、offset 钳制到 >= 0；
        API 层的 Query 校验先于此处（越界请求直接 400）。
        """
        limit = max(1, min(int(limit), MAX_PAGE_SIZE))
        offset = max(0, int(offset))
        with closing(self._open()) as conn:
            rows = conn.execute(
                """SELECT ts, source, status, summary, evidence_id, knowledge_id
                   FROM monitor_log
                   ORDER BY ts DESC, id DESC
                   LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
        return [
            {
                "ts": row[0],
                "source": row[1],
                "status": row[2],
                "summary": row[3],
                "evidence_id": row[4],
                "knowledge_id": row[5],
            }
            for row in rows
        ]

    def list_events_by_day(self, date: str) -> list[dict]:
        """按日查询事件（本地时区日边界 [00:00, 次日 00:00)，时间正序）。

        供递送层 digest（B4-2）按日聚合使用：date 必须为严格 YYYY-MM-DD 有效
        日历日，非法 → ValueError（API 层已先校验返回 400，此为直连防御）；
        当日无事件 → []。行结构与 list_events 一致。
        """
        start, end = day_range(date)
        with closing(self._open()) as conn:
            rows = conn.execute(
                """SELECT ts, source, status, summary, evidence_id, knowledge_id
                   FROM monitor_log
                   WHERE ts >= ? AND ts < ?
                   ORDER BY ts ASC, id ASC""",
                (start, end),
            ).fetchall()
        return [
            {
                "ts": row[0],
                "source": row[1],
                "status": row[2],
                "summary": row[3],
                "evidence_id": row[4],
                "knowledge_id": row[5],
            }
            for row in rows
        ]


async def broadcast_capture_event(
    *,
    source: str,
    status: str,
    summary: str,
    evidence_id: str | None = None,
    knowledge_id: str | None = None,
    ts: int | None = None,
) -> None:
    """构造并广播 capture_event 帧（对齐 MONITOR_API_REQUIREMENTS.md §3）。

    data 与 §2 日志条目同构：事件未产生入库时 evidence_id/knowledge_id 为 null。
    """
    if ts is None:
        ts = int(time.time())
    await ws_manager.broadcast(
        "capture_event",
        {
            "source": source,
            "status": status,
            "summary": summary,
            "ts": int(ts),
            "evidence_id": evidence_id,
            "knowledge_id": knowledge_id,
        },
    )


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "MonitorLogStore",
    "SOURCE_SYSTEM",
    "STATUS_IGNORED",
    "STATUS_INGESTED",
    "STATUS_SENSITIVE_QUARANTINED",
    "STATUS_STATE_CHANGED",
    "broadcast_capture_event",
    "day_range",
]
