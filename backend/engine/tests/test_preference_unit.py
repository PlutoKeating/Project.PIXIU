"""Unit tests for preference extract / resolve (no Knowledge / FTS / trigram)."""

from __future__ import annotations

from typing import Optional

import pytest

from backend.engine.preference import PreferenceService
from backend.engine.preference.adapter import Adapter
from backend.engine.preference.extractor import Extractor
from backend.engine.preference.rules import (
    Rule,
    VERBOSITY_KEY,
    default_rules,
)
from backend.foundation.core.idgen import gen_evidence_id, gen_pref_id
from backend.foundation.core.models import Evidence, Preference, PreferenceSnapshot


class FakePreferenceRepo:
    def __init__(self) -> None:
        self.items: dict[str, Preference] = {}
        self.history: dict[str, list[PreferenceSnapshot]] = {}

    async def save(self, pref: Preference) -> str:
        existing = await self.get_by_key(pref.key, pref.scope)
        if existing is not None:
            self.history.setdefault(existing.id, []).append(
                PreferenceSnapshot(
                    version=existing.version,
                    value=dict(existing.value),
                    updated_at=existing.updated_at,
                )
            )
            pref = pref.model_copy(
                update={
                    "id": existing.id,
                    "version": existing.version + 1,
                    "created_at": existing.created_at,
                }
            )
        self.items[pref.id] = pref
        return pref.id

    async def get(self, id: str) -> Optional[Preference]:
        return self.items.get(id)

    async def get_history(self, pref_id: str) -> list[PreferenceSnapshot]:
        snapshots = list(self.history.get(pref_id, []))
        current = self.items.get(pref_id)
        if current is not None and not any(s.version == current.version for s in snapshots):
            snapshots.append(
                PreferenceSnapshot(
                    version=current.version,
                    value=dict(current.value),
                    updated_at=current.updated_at,
                )
            )
        return sorted(snapshots, key=lambda s: s.version)

    async def get_by_key(self, key: str, scope: str) -> Optional[Preference]:
        matched = [
            item for item in self.items.values() if item.key == key and item.scope == scope
        ]
        if not matched:
            return None
        return max(matched, key=lambda item: item.version)


def _evidence(
    source_type: str,
    raw: dict,
    *,
    scope: str = "user:alice",
    sensitivity: int = 0,
) -> Evidence:
    return Evidence(
        id=gen_evidence_id(),
        source_type=source_type,
        raw=raw,
        quality_score=0.9,
        sensitivity=sensitivity,
        scope=scope,
        created_at=1_700_000_000,
    )


def _pref(
    *,
    key: str,
    scope: str,
    version: int,
    value: dict | None = None,
) -> Preference:
    return Preference(
        id=gen_pref_id(),
        category="OUTPUT_STYLE",
        key=key,
        value=value or {"verbosity": "compact"},
        confidence=0.9,
        version=version,
        scope=scope,
        created_at=1,
        updated_at=1,
    )


def test_adapter_resolve_scope_isolation_and_highest_version() -> None:
    alice_v1 = _pref(key=VERBOSITY_KEY, scope="user:alice", version=1, value={"verbosity": "verbose"})
    alice_v2 = _pref(key=VERBOSITY_KEY, scope="user:alice", version=2, value={"verbosity": "compact"})
    bob = _pref(key=VERBOSITY_KEY, scope="user:bob", version=9, value={"verbosity": "verbose"})
    adapter = Adapter()

    resolved = adapter.resolve(
        [alice_v1, alice_v2, bob],
        scope="user:alice",
        key=VERBOSITY_KEY,
    )
    assert len(resolved) == 1
    assert resolved[0].id == alice_v2.id
    assert resolved[0].version == 2

    bob_only = adapter.resolve([alice_v2, bob], scope="user:bob")
    assert len(bob_only) == 1
    assert bob_only[0].scope == "user:bob"


