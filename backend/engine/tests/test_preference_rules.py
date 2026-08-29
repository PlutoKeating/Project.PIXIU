"""Preference rule behavior tests — evaluation evidence-shape alignment (B3-2).

Locks the acceptance contract for the reference-v1 preference corpus
(backend/foundation/eval/reference.py:119-123): every rotated (category, key)
pair must extract to exactly the expected ``category:key`` label through the
real ingestion → extract pipeline, using the same evidence shape the capture
script feeds (backend/scripts/capture_eval_predictions.py:135-140):

- OP_HABIT        → source_type=USER_BEHAVIOR, raw={"title": key, "key": key, "enabled": True}
- OUTPUT_STYLE    → source_type=MANUAL_CONFIG, raw={"title": key, "key": key, "enabled": True}
- SECURITY_POLICY → source_type=MANUAL_CONFIG, raw={"title": key, "key": key, "enabled": True}
"""

from __future__ import annotations

import pytest

from backend.engine.ingest import IngestionService
from backend.engine.preference import PreferenceService
from backend.engine.preference.extractor import Extractor
from backend.engine.preference.rules import (
    _canonical_from_key,
    _security_from_config,
    _style_from_config,
)
from backend.foundation.core.idgen import gen_evidence_id
from backend.foundation.core.models import Evidence
from backend.foundation.storage.repository import (
    SqliteEvidenceRepo,
    SqlitePreferenceRepo,
)

# 评测语料轮转的三类 (category, key) —— 与 reference.py 期望标签一致。
EVAL_PREFERENCE_SPECS: tuple[tuple[str, str], ...] = (
    ("OP_HABIT", "tool.selection.frequent"),
    ("OUTPUT_STYLE", "output_style.compact"),
    ("SECURITY_POLICY", "security.confirm_sensitive"),
)

EVAL_SOURCE_BY_CATEGORY: dict[str, str] = {
    "OP_HABIT": "USER_BEHAVIOR",
    "OUTPUT_STYLE": "MANUAL_CONFIG",
    "SECURITY_POLICY": "MANUAL_CONFIG",
}


def _eval_raw(key: str) -> dict:
    """capture_eval_predictions.py:139-140 的评测 evidence 形状。"""
    return {"title": key, "key": key, "enabled": True}


def _evidence(source_type: str, raw: dict, *, sensitivity: int = 0) -> Evidence:
    return Evidence(
        id=gen_evidence_id(),
        source_type=source_type,
        raw=raw,
        quality_score=0.9,
        sensitivity=sensitivity,
        scope="user:eval",
        created_at=1_700_000_000,
    )


def _persist_raw(title: str, body: dict) -> dict:
    """ingest 后 evidence.raw 的形状（connector + cleaner + persist_raw）。"""
    return {"title": title, "body": body, "entities": [], "relations": []}


@pytest.mark.asyncio
async def test_eval_corpus_rotation_extracts_exact_labels(db) -> None:
    """15 例轮转全部精确命中 {category}:{key}（preference_accuracy 契约）。"""
    ingest = IngestionService(evidence_repo=SqliteEvidenceRepo(db))
    service = PreferenceService(pref_repo=SqlitePreferenceRepo(db))
    for index in range(15):
        category, key = EVAL_PREFERENCE_SPECS[index % len(EVAL_PREFERENCE_SPECS)]
        source = EVAL_SOURCE_BY_CATEGORY[category]
        evidence = await ingest.ingest(source, _eval_raw(key), "user:eval")
        extracted = await service.extract(evidence)
        labels = [f"{p.category.value}:{p.key}" for p in extracted]
        assert labels == [f"{category}:{key}"], (
            f"preference case {index + 1} ({category}:{key}) misaligned: {labels}"
        )


@pytest.mark.asyncio
async def test_eval_keys_version_same_row_not_fork(db) -> None:
    """同一 canonical key 重复采集走版本升版，不新建行（key 稳定铁律）。"""
    ingest = IngestionService(evidence_repo=SqliteEvidenceRepo(db))
    service = PreferenceService(pref_repo=SqlitePreferenceRepo(db))
    evidence = await ingest.ingest(
        "USER_BEHAVIOR", _eval_raw("tool.selection.frequent"), "user:eval"
    )
    first = (await service.extract(evidence))[0]
    second = (await service.extract(evidence))[0]
    assert first.id == second.id
    assert first.key == second.key == "tool.selection.frequent"
    assert second.version == 2
    history = await service.get_history(first.id)
    assert [snap.version for snap in history] == [1, 2]


def test_canonical_from_key_maps_tool_selection_frequent() -> None:
    raw = _persist_raw("tool.selection.frequent", {"events": []})
    hit = _canonical_from_key(_evidence("USER_BEHAVIOR", raw), raw["body"], raw)
    assert hit is not None
    assert (hit["category"], hit["key"]) == ("OP_HABIT", "tool.selection.frequent")


def test_style_from_config_exact_key_keeps_identity() -> None:
    body = {"key": "output_style.compact", "enabled": True}
    raw = _persist_raw("output_style.compact", body)
    hit = _style_from_config(_evidence("MANUAL_CONFIG", raw), body, raw)
    assert hit is not None
    assert (hit["category"], hit["key"]) == ("OUTPUT_STYLE", "output_style.compact")
    assert hit["value"]["enabled"] is True


def test_security_from_config_exact_key() -> None:
    body = {"key": "security.confirm_sensitive", "enabled": True}
    raw = _persist_raw("security.confirm_sensitive", body)
    hit = _security_from_config(_evidence("MANUAL_CONFIG", raw), body, raw)
    assert hit is not None
    assert (hit["category"], hit["key"]) == (
        "SECURITY_POLICY",
        "security.confirm_sensitive",
    )


def test_security_from_config_case_insensitive_prefix() -> None:
    """前缀判断与触发判断一致（casefold）：大写变体也落到 canonical key。"""
    body = {"key": "SECURITY.confirm_sensitive", "enabled": True}
    raw = _persist_raw("SECURITY.confirm_sensitive", body)
    hit = _security_from_config(_evidence("MANUAL_CONFIG", raw), body, raw)
    assert hit is not None
    assert hit["key"] == "security.confirm_sensitive"


def test_security_from_config_unrelated_key_returns_none() -> None:
    body = {"key": "privacy.block_clipboard", "enabled": True}
    raw = _persist_raw("privacy.block_clipboard", body)
    assert (
        _security_from_config(_evidence("MANUAL_CONFIG", raw), body, raw) is None
    )


def test_extractor_dedupes_by_key_last_rule_wins() -> None:
    """同 key 多规则命中：found 按 key 去重，不产生重复标签。"""
    extractor = Extractor()
    body = {"key": "output_style.compact", "enabled": True}
    raw = _persist_raw("output_style.compact", body)
    hits = extractor.extract(_evidence("MANUAL_CONFIG", raw))
    keys = [h["key"] for h in hits]
    assert keys.count("output_style.compact") == 1
