"""Graph builder — extract entities / BELONG_TO relations."""

from __future__ import annotations

from typing import Optional

from backend.foundation.core.idgen import gen_entity_id
from backend.foundation.core.models import Entity, KnowledgeItem, Relation
from backend.foundation.core.repository import EntityRepository


class GraphBuilder:
    async def build(
        self,
        item: KnowledgeItem,
        entity_repo: EntityRepository,
    ) -> tuple[list[Entity], list[Relation]]:
        entities: list[Entity] = []
        name_to_entity: dict[str, Entity] = {}

        for name in item.entities:
            if not str(name or "").strip():
                continue
            entity = await self._ensure_entity(str(name), item, entity_repo, name_to_entity)
            if entity is not None:
                entities.append(entity)

        relations: list[Relation] = []
        for rel in item.relations:
            if not isinstance(rel, dict):
                continue
            src_name = str(rel.get("from") or rel.get("src") or "").strip()
            dst_name = str(rel.get("to") or rel.get("dst") or "").strip()
            rtype = str(rel.get("type") or "BELONG_TO").strip().upper() or "BELONG_TO"
            if not src_name or not dst_name:
                continue
            src_ent = await self._ensure_entity(
                src_name, item, entity_repo, name_to_entity
            )
            dst_ent = await self._ensure_entity(
                dst_name, item, entity_repo, name_to_entity
            )
            if src_ent is None or dst_ent is None:
                continue
            await entity_repo.save_relation(src_ent.id, dst_ent.id, rtype)
            relations.append(Relation(src=src_ent.id, dst=dst_ent.id, type=rtype))

        return entities, relations

    async def _ensure_entity(
        self,
        name: str,
        item: KnowledgeItem,
        entity_repo: EntityRepository,
        name_to_entity: dict[str, Entity],
    ) -> Optional[Entity]:
        """按名称解析实体：已存在则复用 id，否则新建实体并入库。"""
        norm = name.strip()
        if not norm:
            return None
        if norm in name_to_entity:
            return name_to_entity[norm]

        existing = await entity_repo.find_entity_by_name(norm)
        if existing is not None:
            name_to_entity[norm] = existing
            return existing

        entity = Entity(
            id=gen_entity_id(),
            name=norm,
            norm_name=norm,
            type=self._guess_type(norm, item),
        )
        await entity_repo.save_entity(entity)
        name_to_entity[norm] = entity
        return entity

    @staticmethod
    def _guess_type(name: str, item: KnowledgeItem) -> str:
        _ = item
        finance_keywords = ("电网", "燃气", "水", "银行", "费")
        if any(k in name for k in finance_keywords):
            return "ORG"
        if name.endswith(("类", "分类")) or name in {"水电燃气"}:
            return "CATEGORY"
        return "UNKNOWN"
