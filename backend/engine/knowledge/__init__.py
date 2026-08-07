"""knowledge/ —— 知识结构化整合。

对外暴露 KnowledgeService。V0.1 使用 Mock embedding / Mock repositories。
"""

from __future__ import annotations

from typing import Optional

from engine.knowledge.embed_writer import EmbedWriter
from engine.knowledge.graph import GraphBuilder
from engine.knowledge.structurer import Structurer
from engine.kylin import get_embedder
from engine.kylin.mock_embedding import TextEmbedder
from engine.mocks.models import Evidence, KnowledgeItem
from engine.mocks.repository import EntityRepository, KnowledgeRepository


class KnowledgeService:
    def __init__(
        self,
        knw_repo: KnowledgeRepository,
        entity_repo: EntityRepository,
        embedder: Optional[TextEmbedder] = None,
        structurer: Optional[Structurer] = None,
        graph: Optional[GraphBuilder] = None,
        embed_writer: Optional[EmbedWriter] = None,
    ) -> None:
        self._knw_repo = knw_repo
        self._entity_repo = entity_repo
        resolved_embedder = embedder or get_embedder()
        self._structurer = structurer or Structurer()
        self._graph = graph or GraphBuilder()
        self._embed_writer = embed_writer or EmbedWriter(resolved_embedder)

    async def structure(self, evidence: Evidence) -> KnowledgeItem:
        item = self._structurer.structure(evidence)
        await self._graph.build(item, self._entity_repo)
        item = self._embed_writer.write(item)
        await self._knw_repo.save(item)
        return item


__all__ = ["KnowledgeService"]
