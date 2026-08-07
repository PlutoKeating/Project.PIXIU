"""V0.2 引擎测试用内存仓储 —— 实现 foundation/core Repository ABC。

与 SQLite 实现保持一致的语义（偏好版本化、list_active、向量存储等），
供引擎单元测试与离线 demo 使用。
"""

from __future__ import annotations

import time
from typing import Optional

from backend.foundation.core.models import (
    ConflictRecord,
    Entity,
    Evidence,
    KnowledgeItem,
    KnowledgeStatus,
    Preference,
    PreferenceSnapshot,
    Relation,
)
from backend.foundation.core.repository import (
    ConflictRepository,
    EntityRepository,
    EvidenceRepository,
    KnowledgeRepository,
    PreferenceRepository,
)


class MockEvidenceRepository(EvidenceRepository):
    def __init__(self) -> None:
        self._store: dict[str, Evidence] = {}

    async def save(self, evidence: Evidence) -> str:
        self._store[evidence.id] = evidence
        return evidence.id

    async def get(self, id: str) -> Optional[Evidence]:
        return self._store.get(id)

    async def list_by_scope(self, scope: str, limit: int = 50) -> list[Evidence]:
        hits = [e for e in self._store.values() if e.scope == scope]
        hits.sort(key=lambda e: e.created_at, reverse=True)
        return hits[:limit]


class MockKnowledgeRepository(KnowledgeRepository):
    def __init__(self) -> None:
        self._store: dict[str, KnowledgeItem] = {}
        self._vectors: dict[str, bytes] = {}
        self._dims: dict[str, int] = {}

    async def save(self, item: KnowledgeItem) -> str:
        self._store[item.id] = item
        return item.id

    async def get(self, id: str) -> Optional[KnowledgeItem]:
        return self._store.get(id)

    async def search_fts(self, query: str, limit: int = 20) -> list[KnowledgeItem]:
        q = query.lower()
        hits = [
            i
            for i in self._store.values()
            if i.status == KnowledgeStatus.ACTIVE
            and (q in i.title.lower() or q in str(i.body).lower())
        ]
        return hits[:limit]

    async def search_by_title(self, query: str, limit: int = 20) -> list[KnowledgeItem]:
        q = query.lower()
        hits = [i for i in self._store.values() if q in i.title.lower()]
        hits.sort(key=lambda i: i.updated_at, reverse=True)
        return hits[:limit]

    async def save_vector(self, knowledge_id: str, dim: int, vec: bytes) -> None:
        self._vectors[knowledge_id] = vec
        self._dims[knowledge_id] = dim

    async def update_status(self, id: str, status: KnowledgeStatus) -> None:
        item = self._store.get(id)
        if item is not None:
            item.status = status

    async def list_active(self) -> list[KnowledgeItem]:
        return [i for i in self._store.values() if i.status == KnowledgeStatus.ACTIVE]


class MockPreferenceRepository(PreferenceRepository):
    def __init__(self) -> None:
        self._store: dict[str, Preference] = {}
        self._history: dict[str, list[PreferenceSnapshot]] = {}

    async def save(self, pref: Preference) -> str:
        """版本化保存：同 key+scope 复用稳定 id，version+1，旧版本入历史。"""
        existing = await self.get_by_key(pref.key, pref.scope)
        if existing is not None:
            self._history.setdefault(existing.id, []).append(
                PreferenceSnapshot(
                    version=existing.version,
                    value=dict(existing.value),
                    updated_at=existing.updated_at,
                )
            )
            effective = pref.model_copy(
                update={
                    "id": existing.id,
                    "version": existing.version + 1,
                    "created_at": existing.created_at,
                    "updated_at": int(time.time()),
                }
            )
        else:
            effective = pref
        self._store[effective.id] = effective
        return effective.id

    async def get(self, id: str) -> Optional[Preference]:
        return self._store.get(id)

    async def get_history(self, pref_id: str) -> list[PreferenceSnapshot]:
        snapshots = list(self._history.get(pref_id, []))
        current = self._store.get(pref_id)
        if current is not None and not any(
            s.version == current.version for s in snapshots
        ):
            snapshots.append(
                PreferenceSnapshot(
                    version=current.version,
                    value=dict(current.value),
                    updated_at=current.updated_at,
                )
            )
            snapshots.sort(key=lambda s: s.version)
        return snapshots

    async def get_by_key(self, key: str, scope: str) -> Optional[Preference]:
        matches = [p for p in self._store.values() if p.key == key and p.scope == scope]
        if not matches:
            return None
        return max(matches, key=lambda p: p.version)


class MockEntityRepository(EntityRepository):
    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._relations: list[Relation] = []

    async def save_entity(self, entity: Entity) -> str:
        self._entities[entity.id] = entity
        return entity.id

    async def get_entity(self, id: str) -> Optional[Entity]:
        return self._entities.get(id)

    async def save_relation(self, src: str, dst: str, type: str) -> None:
        rel = Relation(src=src, dst=dst, type=type)
        if rel not in self._relations:
            self._relations.append(rel)

    async def get_relations(self, entity_id: str) -> list[Relation]:
        return [
            r for r in self._relations if r.src == entity_id or r.dst == entity_id
        ]

    async def find_entity_by_name(self, name: str) -> Optional[Entity]:
        norm = name.strip().lower()
        for e in self._entities.values():
            if e.norm_name.strip().lower() == norm:
                return e
        return None

    async def list_relations(self) -> list[Relation]:
        return list(self._relations)

    async def list_entities(self) -> list[Entity]:
        return list(self._entities.values())


class MockConflictRepository(ConflictRepository):
    def __init__(self) -> None:
        self._store: dict[str, ConflictRecord] = {}

    async def save(self, record: ConflictRecord) -> str:
        self._store[record.id] = record
        return record.id

    async def get(self, id: str) -> Optional[ConflictRecord]:
        return self._store.get(id)

    async def list(self) -> list[ConflictRecord]:
        return sorted(self._store.values(), key=lambda r: r.created_at, reverse=True)
