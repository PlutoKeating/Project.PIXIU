"""检索结果组装 — 结构化过滤 + 聚合计算 + evidence 回溯 → MemoryAtom。"""

from __future__ import annotations

import re
from typing import Any

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
    if category_matches:
        return category_matches

    detail_matches: list[dict[str, Any]] = []
    for item in items:
        labels = [item.get("vendor")]
        tags = item.get("tags")
        if isinstance(tags, list):
            labels.extend(tags)
        if any(label and str(label).casefold() in normalized_query for label in labels):
            detail_matches.append(item)
    return detail_matches or items


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
