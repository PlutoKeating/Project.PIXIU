"""定时简报生成（批次④ B4-2）：按日聚合 monitor_log 事件 → 中文简报。

生成规则（对齐 docs/compose/specs/2026-08-29-batch4-delivery-layer-design.md [S2.2]）：
  - 按日（本地时区日边界）取 monitor_log 事件（MonitorLogStore.list_events_by_day）；
  - 仅 status == "ingested" 计为「新增记忆」，按 source 分组计数。monitor_log
    的 source 枚举是 directory|clipboard|behavior|screenshot|system，**无独立
    「文本」枚举**——文本文件经 ingest_bridge 也走 directory source（见批次②），
    故模板按 source 枚举分组即可；
  - sensitive_quarantined 不计入新增记忆（隔离语义：未沉淀为记忆），>0 时
    作为「敏感内容已隔离」单列；ignored / state_changed 不计入；
  - summary 为服务端规则化中文文案，不含任何事件 summary 原文（敏感隔离原则）；
  - 空日 → "当日无新记忆"。
偏好/冲突计数按任务说明简化：MonitorLogStore 不携带偏好/冲突数据，且任务
Produces 接口为 ``DeliveryDigestService(monitor_log)``——本服务只消费
monitor_log，偏好/冲突情况不在简报中出现（冲突计数经 ConflictRepository 可
作为后续增量，见任务上下文「可选，简化可不含」）。
"""

from __future__ import annotations

import asyncio
from collections import Counter

#: 新增记忆按 source 分组的固定展示顺序（与契约 §2 枚举一致）。
_SOURCE_LABELS = {
    "directory": "目录",
    "clipboard": "剪贴板",
    "behavior": "行为",
    "screenshot": "截屏",
    "system": "系统",
}


def _build_summary(counts: dict[str, int], quarantined: int) -> str:
    """规则化中文简报文案（模板计数，不含任何原始 summary 文本）。"""
    total = sum(counts.values())
    parts: list[str] = []
    if total > 0:
        groups = "、".join(
            f"{_SOURCE_LABELS[src]} {counts[src]}"
            for src in _SOURCE_LABELS
            if counts.get(src, 0) > 0
        )
        parts.append(f"当日新增 {total} 条记忆（{groups}）")
    else:
        parts.append("当日无新记忆")
    if quarantined > 0:
        parts.append(f"另有 {quarantined} 条敏感内容已隔离")
    return "，".join(parts)


class DeliveryDigestService:
    """按日聚合当日 monitor_log 事件生成中文简报（无 LLM、离线可运行）。"""

    def __init__(self, monitor_log) -> None:
        #: MonitorLogStore（同步短连接 sqlite，线程安全；调用经 to_thread 包装）。
        self._monitor_log = monitor_log

    async def digest(self, date: str) -> dict:
        """返回 {"date": "YYYY-MM-DD", "summary": 中文简报}。

        date 为严格 YYYY-MM-DD 有效日历日；非法 → ValueError（API 层捕获后
        返回 400 INVALID_REQUEST）。
        """
        # MonitorLogStore 是同步短连接实现（批次②先例），async 服务经
        # asyncio.to_thread 包装避免阻塞事件循环。
        events = await asyncio.to_thread(self._monitor_log.list_events_by_day, date)

        counts: Counter[str] = Counter()
        quarantined = 0
        for event in events:
            if event["status"] == "ingested":
                counts[event["source"]] += 1
            elif event["status"] == "sensitive_quarantined":
                quarantined += 1
            # ignored / state_changed：不沉淀为记忆，不计入
        return {"date": date, "summary": _build_summary(counts, quarantined)}
