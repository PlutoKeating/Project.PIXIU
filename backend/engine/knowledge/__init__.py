"""knowledge/ —— 知识结构化整合。

对外暴露 KnowledgeService。通过 foundation/core Repository 契约注入仓储实现。
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.foundation.core.models import Evidence, KnowledgeItem, KnowledgeStatus
from backend.foundation.core.repository import (
    EntityRepository,
    KnowledgeRepository,
    KnowledgeVersionConflict,
)
from backend.foundation.core.vector_store import VectorStore

from backend.engine.knowledge.embed_writer import EmbedWriter
from backend.engine.knowledge.graph import GraphBuilder
from backend.engine.knowledge.structurer import Structurer
from backend.engine.kylin import get_embedder
from backend.engine.kylin.embedding import TextEmbedder

logger = logging.getLogger(__name__)


class KnowledgeService:
    def __init__(
        self,
        knw_repo: KnowledgeRepository,
        entity_repo: EntityRepository,
        embedder: Optional[TextEmbedder] = None,
        structurer: Optional[Structurer] = None,
        graph: Optional[GraphBuilder] = None,
        embed_writer: Optional[EmbedWriter] = None,
        vector_store: Optional[VectorStore] = None,
    ) -> None:
        self._knw_repo = knw_repo
        self._entity_repo = entity_repo
        resolved_embedder = embedder or get_embedder()
        self._structurer = structurer or Structurer()
        self._graph = graph or GraphBuilder()
        self._embed_writer = embed_writer or EmbedWriter(resolved_embedder)
        self._vector_store = vector_store

    async def structure(self, evidence: Evidence) -> KnowledgeItem:
        item = self._structurer.structure(evidence)
        return await self._persist(item, evidence_id=evidence.id)

    async def update(
        self, item: KnowledgeItem, *, expected_version: int | None = None
    ) -> KnowledgeItem:
        """Replace and reindex an existing knowledge item without changing its ID."""
        if await self._knw_repo.get(item.id) is None:
            raise KeyError(item.id)
        return await self._persist(item, expected_version=expected_version)

    async def materialize(self, item: KnowledgeItem) -> KnowledgeItem:
        """Index and upsert a trusted structured item received from synchronization."""
        return await self._persist(item)

    async def merge(self, item: KnowledgeItem, *, expected_versions: dict[str, int]) -> KnowledgeItem:
        """Apply a reviewed private consolidation and remove obsolete vectors.

        The repository checks every source in one conditional write. Generate
        the new embedding first so a model/SDK failure cannot supersede sources.
        Approval and sensitivity checks belong to the calling API.
        """
        if self._vector_store is None:
            raise RuntimeError("reviewed merge requires a production vector store")
        item = self._embed_writer.write(item)
        vector = self._embed_writer.vector(item)
        if not vector:
            raise ValueError("merged memory has no embedding")
        if not await self._knw_repo.merge_if_versions(item, expected_versions):
            raise KnowledgeVersionConflict(item.id)
        await self._vector_store.upsert(item.id, vector)
        for identifier in expected_versions:
            if identifier != item.id:
                await self._vector_store.delete(identifier)
        return await self._knw_repo.get(item.id)

    async def forget(self, knowledge_id: str) -> None:
        """Hide a synchronized tombstone and remove its production vector."""
        await self._knw_repo.update_status(knowledge_id, KnowledgeStatus.FORGOTTEN)
        if self._vector_store is not None:
            await self._vector_store.delete(knowledge_id)

    async def _persist(
        self,
        item: KnowledgeItem,
        *,
        evidence_id: str = "",
        expected_version: int | None = None,
    ) -> KnowledgeItem:
        step = "graph"
        try:
            await self._graph.build(item, self._entity_repo)
            step = "embed"
            item = self._embed_writer.write(item)
            step = "knowledge_save"
            # 先落知识条目（knowledge_vec 外键依赖 knowledge_items.id），再写向量
            if expected_version is None:
                await self._knw_repo.save(item)
            elif not await self._knw_repo.save_if_version(item, expected_version):
                raise KnowledgeVersionConflict(item.id)
            step = "vector_save"
            if self._vector_store is not None:
                vector = self._embed_writer.vector(item)
                if vector is not None:
                    await self._vector_store.upsert(item.id, vector)
            else:
                # Transitional compatibility for non-production test/custom callers.
                # The application DI always injects an explicit VectorStore.
                vec = self._embed_writer.vector_bytes(item)
                if vec is not None:
                    await self._knw_repo.save_vector(
                        item.id, self._embed_writer.dim(item), vec
                    )
        except Exception:
            logger.warning(
                "knowledge.structure failed at step=%s knowledge_id=%s evidence_id=%s",
                step,
                item.id,
                evidence_id,
            )
            raise
        return item


__all__ = ["KnowledgeService", "KnowledgeVersionConflict"]
