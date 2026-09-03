"""PIXIU Foundation — 混合检索引擎。

七步管线：router → bm25/ann/graph（并行）→ fuse → rerank → assembler → MemoryAtom。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from backend.foundation.core.models import KnowledgeItem, MemoryAtom
from backend.foundation.core.repository import (
    EntityRepository,
    EvidenceRepository,
    KnowledgeRepository,
)
from backend.foundation.core.vector_store import VectorStore

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
        vector_store: VectorStore | None = None,
    ) -> None:
        self._knw_repo = knw_repo
        self._entity_repo = entity_repo
        self._evidence_repo = evidence_repo
        self._embedder = embedder
        self._vector_store = vector_store

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
        reranked = await self.ranked(text, context_hint)

        if not reranked:
            latency = int((time.monotonic() - started) * 1000)
            return MemoryAtom(answer="", latency_ms=latency)

        top_item, top_score = reranked[0]
        latency = int((time.monotonic() - started) * 1000)
        return await Assembler(self._evidence_repo).assemble(
            top_item, top_score, text, latency
        )

    async def ranked(
        self,
        text: str,
        context_hint: dict[str, Any] | None = None,
    ) -> list[tuple[KnowledgeItem, float]]:
        """Return ranked knowledge candidates for context assembly."""
        hint = context_hint or {}
        top_k = max(1, min(100, int(hint.get("top_k", 5))))
        scope = hint.get("scope")
        time_range = hint.get("time_range")

        intent = route(text, await self._entity_names())
        search_limit = max(top_k * 4, 20)

        searches: dict[str, Any] = {}
        if "bm25" in intent.channels:
            searches["bm25"] = BM25Channel(self._knw_repo).search(text, search_limit)
        if "ann" in intent.channels:
            searches["ann"] = ANNChannel(
                self._knw_repo, self._embedder, self._vector_store
            ).search(text, search_limit)
        if "graph" in intent.channels:
            searches["graph"] = GraphChannel(self._knw_repo, self._entity_repo).search(
                intent.entities, search_limit
            )
        channel_names = list(searches)
        channel_results = await asyncio.gather(*(searches[name] for name in channel_names))
        results = dict(zip(channel_names, channel_results))

        # 先在大候选池上融合，重排（词面+时间信号）后再截断到 top_k；
        # 否则 top_k=1 时 rerank 只有一个候选、无法纠正通道间的排名噪声
        #（如实体完全同构时 graph 通道的任意排序）。
        pool_k = max(search_limit, top_k)
        fused = fuse_candidates(
            bm25=results.get("bm25"),
            ann=results.get("ann"),
            graph=results.get("graph"),
            scope=scope,
            time_range=time_range,
            top_k=pool_k,
        )
        return rerank(fused, text)[:top_k]


__all__ = ["RetrievalService"]
