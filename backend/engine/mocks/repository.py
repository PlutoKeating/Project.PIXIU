"""In-memory Mock repositories implementing the foundation/core Repository contract."""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from engine.mocks.models import (
    ConflictRecord,
    Entity,
    Evidence,
    KnowledgeItem,
    Preference,
    PreferenceSnapshot,
    Relation,
)


@runtime_checkable
class EvidenceRepository(Protocol):
    async def save(self, evidence: Evidence) -> str: ...
    async def get(self, id: str) -> Optional[Evidence]: ...


@runtime_checkable
class KnowledgeRepository(Protocol):
    async def save(self, item: KnowledgeItem) -> str: ...
    async def get(self, id: str) -> Optional[KnowledgeItem]: ...
    async def search_fts(self, query: str, limit: int = 10) -> list[KnowledgeItem]: ...
    async def list_active(self) -> list[KnowledgeItem]: ...


@runtime_checkable
class PreferenceRepository(Protocol):
    async def save(self, pref: Preference) -> str: ...
    async def get(self, id: str) -> Optional[Preference]: ...
    async def get_history(self, pref_id: str) -> list[PreferenceSnapshot]: ...


@runtime_checkable
class EntityRepository(Protocol):
    async def save_entity(self, entity: Entity) -> str: ...
    async def save_relation(self, src: str, dst: str, type: str) -> None: ...
    async def list_entities(self) -> list[Entity]: ...
    async def list_relations(self) -> list[Relation]: ...


@runtime_checkable
class ConflictRepository(Protocol):
    async def save(self, record: ConflictRecord) -> str: ...
    async def list(self) -> list[ConflictRecord]: ...


class MockEvidenceRepository:
    def __init__(self) -> None:
        self._store: dict[str, Evidence] = {}

    async def save(self, evidence: Evidence) -> str:
        self._store[evidence.id] = evidence
        return evidence.id

    async def get(self, id: str) -> Optional[Evidence]:
        return self._store.get(id)


class MockKnowledgeRepository:
    def __init__(self) -> None:
        self._store: dict[str, KnowledgeItem] = {}

    async def save(self, item: KnowledgeItem) -> str:
        self._store[item.id] = item
        return item.id

    async def get(self, id: str) -> Optional[KnowledgeItem]:
        return self._store.get(id)

    async def search_fts(self, query: str, limit: int = 10) -> list[KnowledgeItem]:
        q = query.lower()
        hits = [
            item
            for item in self._store.values()
            if item.status == "ACTIVE"
            and (q in item.title.lower() or q in str(item.body).lower())
        ]
        return hits[:limit]

    async def list_active(self) -> list[KnowledgeItem]:
        return [i for i in self._store.values() if i.status == "ACTIVE"]


class MockPreferenceRepository:
    def __init__(self) -> None:
        self._store: dict[str, Preference] = {}
        self._history: dict[str, list[PreferenceSnapshot]] = {}

    async def save(self, pref: Preference) -> str:
        existing = self._store.get(pref.id)
        if existing is not None:
            snap = PreferenceSnapshot(
                version=existing.version,
                value=dict(existing.value),
                updated_at=existing.updated_at,
            )
            self._history.setdefault(pref.id, []).append(snap)
            pref.version = existing.version + 1
        self._store[pref.id] = pref
        return pref.id

    async def get(self, id: str) -> Optional[Preference]:
        return self._store.get(id)

    async def get_history(self, pref_id: str) -> list[PreferenceSnapshot]:
        current = self._store.get(pref_id)
        history = list(self._history.get(pref_id, []))
        if current is not None:
            history = history + [
                PreferenceSnapshot(
                    version=current.version,
                    value=dict(current.value),
                    updated_at=current.updated_at,
                )
            ]
        return history


class MockEntityRepository:
    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._relations: list[Relation] = []

    async def save_entity(self, entity: Entity) -> str:
        self._entities[entity.id] = entity
        return entity.id

    async def save_relation(self, src: str, dst: str, type: str) -> None:
        self._relations.append(Relation(src=src, dst=dst, type=type))

    async def list_entities(self) -> list[Entity]:
        return list(self._entities.values())

    async def list_relations(self) -> list[Relation]:
        return list(self._relations)


class MockConflictRepository:
    def __init__(self) -> None:
        self._store: dict[str, ConflictRecord] = {}

    async def save(self, record: ConflictRecord) -> str:
        self._store[record.id] = record
        return record.id

    async def list(self) -> list[ConflictRecord]:
        return list(self._store.values())
