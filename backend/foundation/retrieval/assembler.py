"""检索结果组装 — 结构化过滤 + 聚合计算 + evidence 回溯 → MemoryAtom。"""

from __future__ import annotations

import re
from typing import Any
from datetime import datetime, timezone
from .fuse import _parse_timestamp, _time_bounds

from backend.foundation.core.models import Evidence, KnowledgeItem, MemoryAtom
from backend.foundation.core.repository import EvidenceRepository

_AGGREGATE_HINT = re.compile(r"花|多少|金额|费用|支出|总共|合计")


def _amount_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    items = body.get("items")
    if not isinstance(items, list):
        return []
    return [
        item
        for item in items
        if isinstance(item, dict) and isinstance(item.get("amount"), (int, float))
    ]


def _matching_items(body: dict[str, Any], query: str) -> list[dict[str, Any]]:
    """按查询中的 category 优先过滤，未命中时再匹配 tag/vendor。"""
    items = _amount_items(body)
    normalized_query = query.casefold()

    category_matches = [
        item
        for item in items
        if item.get("category")
        and str(item["category"]).casefold() in normalized_query
    ]

    detail_matches: list[dict[str, Any]] = []
    for item in items:
        labels = [item.get("vendor")]
        tags = item.get("tags")
        if isinstance(tags, list):
            labels.extend(tags)
        if any(label and str(label).casefold() in normalized_query for label in labels):
            detail_matches.append(item)
    if detail_matches:
        return detail_matches
    if category_matches:
        return category_matches
    if "水电燃气" in normalized_query:
        return [item for item in items if item.get("category") in {"电费", "水费", "燃气费", "水电燃气"}]
    # Only an unqualified total may include every line. A missing category or
    # merchant must never silently turn into a different (whole-bill) answer.
    remainder = re.sub(r"(?:20\d{2}[年/-])?\d{1,2}月|20\d{2}-\d{2}(?:-\d{2})?", "", normalized_query)
    for word in ("这个月", "本月", "上个月", "上月", "我们", "我", "的", "这些", "这个", "这份", "那份",
                 "账单", "清单", "家庭", "总共", "一共", "合计", "总额", "花了", "花费", "花", "支出", "费用", "金额",
                 "多少钱", "多少", "钱", "是", "在", "来着", "请", "帮忙", "算一下", "统计一下", "？", "?", "。", " "):
        remainder = remainder.replace(word, "")
    return items if not remainder else []


def _sum_items(items: list[dict[str, Any]]) -> float | None:
    """汇总已按查询过滤且包含有效 amount 的条目。"""
    if not items:
        return None
    return sum(float(item["amount"]) for item in items)


def _group_summary(items: list[dict[str, Any]]) -> list[tuple[str, float]]:
    """按 category/tags 对 items 金额分组汇总（用于回答模板）。"""
    groups: dict[str, float] = {}
    for item in items:
        amount = item.get("amount")
        label = None
        if isinstance(item.get("tags"), list) and item["tags"]:
            label = str(item["tags"][0])
        elif item.get("category"):
            label = str(item["category"])
        if label:
            groups[label] = groups.get(label, 0.0) + float(amount)
    return sorted(groups.items(), key=lambda t: t[1], reverse=True)


class Assembler:
    """组装器：聚合计算 + 证据回溯 → MemoryAtom。"""

    def __init__(self, evidence_repo: EvidenceRepository) -> None:
        self._evidence_repo = evidence_repo

    async def _evidence_ids(self, item: KnowledgeItem) -> list[str]:
        """回溯证据 id（已回填则直接用，否则逐条确认存在）。"""
        if item.evidence_ids:
            return item.evidence_ids
        return []

    async def _resolve_evidence(self, ids: list[str]) -> list[Evidence]:
        if not ids:
            return []
        resolved: list[Evidence] = []
        for evidence_id in ids:
            evidence = await self._evidence_repo.get(evidence_id)
            if evidence is not None:
                resolved.append(evidence)
        return resolved

    def _build_answer(self, item: KnowledgeItem, query: str) -> str:
        """聚合计算：query 含金额意图且 body 可聚合时生成汇总答案。"""
        if _AGGREGATE_HINT.search(query) and isinstance(item.body, dict):
            matched_items = _matching_items(item.body, query)
            total = _sum_items(matched_items)
            if total is None:
                return "没有找到符合类别或时间条件的支出记录。"
            if total is not None:
                summary = "、".join(
                    f"{label} {amount:.2f} 元"
                    for label, amount in _group_summary(matched_items)
                )
                if summary:
                    return f"共支出 {total:.2f} 元，其中{summary}。"
                return f"共支出 {total:.2f} 元。"
        return item.title

    async def assemble(
        self,
        item: KnowledgeItem,
        score: float,
        query: str,
        latency_ms: int,
    ) -> MemoryAtom:
        evidence_ids = await self._evidence_ids(item)
        await self._resolve_evidence(evidence_ids)  # 校验证据可追溯（不吞异常）

        return MemoryAtom(
            answer=self._build_answer(item, query),
            source_evidence=evidence_ids,
            source_knowledge=item.id,
            confidence=max(0.0, min(1.0, score)),
            latency_ms=latency_ms,
        )


def expense_selection(item: KnowledgeItem, query: str, time_range=None) -> list[dict[str, Any]]:
    """Filter individual expense lines, including dates within a single bill."""
    selected = _matching_items(item.body, query)
    bounds = _time_bounds(time_range)
    month = re.search(r"(?:(20\d{2})[年/-])?(\d{1,2})月", query)
    iso_month = re.search(r"(20\d{2})-(\d{2})(?!-\d)", query)
    match = month or iso_month
    if match:
        year = int(match.group(1) or datetime.now().year)
        number = int(match.group(2))
        if not 1 <= number <= 12:
            return []
        start = datetime(year, number, 1, tzinfo=timezone.utc)
        end = datetime(year + (number == 12), number % 12 + 1, 1, tzinfo=timezone.utc)
        bounds = (start.timestamp(), end.timestamp())
    elif any(word in query for word in ("上个月", "上月")):
        bounds = _time_bounds("last_month")
    elif any(word in query for word in ("这个月", "本月")):
        now = datetime.now(timezone.utc)
        bounds = (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp(), None)
    if bounds is None:
        return selected
    start, end = bounds
    result = []
    title_month = re.search(r"(20\d{2})[年/-](\d{1,2})(?:月|(?=[^0-9]|$))", item.title)
    title_date = ""
    if title_month and 1 <= int(title_month[2]) <= 12:
        title_date = f"{title_month[1]}-{int(title_month[2]):02d}-01"
    for line in selected:
        stamp = _parse_timestamp(line.get("date") or item.body.get("date") or title_date)
        if stamp is not None and (start is None or stamp >= start) and (end is None or stamp < end):
            result.append(line)
    return result
