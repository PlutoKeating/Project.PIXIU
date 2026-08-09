"""检索结果融合 — context 硬过滤 + RRF 排名融合。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from backend.foundation.core.models import KnowledgeItem

RRF_K = 60


def fuse_rrf(rankings: dict[str, list[str]]) -> dict[str, float]:
    """Reciprocal Rank Fusion。

    :param rankings: {通道名: [按相关度降序的 knowledge_id 列表]}
    :return: {knowledge_id: fused_score}
    """
    fused: dict[str, float] = {}
    for channel_ids in rankings.values():
        for rank, knowledge_id in enumerate(channel_ids):
            fused[knowledge_id] = fused.get(knowledge_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    return fused


def _parse_timestamp(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        return float(raw)
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _time_bounds(
    time_range: Any,
    now_ts: float | None = None,
) -> tuple[float | None, float | None] | None:
    """将 API time_range 转为 UTC 半开区间 [start, end)。"""
    if isinstance(time_range, dict):
        start = _parse_timestamp(time_range.get("start") or time_range.get("from"))
        end = _parse_timestamp(time_range.get("end") or time_range.get("to"))
        return (start, end) if start is not None or end is not None else None
    if not isinstance(time_range, str):
        return None

    now = datetime.fromtimestamp(now_ts, timezone.utc) if now_ts is not None else datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if time_range == "today":
        return today.timestamp(), (today + timedelta(days=1)).timestamp()
    if time_range in {"last_7_days", "last_week"}:
        return (now - timedelta(days=7)).timestamp(), now.timestamp()
    if time_range in {"last_30_days", "last_month"}:
        month_start = today.replace(day=1)
        previous_end = month_start
        previous_start = (month_start - timedelta(days=1)).replace(day=1)
        if time_range == "last_30_days":
            return (now - timedelta(days=30)).timestamp(), now.timestamp()
        return previous_start.timestamp(), previous_end.timestamp()
    return None


def _item_timestamps(item: KnowledgeItem) -> list[float]:
    """优先使用结构化业务日期；缺失时退回知识创建时间。"""
    values: list[Any] = []
    if isinstance(item.body, dict):
        values.extend(item.body.get(key) for key in ("date", "created_at", "timestamp"))
        raw_items = item.body.get("items")
        if isinstance(raw_items, list):
            for raw_item in raw_items:
                if isinstance(raw_item, dict):
                    values.extend(raw_item.get(key) for key in ("date", "created_at", "timestamp"))
    parsed = [timestamp for value in values if (timestamp := _parse_timestamp(value)) is not None]
    return parsed or [float(item.created_at)]


def matches_time_range(
    item: KnowledgeItem,
    time_range: Any,
    now_ts: float | None = None,
) -> bool:
    """判断知识的业务日期/创建时间是否落在 context_hint.time_range。"""
    bounds = _time_bounds(time_range, now_ts=now_ts)
    if bounds is None:
        return True
    start, end = bounds
    return any(
        (start is None or timestamp >= start) and (end is None or timestamp < end)
        for timestamp in _item_timestamps(item)
    )


def fuse_candidates(
    bm25: list[tuple[KnowledgeItem, float]] | None = None,
    ann: list[tuple[KnowledgeItem, float]] | None = None,
    graph: list[tuple[KnowledgeItem, float]] | None = None,
    scope: str | None = None,
    time_range: Any = None,
    top_k: int = 10,
) -> list[tuple[KnowledgeItem, float]]:
    """三通道融合入口：scope/time_range 硬过滤 → RRF → Top-K。

    各通道得分仅用于通道内排序（RRF 只看排名），因此通道内按 score 降序即可。
    """
    rankings: dict[str, list[str]] = {}
    items_by_id: dict[str, KnowledgeItem] = {}

    def _add(channel: str, results: list[tuple[KnowledgeItem, float]] | None) -> None:
        if not results:
            return
        eligible = [
            (item, score)
            for item, score in results
            if (scope is None or item.scope == scope)
            and matches_time_range(item, time_range)
        ]
        ordered = sorted(eligible, key=lambda t: t[1], reverse=True)
        if not ordered:
            return
        rankings[channel] = [item.id for item, _ in ordered]
        for item, _ in ordered:
            items_by_id[item.id] = item

    _add("bm25", bm25)
    _add("ann", ann)
    _add("graph", graph)

    fused = fuse_rrf(rankings)

    ranked = sorted(fused.items(), key=lambda t: t[1], reverse=True)[:top_k]
    return [(items_by_id[kid], score) for kid, score in ranked]
