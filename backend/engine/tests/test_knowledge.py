"""Basic tests for knowledge structuring with Mock embedding."""

from __future__ import annotations

import pytest

from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.kylin import MockEmbedding
from backend.engine.mocks import (
    MockEntityRepository,
    MockEvidenceRepository,
    MockKnowledgeRepository,
)


@pytest.fixture
def knowledge_service() -> KnowledgeService:
    return KnowledgeService(
        knw_repo=MockKnowledgeRepository(),
        entity_repo=MockEntityRepository(),
        embedder=MockEmbedding(dim=32),
    )


@pytest.fixture
def ingest_service() -> IngestionService:
    return IngestionService(evidence_repo=MockEvidenceRepository())


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

    entities = await knowledge_service._entity_repo.list_entities()  # noqa: SLF001
    assert any(e.norm_name == "国家电网" for e in entities)


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


def test_mock_embedding_deterministic() -> None:
    emb = MockEmbedding(dim=8)
    a = emb.embed("hello")
    b = emb.embed("hello")
    c = emb.embed("world")
    assert a == b
    assert a != c
    assert len(a) == 8
