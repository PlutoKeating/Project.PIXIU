"""Tests for core/models.py — Pydantic data models and enums."""

from __future__ import annotations

import json
import time
from copy import deepcopy

import pytest
from pydantic import ValidationError

from backend.foundation.core.models import (
    ConflictRecord,
    ConflictResolution,
    Entity,
    Evidence,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeStatus,
    MemoryAtom,
    Preference,
    PreferenceCategory,
    PreferenceSnapshot,
    Relation,
    SourceType,
    SyncOp,
    _SCOPE_PATTERN,
    validate_id,
    validate_scope,
)

NOW = int(time.time())

# ══════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════

def _valid_evidence(**overrides) -> Evidence:
    defaults = {
        "id": "evd_01KYSVDG0739TWR7179BEYETVT",
        "source_type": SourceType.OCR,
        "scope": "user:alice",
        "created_at": NOW,
    }
    return Evidence(**(defaults | overrides))


def _valid_knowledge(**overrides) -> KnowledgeItem:
    defaults = {
        "id": "knw_01KYSVDG0739TWR7179BEYETVT",
        "kind": KnowledgeKind.FACT,
        "title": "test",
        "scope": "user:alice",
        "created_at": NOW,
        "updated_at": NOW,
    }
    return KnowledgeItem(**(defaults | overrides))


# ══════════════════════════════════════════════════════════
# Group 1: valid input — all models construct cleanly
# ══════════════════════════════════════════════════════════

def test_evidence_valid_minimal():
    e = _valid_evidence()
    assert e.source_type == SourceType.OCR
    assert e.raw == {}
    assert e.sensitivity == 0


def test_evidence_valid_full():
    e = Evidence(
        id="evd_01KYSVDG0739TWR7179BEYETVT",
        source_type=SourceType.TOOL_RESULT,
        raw={"key": "val"},
        quality_score=0.95,
        sensitivity=3,
        scope="shared:home",
        created_at=NOW,
    )
    assert e.quality_score == 0.95
    assert e.raw["key"] == "val"


def test_evidence_source_type_from_str():
    """String values that match enum members should auto-coerce."""
    e = Evidence(
        id="evd_01KYSVDG0739TWR7179BEYETVT",
        source_type="MANUAL_CONFIG",
        scope="user:bob",
        created_at=NOW,
    )
    assert e.source_type == SourceType.MANUAL_CONFIG


def test_knowledge_valid():
    k = _valid_knowledge()
    assert k.kind == KnowledgeKind.FACT
    assert k.status == KnowledgeStatus.ACTIVE
    assert k.version == 1
    assert k.evidence_ids == []
    assert k.entities == []


def test_knowledge_with_optional():
    k = KnowledgeItem(
        id="knw_01KYSVDG0739TWR7179BEYETVT",
        kind="CASE",
        title="test",
        scope="shared:lab",
        created_at=NOW,
        updated_at=NOW,
        embedding_ref="vec_abc",
    )
    assert k.embedding_ref == "vec_abc"
    assert k.kind == KnowledgeKind.CASE


def test_preference_valid():
    p = Preference(
        id="pref_01KYSVDG0739TWR7179BEYETVT",
        category=PreferenceCategory.OP_HABIT,
        key="output_style",
        scope="user:alice",
        created_at=NOW,
        updated_at=NOW,
    )
    assert p.category == PreferenceCategory.OP_HABIT


def test_entity_valid():
    e = Entity(
        id="ent_01KYSVDG0739TWR7179BEYETVT",
        name="国家电网",
        norm_name="国家电网",
        type="ORG",
    )
    assert e.norm_name == "国家电网"


def test_relation_valid():
    r = Relation(src="ent_a", dst="ent_b", type="BELONG_TO")
    assert r.type == "BELONG_TO"


def test_conflict_valid():
    c = ConflictRecord(
        id="cfl_01KYSVDG0739TWR7179BEYETVT",
        target_knowledge="knw_x",
        field="body.amount",
        old_value=100,
        new_value=200,
        created_at=NOW,
    )
    assert c.resolution == ConflictResolution.NEW_WINS


def test_conflict_from_str():
    c = ConflictRecord(
        id="cfl_01KYSVDG0739TWR7179BEYETVT",
        target_knowledge="knw_x",
        field="body.amount",
        resolution="MERGE",
        created_at=NOW,
    )
    assert c.resolution == ConflictResolution.MERGE


def test_memory_atom_valid():
    m = MemoryAtom(
        answer="answer text",
        source_evidence=["evd_a"],
        source_knowledge="knw_b",
        confidence=0.93,
        latency_ms=210,
    )
    assert m.confidence == 0.93
    assert m.latency_ms == 210


