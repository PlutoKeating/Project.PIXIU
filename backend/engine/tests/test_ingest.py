"""Basic tests for ingest pipeline."""

from __future__ import annotations

import pytest
import pytest_asyncio

from backend.engine.ingest import IngestionService
from backend.engine.ingest.cleaner import Cleaner
from backend.engine.ingest.normalizer import Normalizer
from backend.engine.ingest.quality import Quality, QualityError
from backend.foundation.storage.repository import SqliteEvidenceRepo


@pytest_asyncio.fixture
async def service(db) -> IngestionService:
    return IngestionService(evidence_repo=SqliteEvidenceRepo(db))


@pytest.mark.asyncio
async def test_ingest_ocr_expense_list(service: IngestionService) -> None:
    raw = {
        "title": "2026年4月家庭支出清单",
        "body": {
            "items": [
                {
                    "category": "水电燃气",
                    "vendor": "国家电网",
                    "amount": 210.0,
                    "date": "2026-04-10",
                    "tags": ["电费"],
                },
                {
                    "category": "水电燃气",
                    "vendor": "国网",
                    "amount": 0,
                    "date": None,
                },
            ]
        },
        "entities": ["国家电网公司"],
        "relations": [],
    }
    evidence = await service.ingest("OCR", raw, scope="user:alice")

    assert evidence.id.startswith("evd_")
    assert evidence.source_type == "OCR"
    assert evidence.scope == "user:alice"
    assert 0.0 <= evidence.quality_score <= 1.0
    assert evidence.quality_score > 0.5
    assert evidence.raw["title"] == "2026年4月家庭支出清单"
    # Alias normalized
    assert "国家电网" in evidence.raw["entities"]
    # BELONG_TO auto from OCR connector + normalize
    assert any(r.get("type") == "BELONG_TO" for r in evidence.raw["relations"])

    stored = await service._repo.get(evidence.id)  # noqa: SLF001
    assert stored is not None
    assert stored.id == evidence.id


@pytest.mark.asyncio
async def test_ingest_tool_result(service: IngestionService) -> None:
    evidence = await service.ingest(
        "TOOL_RESULT",
        {"tool_name": "file_search", "hits": [{"path": "/tmp/a.txt"}]},
        scope="shared:home",
    )
    assert evidence.source_type == "TOOL_RESULT"
    assert evidence.raw["title"] == "file_search"
    assert "hits" in evidence.raw["body"]


@pytest.mark.asyncio
async def test_ingest_user_behavior(service: IngestionService) -> None:
    evidence = await service.ingest(
        "USER_BEHAVIOR",
        {
            "title": "shortcut_usage",
            "events": [
                {"action": "hotkey", "key": "Ctrl+Space"},
                {"action": "hotkey", "key": "Ctrl+Space"},
            ],
        },
        scope="user:alice",
    )
    assert evidence.source_type == "USER_BEHAVIOR"
    # Deduped identical events
    assert len(evidence.raw["body"]["events"]) == 1


@pytest.mark.asyncio
async def test_ingest_manual_config(service: IngestionService) -> None:
    evidence = await service.ingest(
        "MANUAL_CONFIG",
        {"key": "output_style.compact", "enabled": True},
        scope="user:alice",
    )
    assert evidence.source_type == "MANUAL_CONFIG"
    assert evidence.raw["body"]["enabled"] is True


@pytest.mark.asyncio
async def test_ingest_rejects_unknown_source(service: IngestionService) -> None:
    with pytest.raises(ValueError, match="unsupported source_type"):
        await service.ingest("UNKNOWN", {"title": "x"}, scope="user:alice")


def test_cleaner_drops_noise() -> None:
    cleaned = Cleaner().clean(
        {"title": "t", "body": {"a": None, "b": "", "c": 1}, "entities": ["x", "x"]}
    )
    assert cleaned["body"] == {"c": 1}
    assert cleaned["entities"] == ["x"]
    assert "_content_hash" in cleaned


def test_normalizer_entity_alias() -> None:
    out = Normalizer().normalize(
        {
            "title": " t ",
            "body": {},
            "entities": ["国网"],
            "relations": [{"from": "国网", "to": "水电燃气", "type": "belong_to"}],
        }
    )
    assert out["title"] == "t"
    assert out["entities"] == ["国家电网"]
    assert out["relations"][0]["from"] == "国家电网"
    assert out["relations"][0]["type"] == "BELONG_TO"


def test_quality_requires_body() -> None:
    q = Quality()
    with pytest.raises(QualityError):
        q.score({"title": "only"}, "OCR")