@pytest.mark.asyncio
async def test_service_resolve_uses_get_by_key_and_adapter() -> None:
    repo = FakePreferenceRepo()
    service = PreferenceService(pref_repo=repo)
    stored = _pref(key=VERBOSITY_KEY, scope="user:alice", version=3)
    await repo.save(stored)

    found = await service.resolve("user:alice", key=VERBOSITY_KEY)
    assert len(found) == 1
    assert found[0].key == VERBOSITY_KEY

    missing = await service.resolve("user:bob", key=VERBOSITY_KEY)
    assert missing == []

    listed = await service.resolve(
        "user:alice",
        preferences=[stored, _pref(key=VERBOSITY_KEY, scope="user:bob", version=1)],
    )
    assert len(listed) == 1
    assert listed[0].scope == "user:alice"


@pytest.mark.asyncio
async def test_service_resolve_without_key_or_list_is_unsupported() -> None:
    service = PreferenceService(pref_repo=FakePreferenceRepo())
    with pytest.raises(ValueError, match="list_by_scope"):
        await service.resolve("user:alice")


@pytest.mark.asyncio
async def test_extract_compact_from_natural_language() -> None:
    service = PreferenceService(pref_repo=FakePreferenceRepo())
    prefs = await service.extract(
        _evidence(
            "USER_BEHAVIOR",
            {"title": "喜欢简洁回答", "body": {"text": "喜欢简洁回答"}},
        )
    )
    assert len(prefs) == 1
    assert prefs[0].key == VERBOSITY_KEY
    assert prefs[0].value == {"verbosity": "compact"}


@pytest.mark.asyncio
async def test_synonym_compact_phrases_share_key_value() -> None:
    service = PreferenceService(pref_repo=FakePreferenceRepo())
    a = await service.extract(
        _evidence("USER_BEHAVIOR", {"title": "简洁回答", "body": {"text": "简洁回答"}})
    )
    b = await service.extract(
        _evidence("USER_BEHAVIOR", {"title": "简短回复", "body": {"text": "简短回复"}})
    )
    assert a[0].key == b[0].key == VERBOSITY_KEY
    assert a[0].value == b[0].value == {"verbosity": "compact"}


@pytest.mark.asyncio
async def test_reverse_verbose_then_compact_keeps_history() -> None:
    repo = FakePreferenceRepo()
    service = PreferenceService(pref_repo=repo)
    first = await service.extract(
        _evidence(
            "USER_BEHAVIOR",
            {"title": "喜欢详细回答", "body": {"text": "喜欢详细回答"}},
        )
    )
    second = await service.extract(
        _evidence(
            "USER_BEHAVIOR",
            {"title": "喜欢简洁回答", "body": {"text": "喜欢简洁回答"}},
        )
    )
    assert first[0].id == second[0].id
    assert first[0].value["verbosity"] == "verbose"
    assert second[0].value["verbosity"] == "compact"
    assert second[0].version == 2
    history = await service.get_history(second[0].id)
    assert [snap.version for snap in history] == [1, 2]
    assert history[0].value["verbosity"] == "verbose"
    assert history[1].value["verbosity"] == "compact"


@pytest.mark.asyncio
async def test_unknown_text_does_not_create_preference() -> None:
    service = PreferenceService(pref_repo=FakePreferenceRepo())
    prefs = await service.extract(
        _evidence(
            "USER_BEHAVIOR",
            {"title": "今天天气不错", "body": {"text": "去公园散步"}},
        )
    )
    assert prefs == []


def test_adding_rule_does_not_change_extractor_loop() -> None:
    def extra_apply(evidence: Evidence, body: dict, raw: dict):
        title = str(raw.get("title") or "")
        if "unit-test-marker" not in title:
            return None
        return {
            "category": "OP_HABIT",
            "key": "op_habit.test_extension",
            "value": {"enabled": True},
            "confidence": 0.5,
        }

    extra = Rule(
        name="unit_test_extension",
        category="OP_HABIT",
        source_types=frozenset({"USER_BEHAVIOR"}),
        apply=extra_apply,
    )
    extractor = Extractor(rules=(*default_rules(), extra))
    hits = extractor.extract(
        _evidence("USER_BEHAVIOR", {"title": "unit-test-marker", "body": {}})
    )
    assert any(item["key"] == "op_habit.test_extension" for item in hits)
    stock = Extractor().extract(
        _evidence("USER_BEHAVIOR", {"title": "unit-test-marker", "body": {}})
    )
    assert stock == []
