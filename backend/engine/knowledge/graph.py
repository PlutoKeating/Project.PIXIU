"""Graph builder — extract entities / BELONG_TO relations."""

from __future__ import annotations

import uuid
from typing import Any

from engine.mocks.models import Entity, KnowledgeItem, Relation
from engine.mocks.repository import EntityRepository


class GraphBuilder:
    async def build(
        self,
        item: KnowledgeItem,
        entity_repo: EntityRepository,
    ) -> tuple[list[Entity], list[Relation]]:
        entities: list[Entity] = []
        seen: set[str] = set()

        for name in item.entities:
            norm = name.strip()
            if not norm or norm in seen:
                continue
            seen.add(norm)
            entity = Entity(
                id=f"ent_{uuid.uuid5(uuid.NAMESPACE_URL, norm).hex[:12]}",
                name=norm,
                norm_name=norm,
                type=self._guess_type(norm, item),
            )
            await entity_repo.save_entity(entity)
            entities.append(entity)

        relations: list[Relation] = []
        for rel in item.relations:
            if not isinstance(rel, dict):
                continue
            src = str(rel.get("from") or rel.get("src") or "").strip()
            dst = str(rel.get("to") or rel.get("dst") or "").strip()
            rtype = str(rel.get("type") or "BELONG_TO").upper()
            if not src or not dst:
                continue
            await entity_repo.save_relation(src, dst, rtype)
            relations.append(Relation(src=src, dst=dst, type=rtype))

        return entities, relations

    @staticmethod
    def _guess_type(name: str, item: KnowledgeItem) -> str:
        _ = item
        finance_keywords = ("电网", "燃气", "水", "银行", "费")
        if any(k in name for k in finance_keywords):
            return "ORG"
        if name.endswith(("类", "分类")) or name in {"水电燃气"}:
            return "CATEGORY"
        return "UNKNOWN"
