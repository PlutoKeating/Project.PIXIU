"""Tests for core/idgen.py — ULID prefix ID generators."""

from __future__ import annotations

from backend.foundation.core.idgen import (
    gen_conflict_id,
    gen_device_id,
    gen_entity_id,
    gen_evidence_id,
    gen_knowledge_id,
    gen_pref_id,
    gen_request_id,
    gen_sync_op_id,
)

ALL_GENERATORS = {
    gen_evidence_id: "evd_",
    gen_knowledge_id: "knw_",
    gen_pref_id: "pref_",
    gen_conflict_id: "cfl_",
    gen_device_id: "dev_",
    gen_sync_op_id: "sync_",
    gen_entity_id: "ent_",
    gen_request_id: "req_",
}


# ═══════════════════════════════════════════════════════
# Group 1: prefix correctness
# ═══════════════════════════════════════════════════════

def test_evidence_prefix():
    result = gen_evidence_id()
    assert result.startswith("evd_")
    assert len(result) == 30


def test_knowledge_prefix():
    result = gen_knowledge_id()
    assert result.startswith("knw_")
    assert len(result) == 30


def test_pref_prefix():
    result = gen_pref_id()
    assert result.startswith("pref_")
    assert len(result) == 31


def test_conflict_prefix():
    result = gen_conflict_id()
    assert result.startswith("cfl_")
    assert len(result) == 30


def test_device_prefix():
    result = gen_device_id()
    assert result.startswith("dev_")
    assert len(result) == 30


def test_sync_op_prefix():
    result = gen_sync_op_id()
    assert result.startswith("sync_")
    assert len(result) == 31


def test_entity_prefix():
    result = gen_entity_id()
    assert result.startswith("ent_")
    assert len(result) == 30


def test_request_prefix():
    result = gen_request_id()
    assert result.startswith("req_")
    assert len(result) == 30


# ═══════════════════════════════════════════════════════
# Group 2: no duplicates on consecutive generation
# ═══════════════════════════════════════════════════════

def test_no_duplicates_within_generator():
    """Call each generator 1000 times — all IDs must be unique."""
    for gen_func, prefix in ALL_GENERATORS.items():
        ids = [gen_func() for _ in range(1000)]
        assert len(set(ids)) == 1000, f"{gen_func.__name__} produced duplicates"


def test_no_duplicates_across_generators():
    """800 IDs from 8 generators all go into one set — no collisions."""
    all_ids: list[str] = []
    for gen_func in ALL_GENERATORS:
        all_ids.extend(gen_func() for _ in range(100))
    assert len(set(all_ids)) == 800, "cross-generator collision detected"


def test_id_length_consistent():
    """Every ID is exactly len(prefix) + 26 characters (prefix + _ + 26-char ULID)."""
    for gen_func, prefix in ALL_GENERATORS.items():
        result = gen_func()
        expected = len(prefix) + 26
        assert len(result) == expected, f"{gen_func.__name__} returned length {len(result)}, expected {expected}"


# ═══════════════════════════════════════════════════════
# Group 3: return type is string
# ═══════════════════════════════════════════════════════

def test_return_type_is_str():
    for gen_func in ALL_GENERATORS:
        result = gen_func()
        assert isinstance(result, str), f"{gen_func.__name__} returned {type(result)}"


def test_id_not_numeric_only():
    """ID should not be a pure digit string — ULID uses Base32 alphabet."""
    for gen_func in ALL_GENERATORS:
        result = gen_func()
        assert not result.removeprefix(
            ALL_GENERATORS[gen_func]
        ).isdigit(), f"{gen_func.__name__} ULID part is all digits"


def test_id_contains_only_alphanumeric():
    """After the prefix, only Crockford Base32 chars allowed."""
    import re

    pattern = re.compile(r"^[0-9A-HJ-NP-TV-Z]+$")
    for gen_func, prefix in ALL_GENERATORS.items():
        ulid_part = gen_func().removeprefix(prefix)
        assert pattern.match(ulid_part), f"{gen_func.__name__} has invalid chars in ULID"
