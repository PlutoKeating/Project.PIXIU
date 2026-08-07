"""实体关系图检索通道。

依赖实体表（entities）+ 关系表（relations）与知识文本。

⚠️ 已知架构缺口：knowledge ↔ entity 关联未持久化（schema 无关联表），
KnowledgeItem.entities 读回为空。本通道采用务实方案：
- 在 ACTIVE 知识的 title/body 文本中对查询实体做子串匹配（等价实体命中）
- 命中实体的 BELONG_TO 关联实体（relations 表）也出现在该知识文本中时加权
待团队决策后补 knowledge↔entity 关联表，可切换为精确图遍历。
"""

from __future__ import annotations

import json
from typing import Any

from backend.foundation.core.models import KnowledgeItem, KnowledgeStatus
from backend.foundation.core.repository import EntityRepository, KnowledgeRepository


def _knowledge_text(item: KnowledgeItem) -> str:
    parts: list[Any] = [item.title, item.body]
    return " ".join(str(p) for p in parts)


class GraphChannel:
    """实体关系图遍历通道。"""

    def __init__(self, knw_repo: KnowledgeRepository, entity_repo: EntityRepository) -> None:
        self._knw_repo = knw_repo
        self._entity_repo = entity_repo

    async def search(self, entities: list[str], limit: int = 20) -> list[tuple[KnowledgeItem, float]]:
        """返回 [(KnowledgeItem, score)]。

        score = 知识文本中命中的查询实体数；命中实体的 BELONG_TO
        关联实体也出现在该知识文本中时，每条 +0.5。
        """
        if not entities:
            return []

        active = await self._knw_repo.list_active()
        relations = await self._entity_repo.list_relations()
        related_edges = [
            (r.src, r.dst) for r in relations if r.src in entities or r.dst in entities
        ]
        # 关联实体的实体名（用于文本匹配加分）
        related_names: list[str] = []
        for edge_src, edge_dst in related_edges:
            other = edge_dst if edge_src in entities else edge_src
            if other not in entities:
                related_names.append(other)
        related_names = list(dict.fromkeys(related_names))

        scored: list[tuple[KnowledgeItem, float]] = []
        for item in active:
            if item.status != KnowledgeStatus.ACTIVE:
                continue
            text = _knowledge_text(item)
            hits = [e for e in entities if e and e in text]
            if not hits:
                continue
            score = float(len(hits))
            for name in related_names:
                if name and name in text:
                    score += 0.5
            scored.append((item, score))

        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:limit]