def test_sync_op_valid():
    s = SyncOp(
        op_id="sync_01KYSVDG0739TWR7179BEYETVT",
        entity="knowledge",
        payload={"title": "x"},
        ts=NOW,
    )
    assert s.entity == "knowledge"


# ══════════════════════════════════════════════════════════
# Group 2: invalid enum values rejected
# ══════════════════════════════════════════════════════════

def test_evidence_invalid_source_type():
    with pytest.raises(ValidationError) as exc:
        Evidence(
            id="evd_01KYSVDG0739TWR7179BEYETVT",
            source_type="INVALID",
            scope="user:a",
            created_at=NOW,
        )
    assert "source_type" in str(exc.value)


def test_knowledge_invalid_kind():
    with pytest.raises(ValidationError):
        _valid_knowledge(kind="BAD_KIND")


def test_knowledge_invalid_status():
    with pytest.raises(ValidationError):
        _valid_knowledge(status="DELETED")


def test_preference_invalid_category():
    with pytest.raises(ValidationError):
        Preference(
            id="pref_01KYSVDG0739TWR7179BEYETVT",
            category="INVALID",
            key="x",
            scope="user:a",
            created_at=NOW,
            updated_at=NOW,
        )


def test_conflict_invalid_resolution():
    with pytest.raises(ValidationError):
        ConflictRecord(
            id="cfl_01KYSVDG0739TWR7179BEYETVT",
            target_knowledge="knw_x",
            field="x",
            resolution="DELETE",
            created_at=NOW,
        )


# ══════════════════════════════════════════════════════════
# Group 3: range violations
# ══════════════════════════════════════════════════════════

def test_evidence_quality_score_out_of_range_high():
    with pytest.raises(ValidationError):
        _valid_evidence(quality_score=1.5)


def test_evidence_quality_score_out_of_range_low():
    with pytest.raises(ValidationError):
        _valid_evidence(quality_score=-0.1)


def test_evidence_sensitivity_out_of_range():
    with pytest.raises(ValidationError):
        _valid_evidence(sensitivity=11)

    with pytest.raises(ValidationError):
        _valid_evidence(sensitivity=-1)


def test_preference_confidence_out_of_range():
    with pytest.raises(ValidationError):
        Preference(
            id="pref_01KYSVDG0739TWR7179BEYETVT",
            category=PreferenceCategory.OP_HABIT,
            key="x",
            scope="user:a",
            confidence=1.5,
            created_at=NOW,
            updated_at=NOW,
        )


def test_memory_atom_confidence_range():
    with pytest.raises(ValidationError):
        MemoryAtom(answer="x", confidence=1.5)

    MemoryAtom(answer="x", confidence=1.0)
    MemoryAtom(answer="x", confidence=0.0)


def test_memory_atom_latency_negative():
    with pytest.raises(ValidationError):
        MemoryAtom(answer="x", latency_ms=-1)


def test_knowledge_version_non_positive():
    with pytest.raises(ValidationError):
        _valid_knowledge(version=0)

    with pytest.raises(ValidationError):
        _valid_knowledge(version=-1)


# ══════════════════════════════════════════════════════════
# Group 4: default value isolation (mutable defaults)
# ══════════════════════════════════════════════════════════

def test_evidence_raw_is_isolated():
    e1 = _valid_evidence(raw={"a": 1})
    e2 = _valid_evidence(raw={"b": 2})
    assert "b" not in e1.raw
    assert "a" not in e2.raw


def test_knowledge_body_is_isolated():
    k1 = _valid_knowledge(body={"a": 1})
    k2 = _valid_knowledge(body={"b": 2})
    assert "b" not in k1.body
    assert "a" not in k2.body


def test_knowledge_entities_is_isolated():
    k1 = _valid_knowledge(entities=["x"])
    k2 = _valid_knowledge(entities=["y"])
    assert len(k1.entities) == 1
    assert len(k2.entities) == 1


def test_knowledge_evidence_ids_is_isolated():
    k1 = _valid_knowledge(evidence_ids=["evd_a"])
    k2 = _valid_knowledge(evidence_ids=["evd_b"])
    assert len(k1.evidence_ids) == 1
    assert len(k2.evidence_ids) == 1


def test_memory_atom_evidence_list_is_isolated():
    m1 = MemoryAtom(answer="x", source_evidence=["a"])
    m2 = MemoryAtom(answer="y", source_evidence=["b"])
    assert m1.source_evidence == ["a"]
    assert m2.source_evidence == ["b"]


def test_sync_op_payload_is_isolated():
    s1 = SyncOp(op_id="sync_01KYSVDG0739TWR7179BEYETVT", entity="k", payload={"a": 1}, ts=NOW)
    s2 = SyncOp(op_id="sync_01KYSVDG0739TWR7179BEYETVU", entity="k", payload={"b": 2}, ts=NOW)
    assert "b" not in s1.payload
    assert "a" not in s2.payload


