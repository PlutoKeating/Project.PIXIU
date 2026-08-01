"""Tests for core/repository.py — ABC interfaces contract verification.

All Repository ABCs:
  - Must not be directly instantiable.
  - Minimal fake implementations must satisfy the interface
    (all abstract methods present with correct signatures).
"""

from __future__ import annotations

from typing import Optional

import pytest

from backend.foundation.core.models import (
    ConflictRecord,
    ConflictResolution,
    Entity,
    Evidence,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeStatus,
    Preference,
    PreferenceCategory,
    PreferenceSnapshot,
    Relation,
    SourceType,
)
from backend.foundation.core.repository import (
    ConflictRepository,
    EntityRepository,
    EvidenceRepository,
    KnowledgeRepository,
    PreferenceRepository,
)

NOW = 1700000000

# ─── valid model factories ──────────────────────────────


def _evd(**kwargs) -> Evidence:
    defaults = {
        "id": "evd_01KYSVDG0739TWR7179BEYETVT",
        "source_type": SourceType.OCR,
        "scope": "user:alice",
        "created_at": NOW,
    }
    return Evidence(**(defaults | kwargs))


def _knw(**kwargs) -> KnowledgeItem:
    defaults = {
        "id": "knw_01KYSVDG0739TWR7179BEYETVT",
        "kind": KnowledgeKind.FACT,
        "title": "test",
        "scope": "user:alice",
        "created_at": NOW,
        "updated_at": NOW,
    }
    return KnowledgeItem(**(defaults | kwargs))


def _pref(**kwargs) -> Preference:
    defaults = {
        "id": "pref_01KYSVDG0739TWR7179BEYETVT",
        "category": PreferenceCategory.OP_HABIT,
        "key": "x",
        "scope": "user:alice",
        "created_at": NOW,
        "updated_at": NOW,
    }
    return Preference(**(defaults | kwargs))


def _ent(**kwargs) -> Entity:
    defaults = {
        "id": "ent_01KYSVDG0739TWR7179BEYETVT",
        "name": "X",
        "norm_name": "x",
        "type": "ORG",
    }
    return Entity(**(defaults | kwargs))


def _cfl(**kwargs) -> ConflictRecord:
    defaults = {
        "id": "cfl_01KYSVDG0739TWR7179BEYETVT",
        "target_knowledge": "knw_x",
        "field": "x",
        "created_at": NOW,
    }
    return ConflictRecord(**(defaults | kwargs))


# ══════════════════════════════════════════════════════════
# Group 1: ABCs cannot be instantiated directly
# ══════════════════════════════════════════════════════════


def test_evidence_repo_cannot_instantiate():
    with pytest.raises(TypeError):
        EvidenceRepository()  # type: ignore[abstract]


def test_knowledge_repo_cannot_instantiate():
    with pytest.raises(TypeError):
        KnowledgeRepository()  # type: ignore[abstract]


def test_preference_repo_cannot_instantiate():
    with pytest.raises(TypeError):
        PreferenceRepository()  # type: ignore[abstract]


def test_entity_repo_cannot_instantiate():
    with pytest.raises(TypeError):
        EntityRepository()  # type: ignore[abstract]


def test_conflict_repo_cannot_instantiate():
    with pytest.raises(TypeError):
        ConflictRepository()  # type: ignore[abstract]


# ══════════════════════════════════════════════════════════
# Group 2: minimal fake implementations satisfy the interface
#         (all abstract methods present with correct signatures)
# ══════════════════════════════════════════════════════════


class FakeEvidenceRepo(EvidenceRepository):
    async def save(self, evidence: Evidence) -> str:
        return evidence.id

    async def get(self, id: str) -> Optional[Evidence]:
        return None


class FakeKnowledgeRepo(KnowledgeRepository):
    async def save(self, item: KnowledgeItem) -> str:
        return item.id

    async def get(self, id: str) -> Optional[KnowledgeItem]:
        return None

    async def search_fts(self, query: str, limit: int) -> list[KnowledgeItem]:
        return []


class FakePreferenceRepo(PreferenceRepository):
    async def save(self, pref: Preference) -> str:
        return pref.id

    async def get_history(self, pref_id: str) -> list[PreferenceSnapshot]:
        return []


class FakeEntityRepo(EntityRepository):
    async def save_entity(self, entity: Entity) -> str:
        return entity.id

    async def save_relation(self, src: str, dst: str, type: str) -> None:
        pass


class FakeConflictRepo(ConflictRepository):
    async def save(self, record: ConflictRecord) -> str:
        return record.id

    async def list(self) -> list[ConflictRecord]:
        return []


# ─── Verify fakes can be instantiated ─────────────────


def test_fake_evidence_repo_instantiable():
    repo = FakeEvidenceRepo()
    assert isinstance(repo, EvidenceRepository)


def test_fake_knowledge_repo_instantiable():
    repo = FakeKnowledgeRepo()
    assert isinstance(repo, KnowledgeRepository)


def test_fake_preference_repo_instantiable():
    repo = FakePreferenceRepo()
    assert isinstance(repo, PreferenceRepository)


def test_fake_entity_repo_instantiable():
    repo = FakeEntityRepo()
    assert isinstance(repo, EntityRepository)


def test_fake_conflict_repo_instantiable():
    repo = FakeConflictRepo()
    assert isinstance(repo, ConflictRepository)


# ─── Verify fakes satisfy the contract at runtime ─────

@pytest.mark.asyncio
async def test_fake_evidence_save_returns_id():
    repo = FakeEvidenceRepo()
    evd = _evd()
    result = await repo.save(evd)
    assert result == evd.id


@pytest.mark.asyncio
async def test_fake_knowledge_save_returns_id():
    repo = FakeKnowledgeRepo()
    knw = _knw()
    result = await repo.save(knw)
    assert result == knw.id


@pytest.mark.asyncio
async def test_fake_knowledge_search_fts_returns_list():
    repo = FakeKnowledgeRepo()
    result = await repo.search_fts("hello", 10)
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_fake_preference_save_returns_id():
    repo = FakePreferenceRepo()
    pref = _pref()
    result = await repo.save(pref)
    assert result == pref.id


@pytest.mark.asyncio
async def test_fake_preference_get_history_returns_list():
    repo = FakePreferenceRepo()
    result = await repo.get_history("pref_x")
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_fake_entity_save_entity_returns_id():
    repo = FakeEntityRepo()
    ent = _ent()
    result = await repo.save_entity(ent)
    assert result == ent.id


@pytest.mark.asyncio
async def test_fake_entity_save_relation_returns_none():
    repo = FakeEntityRepo()
    result = await repo.save_relation("a", "b", "BELONG_TO")
    assert result is None


@pytest.mark.asyncio
async def test_fake_conflict_save_returns_id():
    repo = FakeConflictRepo()
    cfl = _cfl()
    result = await repo.save(cfl)
    assert result == cfl.id


@pytest.mark.asyncio
async def test_fake_conflict_list_returns_list():
    repo = FakeConflictRepo()
    result = await repo.list()
    assert isinstance(result, list)
