"""Basic tests for preference extraction and versioning."""

from __future__ import annotations

import pytest

from backend.engine.ingest import IngestionService
from backend.engine.mocks import MockEvidenceRepository, MockPreferenceRepository
from backend.engine.preference import PreferenceService


@pytest.fixture
def pref_service() -> PreferenceService:
    return PreferenceService(pref_repo=MockPreferenceRepository())


@pytest.fixture
def ingest_service() -> IngestionService:
    return IngestionService(evidence_repo=MockEvidenceRepository())


@pytest.mark.asyncio
async def test_extract_op_habit_from_behavior(
    pref_service: PreferenceService, ingest_service: IngestionService
) -> None:
    evidence = await ingest_service.ingest(
        "USER_BEHAVIOR",
        {"title": "hotkeys", "events": [{"action": "hotkey", "key": "Ctrl+Space"}]},
        scope="user:alice",
    )
    prefs = await pref_service.extract(evidence)
    assert len(prefs) >= 1
    assert prefs[0].category == "OP_HABIT"
    assert prefs[0].key == "op_habit.prefer_hotkey"
    assert prefs[0].value.get("enabled") is True


@pytest.mark.asyncio
async def test_extract_output_style_and_versioning(
    pref_service: PreferenceService, ingest_service: IngestionService
) -> None:
    evidence = await ingest_service.ingest(
        "MANUAL_CONFIG",
        {"key": "output_style.compact", "enabled": True},
        scope="user:alice",
    )
    first = await pref_service.extract(evidence)
    assert len(first) == 1
    pref_id = first[0].id
    assert first[0].version == 1

    evidence2 = await ingest_service.ingest(
        "MANUAL_CONFIG",
        {"key": "output_style.compact", "enabled": True, "detail_level": "high"},
        scope="user:alice",
    )
    second = await pref_service.extract(evidence2)
    assert second[0].id == pref_id
    assert second[0].version == 2

    history = await pref_service.get_history(pref_id)
    assert len(history) >= 2
    assert history[0].version == 1
    assert history[-1].version == 2


@pytest.mark.asyncio
async def test_extract_security_from_ocr_finance(
    pref_service: PreferenceService, ingest_service: IngestionService
) -> None:
    evidence = await ingest_service.ingest(
        "OCR",
        {
            "title": "账单",
            "body": {"items": [{"vendor": "国家电网", "amount": 210}]},
        },
        scope="user:alice",
    )
    prefs = await pref_service.extract(evidence)
    assert any(p.category == "SECURITY_POLICY" for p in prefs)