def test_sync_op_vclock_is_isolated():
    s1 = SyncOp(
        op_id="sync_01KYSVDG0739TWR7179BEYETVT", entity="k", vclock={"a": 1}, ts=NOW
    )
    s2 = SyncOp(
        op_id="sync_01KYSVDG0739TWR7179BEYETVU", entity="k", vclock={"b": 2}, ts=NOW
    )
    assert "b" not in s1.vclock
    assert "a" not in s2.vclock


# ══════════════════════════════════════════════════════════
# Group 5: scope validation
# ══════════════════════════════════════════════════════════

def test_scope_valid_user():
    e = _valid_evidence(scope="user:alice")
    assert e.scope == "user:alice"


def test_scope_valid_shared():
    e = _valid_evidence(scope="shared:home-office")
    assert e.scope == "shared:home-office"


def test_scope_invalid_no_prefix():
    with pytest.raises(ValidationError):
        _valid_evidence(scope="alice")


def test_scope_invalid_prefix():
    with pytest.raises(ValidationError):
        _valid_evidence(scope="admin:alice")


def test_scope_invalid_format():
    with pytest.raises(ValidationError):
        _valid_evidence(scope="user:")


# ══════════════════════════════════════════════════════════
# Group 6: ID validation
# ══════════════════════════════════════════════════════════

def test_id_validator_accepts_correct():
    assert validate_id("evidence", "evd_01KYSVDG0739TWR7179BEYETVT") == "evd_01KYSVDG0739TWR7179BEYETVT"
    assert validate_id("knowledge", "knw_AAAAAAAAAAAAAAAAAAAAAAAAAA") == "knw_AAAAAAAAAAAAAAAAAAAAAAAAAA"


def test_id_validator_rejects_wrong_prefix():
    with pytest.raises(ValueError):
        validate_id("evidence", "knw_01KYSVDG0739TWR7179BEYETVT")


def test_id_validator_rejects_short():
    with pytest.raises(ValueError):
        validate_id("evidence", "evd_short")


def test_evidence_bad_id_rejected():
    with pytest.raises(ValidationError):
        _valid_evidence(id="bad_id")


def test_entity_bad_id_rejected():
    with pytest.raises(ValidationError):
        Entity(id="bad", name="x", norm_name="x", type="y")


def test_conflict_bad_id_rejected():
    with pytest.raises(ValidationError):
        ConflictRecord(
            id="bad",
            target_knowledge="knw_x",
            field="x",
            created_at=NOW,
        )


def test_sync_op_bad_id_rejected():
    with pytest.raises(ValidationError):
        SyncOp(op_id="bad", entity="k", ts=NOW)


# ══════════════════════════════════════════════════════════
# Group 7: serialization / deserialization
# ══════════════════════════════════════════════════════════

def test_evidence_serialize_roundtrip():
    original = _valid_evidence(
        source_type=SourceType.TOOL_RESULT,
        raw={"items": [1, 2]},
        quality_score=0.88,
        sensitivity=2,
    )
    dumped = original.model_dump()
    reloaded = Evidence(**dumped)
    assert reloaded.source_type == original.source_type
    assert reloaded.source_type == SourceType.TOOL_RESULT
    assert reloaded.raw == {"items": [1, 2]}
    assert reloaded.quality_score == 0.88


def test_evidence_serialize_json():
    e = _valid_evidence(source_type=SourceType.OCR, raw={"a": 1})
    data = e.model_dump_json()
    parsed = json.loads(data)
    assert parsed["source_type"] == "OCR"
    assert parsed["quality_score"] == 0.0


def test_knowledge_serialize_roundtrip():
    original = _valid_knowledge(
        kind=KnowledgeKind.TEMPLATE,
        status=KnowledgeStatus.SUPERSEDED,
        version=4,
        evidence_ids=["evd_a", "evd_b"],
    )
    reloaded = KnowledgeItem(**original.model_dump())
    assert reloaded.kind == KnowledgeKind.TEMPLATE
    assert reloaded.status == KnowledgeStatus.SUPERSEDED
    assert reloaded.evidence_ids == ["evd_a", "evd_b"]


def test_preference_snapshot_serialize():
    snap = PreferenceSnapshot(version=2, value={"compact": True}, updated_at=NOW)
    dumped = snap.model_dump()
    assert dumped == {"version": 2, "value": {"compact": True}, "updated_at": NOW}


def test_conflict_serialize_none_values():
    """old_value=None, new_value=None should survive round-trip."""
    c = ConflictRecord(
        id="cfl_01KYSVDG0739TWR7179BEYETVT",
        target_knowledge="knw_x",
        field="x",
        created_at=NOW,
    )
    reloaded = ConflictRecord(**c.model_dump())
    assert reloaded.old_value is None
    assert reloaded.new_value is None


