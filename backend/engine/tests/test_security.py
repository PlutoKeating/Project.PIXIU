"""Basic tests for security detector and forget."""

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
from backend.engine.security import SecurityService


@pytest.fixture
def security() -> SecurityService:
    return SecurityService(
        knw_repo=MockKnowledgeRepository(),
        entity_repo=MockEntityRepository(),
    )


@pytest.mark.asyncio
async def test_detect_id_card_high(security: SecurityService) -> None:
    score = await security.detect_sensitivity(
        {"note": "身份证号 110101199001011234"}
    )
    assert score == 3


@pytest.mark.asyncio
async def test_detect_phone_mid(security: SecurityService) -> None:
    score = await security.detect_sensitivity({"phone": "13812345678"})
    assert score == 2


@pytest.mark.asyncio
async def test_detect_clean(security: SecurityService) -> None:
    score = await security.detect_sensitivity({"title": "普通笔记", "body": {}})
    assert score == 0


@pytest.mark.asyncio
async def test_forget_pending_then_confirm() -> None:
    evidence_repo = MockEvidenceRepository()
    knw_repo = MockKnowledgeRepository()
    entity_repo = MockEntityRepository()

    ingest = IngestionService(evidence_repo=evidence_repo)
    knowledge = KnowledgeService(
        knw_repo=knw_repo,
        entity_repo=entity_repo,
        embedder=MockEmbedding(dim=16),
    )
    security = SecurityService(knw_repo=knw_repo, entity_repo=entity_repo)

    evidence = await ingest.ingest(
        "OCR",
        {
            "title": "2026年4月家庭支出清单",
            "body": {"items": [{"vendor": "国家电网", "amount": 210}]},
        },
        scope="user:alice",
    )
    item = await knowledge.structure(evidence)

    pending = await security.forget("忘记那张4月支出清单", confirm=False)
    assert pending.status == "pending"
    assert any(t["id"] == item.id for t in pending.targets)
    assert pending.cascade.get("evidence_count", 0) >= 1

    still = await knw_repo.get(item.id)
    assert still is not None and still.status == "ACTIVE"

    done = await security.forget("忘记那张4月支出清单", confirm=True)
    assert done.status == "forgotten"
    assert item.id in done.forgotten_ids

    forgotten = await knw_repo.get(item.id)
    assert forgotten is not None and forgotten.status == "FORGOTTEN"
