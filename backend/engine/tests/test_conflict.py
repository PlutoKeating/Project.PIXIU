"""Basic tests for conflict arbitration."""

from __future__ import annotations

import pytest
import pytest_asyncio

from backend.engine.conflict import ConflictService
from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.tests.fakes import StubTextEmbedder
from backend.foundation.storage.repository import (
    SqliteConflictRepo,
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
)


@pytest_asyncio.fixture
async def repos(db) -> dict:
    knw = SqliteKnowledgeRepo(db)
    return {
        "knw": knw,
        "entity": SqliteEntityRepo(db),
        "conflict": SqliteConflictRepo(db),
        "evidence": SqliteEvidenceRepo(db),
    }


@pytest.mark.asyncio
async def test_arbitrate_amount_conflict(repos: dict) -> None:
    ingest = IngestionService(evidence_repo=repos["evidence"])
    knowledge = KnowledgeService(
        knw_repo=repos["knw"],
        entity_repo=repos["entity"],
        embedder=StubTextEmbedder(dim=16),
    )
    conflict = ConflictService(
        knw_repo=repos["knw"],
        conflict_repo=repos["conflict"],
    )

    ev1 = await ingest.ingest(
        "OCR",
        {
            "title": "2026年4月家庭支出清单",
            "body": {
                "items": [
                    {"category": "水电燃气", "vendor": "新奥燃气", "amount": 156}
                ]
            },
        },
        scope="shared:home",
    )
    old_item = await knowledge.structure(ev1)

    ev2 = await ingest.ingest(
        "OCR",
        {
            "title": "2026年4月家庭支出清单",
            "body": {
                "items": [
                    {"category": "水电燃气", "vendor": "新奥燃气", "amount": 186}
                ]
            },
        },
        scope="shared:home",
    )
    new_item = await knowledge.structure(ev2)

    record = await conflict.arbitrate(new_item)
    assert record is not None
    assert record.resolution == "NEW_WINS"
    assert record.old_value == 156
    assert record.new_value == 186
    assert "amount" in record.field

    stored_old = await repos["knw"].get(old_item.id)
    assert stored_old is not None
    assert stored_old.status == "SUPERSEDED"

    stored_new = await repos["knw"].get(new_item.id)
    assert stored_new is not None
    assert stored_new.status == "ACTIVE"
    assert stored_new.version >= 2


@pytest.mark.asyncio
async def test_arbitrate_no_conflict_different_title(repos: dict) -> None:
    ingest = IngestionService(evidence_repo=repos["evidence"])
    knowledge = KnowledgeService(
        knw_repo=repos["knw"],
        entity_repo=repos["entity"],
        embedder=StubTextEmbedder(dim=16),
    )
    conflict = ConflictService(
        knw_repo=repos["knw"],
        conflict_repo=repos["conflict"],
    )

    ev1 = await ingest.ingest(
        "OCR",
        {"title": "清单A", "body": {"items": [{"amount": 1}]}},
        scope="user:alice",
    )
    await knowledge.structure(ev1)

    ev2 = await ingest.ingest(
        "OCR",
        {"title": "清单B", "body": {"items": [{"amount": 2}]}},
        scope="user:alice",
    )
    new_item = await knowledge.structure(ev2)
    record = await conflict.arbitrate(new_item)
    assert record is None
