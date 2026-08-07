"""PIXIU Foundation — 混合检索引擎。

七步管线：router → bm25/ann/graph（并行）→ fuse → rerank → assembler → MemoryAtom。
"""

from __future__ import annotations

import time
from typing import Any

from backend.foundation.core.models import MemoryAtom
from backend.foundation.core.repository import (
    EntityRepository,
    EvidenceRepository,
    KnowledgeRepository,
)

from .ann import ANNChannel, Embedder
from .assembler import Assembler
from .bm25 import BM25Channel
from .fuse import fuse_candidates
from .graph_search import GraphChannel
from .rerank import rerank
from .router import route


class RetrievalService:
    """混合检索服务（/memory/query 业务入口）。"""

    def __init__(
        self,
        knw_repo: KnowledgeRepository,
        entity_repo: EntityRepository,
        evidence_repo: EvidenceRepository,
        embedder: Embedder,
    ) -> None:
        self._knw_repo = knw_repo
        self._entity_repo = entity_repo
        self._evidence_repo = evidence_repo
        self._embedder = embedder

    async def _entity_names(self) -> list[str]:
        """收集全部已知实体名（来自 ACTIVE 知识的 entities 字段，供 router 匹配）。"""
        active = await self._knw_repo.list_active()
        names: list[str] = []
        seen: set[str] = set()
        for item in active:
            for entity in item.entities:
                if entity not in seen:
                    seen.add(entity)
                    names.append(entity)
        return names

    async def query(self, text: str, context_hint: dict[str, Any] | None = None) -> MemoryAtom:
        """执行混合检索，返回 MemoryAtom。"""
        started = time.monotonic()
        hint = context_hint or {}
        top_k = int(hint.get("top_k", 5))
        scope = hint.get("scope")

        intent = route(text, await self._entity_names())
        search_limit = max(top_k * 4, 20)

        results: dict[str, list] = {}
        if "bm25" in intent.channels:
            results["bm25"] = await BM25Channel(self._knw_repo).search(text, search_limit)
        if "ann" in intent.channels:
            results["ann"] = await ANNChannel(self._knw_repo, self._embedder).search(text, search_limit)
        if "graph" in intent.channels:
            results["graph"] = await GraphChannel(self._knw_repo, self._entity_repo).search(
                intent.entities, search_limit
            )

        fused = fuse_candidates(
            bm25=results.get("bm25"),
            ann=results.get("ann"),
            graph=results.get("graph"),
            scope=scope,
            top_k=top_k,
        )
        reranked = rerank(fused, text)

        if not reranked:
            latency = int((time.monotonic() - started) * 1000)
            return MemoryAtom(answer="", latency_ms=latency)

        top_item, top_score = reranked[0]
        latency = int((time.monotonic() - started) * 1000)
        return await Assembler(self._evidence_repo).assemble(top_item, top_score, text, latency)


__all__ = ["RetrievalService"]