def test_memory_atom_json_format():
    m = MemoryAtom(
        answer="answer",
        source_evidence=["evd_01KYSVDG0739TWR7179BEYETVT"],
        source_knowledge="knw_01KYSVDG0739TWR7179BEYETVT",
        confidence=0.93,
        latency_ms=210,
    )
    data = json.loads(m.model_dump_json())
    assert data["answer"] == "answer"
    assert data["confidence"] == 0.93
    assert data["latency_ms"] == 210


def test_sync_op_serialize_roundtrip():
    original = SyncOp(
        op_id="sync_01KYSVDG0739TWR7179BEYETVT",
        entity="preference",
        payload={"key": "value"},
        vclock={"dev_a": 5},
        ts=NOW,
    )
    reloaded = SyncOp(**original.model_dump())
    assert reloaded.entity == "preference"
    assert reloaded.payload == {"key": "value"}
    assert reloaded.vclock == {"dev_a": 5}


# ══════════════════════════════════════════════════════════
# Group 8: enum value correctness
# ══════════════════════════════════════════════════════════

def test_source_type_enum_values():
    assert SourceType.OCR.value == "OCR"
    assert SourceType.TOOL_RESULT.value == "TOOL_RESULT"
    assert SourceType.USER_BEHAVIOR.value == "USER_BEHAVIOR"
    assert SourceType.MANUAL_CONFIG.value == "MANUAL_CONFIG"


def test_knowledge_kind_enum_values():
    assert set(KnowledgeKind) == {KnowledgeKind.FACT, KnowledgeKind.WORKFLOW, KnowledgeKind.CASE, KnowledgeKind.TEMPLATE}


def test_knowledge_status_enum_values():
    assert set(KnowledgeStatus) == {KnowledgeStatus.ACTIVE, KnowledgeStatus.SUPERSEDED, KnowledgeStatus.FORGOTTEN}


def test_preference_category_enum_values():
    assert set(PreferenceCategory) == {
        PreferenceCategory.OP_HABIT,
        PreferenceCategory.OUTPUT_STYLE,
        PreferenceCategory.SECURITY_POLICY,
    }


def test_conflict_resolution_enum_values():
    assert set(ConflictResolution) == {
        ConflictResolution.NEW_WINS,
        ConflictResolution.MERGE,
        ConflictResolution.MANUAL,
    }


# ══════════════════════════════════════════════════════════
# Group 9: scope regex unit tests
# ══════════════════════════════════════════════════════════

def test_scope_regex_accepts_valid():
    assert _SCOPE_PATTERN.match("user:alice")
    assert _SCOPE_PATTERN.match("shared:home-office")
    assert _SCOPE_PATTERN.match("shared:lab_01")


def test_scope_regex_rejects_invalid():
    assert not _SCOPE_PATTERN.match("admin:alice")
    assert not _SCOPE_PATTERN.match("user:")
    assert not _SCOPE_PATTERN.match(":alice")
    assert not _SCOPE_PATTERN.match("user")


# ══════════════════════════════════════════════════════════
# Group 10: no database logic leakage
# ══════════════════════════════════════════════════════════

def test_models_have_no_db_fields():
    """Models should not contain DB-specific fields like rowid or table name."""
    for model_cls in [
        Evidence, KnowledgeItem, Preference, Entity, Relation,
        ConflictRecord, MemoryAtom, SyncOp,
    ]:
        fields = set(model_cls.model_fields.keys())
        for banned in ("table_name", "rowid", "db", "connection", "cursor"):
            assert banned not in fields, f"{model_cls.__name__} leaks DB field: {banned}"


# ══════════════════════════════════════════════════════════
# Group 11: mapping type stays flexible
# ══════════════════════════════════════════════════════════

def test_raw_and_body_accept_arbitrary_dict():
    """raw and body fields should accept arbitrary nested dicts."""
    e = _valid_evidence(raw={"nested": {"deep": [1, 2, 3]}})
    assert e.raw["nested"]["deep"] == [1, 2, 3]

    k = _valid_knowledge(body={"summary": "x", "tags": ["a", "b"]})
    assert k.body["tags"] == ["a", "b"]


def test_old_new_value_accept_any():
    """ConflictRecord.old_value and new_value accept any type."""
    c = ConflictRecord(
        id="cfl_01KYSVDG0739TWR7179BEYETVT",
        target_knowledge="knw_x",
        field="x",
        old_value={"complex": [1, None, "s"]},
        new_value=[1, 2, 3],
        created_at=NOW,
    )
    assert c.old_value == {"complex": [1, None, "s"]}
    assert c.new_value == [1, 2, 3]
