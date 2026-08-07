"""检索结果组装 — 结构化过滤 + 聚合计算 + evidence 回溯 → MemoryAtom。"""

from __future__ import annotations

import re
from typing import Any

from backend.foundation.core.models import Evidence, KnowledgeItem, MemoryAtom
from backend.foundation.core.repository import EvidenceRepository

_AGGREGATE_HINT = re.compile(r"花|多少|金额|费用|支出|总共|合计")
_AMOUNT_HINT = re.compile(r"amount|金额")


def _sum_items(body: dict[str, Any]) -> float | None:
    """若 body 含 items 列表且每项有 amount，返回金额总和，否则 None。"""
    items = body.get("items")
    if not isinstance(items, list) or not items:
        return None
    total = 0.0
    for item in items:
        if not isinstance(item, dict):
            return None
        amount = item.get("amount")
        if not isinstance(amount, (int, float)):
            return None
        total += float(amount)
    return total


def _group_summary(body: dict[str, Any]) -> list[tuple[str, float]]:
    """按 category/tags 对 items 金额分组汇总（用于回答模板）。"""
    groups: dict[str, float] = {}
    items = body.get("items") if isinstance(body.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        amount = item.get("amount")
        if not isinstance(amount, (int, float)):
            continue
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
            total = _sum_items(item.body)
            if total is not None:
                summary = "、".join(f"{label} {amount:.2f} 元" for label, amount in _group_summary(item.body))
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
