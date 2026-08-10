"""轻量重排 — 词面重叠微调（在线零 LLM 约束下不引入神经网络 reranker）。"""

from __future__ import annotations

import re

from backend.foundation.core.models import KnowledgeItem

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text or ""))


def overlap_score(query: str, item: KnowledgeItem) -> float:
    """查询词与 标题+描述 的词面重叠率。"""
    desc = ""
    if isinstance(item.body, dict):
        desc = item.body.get("description", "")
    q_tokens = _tokens(query)
    item_tokens = _tokens(f"{item.title} {desc}")
    if not q_tokens or not item_tokens:
        return 0.0
    return len(q_tokens & item_tokens) / len(q_tokens)


def rerank(
    candidates: list[tuple[KnowledgeItem, float]],
    query: str,
) -> list[tuple[KnowledgeItem, float]]:
    """在融合分数基础上叠加词面重叠微调，返回重排后列表。"""
    adjusted = [
        (item, score + overlap_score(query, item))
        for item, score in candidates
    ]
    adjusted.sort(key=lambda t: t[1], reverse=True)
    return adjusted
