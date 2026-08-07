"""检索结果融合 — RRF 排名融合 + context_hint 加权。"""

from __future__ import annotations

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


def apply_scope_weight(
    fused: dict[str, float],
    items: dict[str, KnowledgeItem],
    scope: str | None,
) -> dict[str, float]:
    """context_hint.scope 加权：候选 scope 命中时 ×1.5。"""
    if not scope:
        return fused
    return {
        knowledge_id: score * (1.5 if items[knowledge_id].scope == scope else 1.0)
        for knowledge_id, score in fused.items()
    }


def fuse_candidates(
    bm25: list[tuple[KnowledgeItem, float]] | None = None,
    ann: list[tuple[KnowledgeItem, float]] | None = None,
    graph: list[tuple[KnowledgeItem, float]] | None = None,
    scope: str | None = None,
    top_k: int = 10,
) -> list[tuple[KnowledgeItem, float]]:
    """三通道融合入口：内部按通道名排序 → RRF → scope 加权 → Top-K。

    各通道得分仅用于通道内排序（RRF 只看排名），因此通道内按 score 降序即可。
    """
    rankings: dict[str, list[str]] = {}
    items_by_id: dict[str, KnowledgeItem] = {}

    def _add(channel: str, results: list[tuple[KnowledgeItem, float]] | None) -> None:
        if not results:
            return
        ordered = sorted(results, key=lambda t: t[1], reverse=True)
        rankings[channel] = [item.id for item, _ in ordered]
        for item, _ in ordered:
            items_by_id[item.id] = item

    _add("bm25", bm25)
    _add("ann", ann)
    _add("graph", graph)

    fused = fuse_rrf(rankings)
    fused = apply_scope_weight(fused, items_by_id, scope)

    ranked = sorted(fused.items(), key=lambda t: t[1], reverse=True)[:top_k]
    return [(items_by_id[kid], score) for kid, score in ranked]
