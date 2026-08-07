"""Basic tests for knowledge structuring."""

from __future__ import annotations

import pytest
import pytest_asyncio

from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.tests.fakes import StubTextEmbedder
from backend.foundation.storage.repository import (
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
)


@pytest_asyncio.fixture
async def knowledge_service(db) -> KnowledgeService:
    return KnowledgeService(
        knw_repo=SqliteKnowledgeRepo(db),
        entity_repo=SqliteEntityRepo(db),
        embedder=StubTextEmbedder(dim=32),
    )


@pytest_asyncio.fixture
async def ingest_service(db) -> IngestionService:
    return IngestionService(evidence_repo=SqliteEvidenceRepo(db))


@pytest.mark.asyncio
async def test_structure_ocr_to_fact(
    knowledge_service: KnowledgeService, ingest_service: IngestionService
) -> None:
    evidence = await ingest_service.ingest(
        "OCR",
        {
            "title": "2026年4月家庭支出清单",
            "body": {
                "items": [
                    {
                        "category": "水电燃气",
                        "vendor": "国家电网",
                        "amount": 210.0,
                    }
                ]
            },
        },
        scope="shared:home",
    )
    item = await knowledge_service.structure(evidence)

    assert item.id.startswith("knw_")
    assert item.kind == "FACT"
    assert item.status == "ACTIVE"
    assert evidence.id in item.evidence_ids
    assert item.embedding_ref == f"vec_{item.id}"
    assert "国家电网" in item.entities

    stored = await knowledge_service._knw_repo.get(item.id)  # noqa: SLF001
    assert stored is not None

    found = await knowledge_service._entity_repo.find_entity_by_name("国家电网")  # noqa: SLF001
    assert found is not None
    assert found.norm_name == "国家电网"


@pytest.mark.asyncio
async def test_structure_workflow_kind(
    knowledge_service: KnowledgeService, ingest_service: IngestionService
) -> None:
    evidence = await ingest_service.ingest(
        "TOOL_RESULT",
        {
            "title": "报销流程",
            "body": {"steps": ["填写报销单", "上传发票", "主管审批"]},
        },
        scope="user:alice",
    )
    item = await knowledge_service.structure(evidence)
    assert item.kind == "WORKFLOW"


def test_stub_embedder_deterministic() -> None:
    emb = StubTextEmbedder(dim=8)
    a = emb.embed("hello")
    b = emb.embed("hello")
    c = emb.embed("world")
    assert a == b
    assert a != c
    assert len(a) == 8
