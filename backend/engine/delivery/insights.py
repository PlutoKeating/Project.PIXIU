"""洞察流生成（批次④ B4-1）：最近高质量记忆候选（无 LLM，规则化）。

生成规则（对齐 docs/compose/specs/2026-08-29-batch4-delivery-layer-design.md [S2.1]）：
  - 候选 = 最近 24h 入库（created_at >= now-24h）的 ACTIVE knowledge，scope 精确匹配；
  - 质量分 / 敏感度取自关联 Evidence（knowledge_evidence 链接）。KnowledgeItem 本身
    不携带 quality_score/sensitivity（见 foundation/core/models.py），故服务可选注入
    evidence_repo 逐条解析；未注入时回退读取 item 上的同名属性（测试桩路径）；
  - 过滤 sensitivity > 0 的候选（敏感原文不出洞察）；
  - 按 quality_score 降序取 top limit；
  - 任一 MANUAL 冲突待处理 → 整体抑制（返回空列表，避免干扰人工裁决）。
"""

from __future__ import annotations

import time
from typing import Any

from backend.foundation.core.models import ConflictResolution

_SINCE_WINDOW_S = 24 * 3600
_SENSITIVE_THRESHOLD = 0


def _resolution_of(record: Any) -> Any:
    """兼容 ConflictRecord 对象（.resolution，str-Enum）与 dict 测试桩。"""
    if isinstance(record, dict):
        return record.get("resolution")
    return getattr(record, "resolution", None)


def _summarize(item: Any) -> str:
    """摘要 = 标题 + 正文前 60 字（候选已过滤敏感，不含敏感原文）。"""
    body = item.body if isinstance(item.body, dict) else {}
    text = str(body.get("text") or "")
    snippet = text[:60].strip()
    title = item.title or ""
    return f"{title}：{snippet}" if snippet else title


class DeliveryInsightsService:
    """最近高质量记忆洞察流生成器。"""

    def __init__(
        self,
        knowledge_repo,
        conflict_repo,
        evidence_repo=None,
    ) -> None:
        self._knowledge = knowledge_repo
        self._conflicts = conflict_repo
        self._evidence = evidence_repo

    async def insights(self, scope: str, limit: int = 3) -> list[dict]:
        """返回最近 24h 高质量记忆候选（quality 降序），每项含
        {title, summary, knowledge_id, score, kind:"recent"}。

        MANUAL 冲突待处理时返回空列表（抑制递送）。
        """
        conflicts = await self._conflicts.list()
        if any(
            _resolution_of(record) == ConflictResolution.MANUAL for record in conflicts
        ):
            return []

        since = int(time.time()) - _SINCE_WINDOW_S
        items = await self._knowledge.list_active()
        candidates = [
            item
            for item in items
            if item.scope == scope and item.created_at >= since
        ]

        scored: list[tuple[float, int, Any]] = []
        for item in candidates:
            score, sensitivity = await self._quality(item)
            if sensitivity <= _SENSITIVE_THRESHOLD:
                scored.append((score, sensitivity, item))
        scored.sort(key=lambda t: t[0], reverse=True)

        return [
            {
                "title": item.title,
                "summary": _summarize(item),
                "knowledge_id": item.id,
                "score": score,
                "kind": "recent",
            }
            for score, _sensitivity, item in scored[:limit]
        ]

    async def _quality(self, item: Any) -> tuple[float, int]:
        """解析单个候选的质量分与敏感度（取关联证据中的最大值）。"""
        if self._evidence is None:
            # 测试桩路径：item 自带 quality_score/sensitivity 属性
            return (
                float(getattr(item, "quality_score", 0.0) or 0.0),
                int(getattr(item, "sensitivity", 0) or 0),
            )
        best_score = 0.0
        worst_sensitivity = 0
        for evidence_id in getattr(item, "evidence_ids", None) or []:
            evidence = await self._evidence.get(evidence_id)
            if evidence is None:
                continue
            best_score = max(best_score, float(evidence.quality_score or 0.0))
            worst_sensitivity = max(
                worst_sensitivity, int(evidence.sensitivity or 0)
            )
        return best_score, worst_sensitivity
