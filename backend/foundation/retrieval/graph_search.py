"""实体关系图检索通道。

依赖 entities、relations 与 knowledge_entities。知识读取时已回填实体名，
本通道通过 EntityRepository 将查询实体解析为稳定 ID，再沿 BELONG_TO 边
扩展一跳，避免依赖标题/body 的偶然文本命中。
"""

from __future__ import annotations

from backend.foundation.core.models import KnowledgeItem, KnowledgeStatus
from backend.foundation.core.repository import EntityRepository, KnowledgeRepository


def _norm(value: str) -> str:
    return value.strip().casefold()


class GraphChannel:
    """实体关系图遍历通道。"""

    def __init__(self, knw_repo: KnowledgeRepository, entity_repo: EntityRepository) -> None:
        self._knw_repo = knw_repo
        self._entity_repo = entity_repo

    async def search(self, entities: list[str], limit: int = 20) -> list[tuple[KnowledgeItem, float]]:
        """返回 [(KnowledgeItem, score)]。

        score = 知识关联中命中的查询实体数；命中实体沿 BELONG_TO
        一跳可达的关联实体若也属于该知识，每个 +0.5。
        """
        if not entities:
            return []

        query_entities = []
        for name in entities:
            entity = await self._entity_repo.find_entity_by_name(name)
            if entity is not None:
                query_entities.append(entity)
        if not query_entities:
            return []

        query_ids = {entity.id for entity in query_entities}
        query_names = {_norm(entity.name) for entity in query_entities}
        relations = await self._entity_repo.list_relations()
        related_ids: set[str] = set()
        for relation in relations:
            if relation.type != "BELONG_TO":
                continue
            if relation.src in query_ids:
                related_ids.add(relation.dst)
            if relation.dst in query_ids:
                related_ids.add(relation.src)

        related_names: set[str] = set()
        for entity_id in related_ids - query_ids:
            related = await self._entity_repo.get_entity(entity_id)
            if related is not None:
                related_names.add(_norm(related.name))

        active = await self._knw_repo.list_active()
        scored: list[tuple[KnowledgeItem, float]] = []
        for item in active:
            if item.status != KnowledgeStatus.ACTIVE:
                continue
            associated = {_norm(name) for name in item.entities if name.strip()}
            hits = associated & query_names
            if not hits:
                continue
            score = float(len(hits))
            score += 0.5 * len(associated & related_names)
            scored.append((item, score))

        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:limit]
