"""Security detector and forget tests (Fake repositories; no SQLite FTS)."""

from __future__ import annotations

from typing import Optional

import pytest

from backend.engine.security import SecurityService
from backend.engine.security.detector import Detector
from backend.foundation.core.idgen import gen_evidence_id, gen_knowledge_id
from backend.foundation.core.models import (
    Entity,
    Evidence,
    KnowledgeItem,
    KnowledgeStatus,
    Relation,
    SourceType,
)
from backend.foundation.core.repository import EntityRepository, KnowledgeRepository


class _FakeKnowledgeRepo(KnowledgeRepository):
    def __init__(self, items: Optional[list[KnowledgeItem]] = None) -> None:
        self.items: dict[str, KnowledgeItem] = {item.id: item for item in (items or [])}

    async def save(self, item: KnowledgeItem) -> str:
        self.items[item.id] = item
        return item.id

    async def get(self, id: str) -> Optional[KnowledgeItem]:
        return self.items.get(id)

    async def search_fts(self, query: str, limit: int) -> list[KnowledgeItem]:
        return []

    async def search_by_title(self, query: str, limit: int) -> list[KnowledgeItem]:
        return []

    async def save_vector(self, knowledge_id: str, dim: int, vec: bytes) -> None:
        return None

    async def update_status(self, id: str, status: KnowledgeStatus) -> None:
        item = self.items.get(id)
        if item is not None:
            item.status = status

    async def list_active(self) -> list[KnowledgeItem]:
        return [i for i in self.items.values() if i.status == KnowledgeStatus.ACTIVE]

    async def list_vectors(self) -> list[tuple[str, int, bytes]]:
        return []


class _FakeEntityRepo(EntityRepository):
    def __init__(self) -> None:
        self.entities: dict[str, Entity] = {}
        self.relations: list[Relation] = []

    async def save_entity(self, entity: Entity) -> str:
        self.entities[entity.id] = entity
        return entity.id

    async def get_entity(self, id: str) -> Optional[Entity]:
        return self.entities.get(id)

    async def save_relation(self, src: str, dst: str, type: str) -> None:
        self.relations.append(Relation(src=src, dst=dst, type=type))

    async def get_relations(self, entity_id: str) -> list[Relation]:
        return [
            rel
            for rel in self.relations
            if rel.src == entity_id or rel.dst == entity_id
        ]

    async def find_entity_by_name(self, name: str) -> Optional[Entity]:
        key = name.strip().casefold()
        for entity in self.entities.values():
            if entity.name.casefold() == key:
                return entity
        return None

    async def list_relations(self) -> list[Relation]:
        return list(self.relations)


def _knowledge_item(
    *,
    title: str,
    scope: str,
    body: Optional[dict] = None,
    evidence_ids: Optional[list[str]] = None,
    item_id: Optional[str] = None,
) -> KnowledgeItem:
    now = 1
    return KnowledgeItem(
        id=item_id or gen_knowledge_id(),
        kind="FACT",
        title=title,
        body=body or {},
        entities=[],
        relations=[],
        status="ACTIVE",
        version=1,
        evidence_ids=evidence_ids or [],
        scope=scope,
        created_at=now,
        updated_at=now,
    )


def _security(
    items: list[KnowledgeItem],
) -> tuple[SecurityService, _FakeKnowledgeRepo, _FakeEntityRepo]:
    knw = _FakeKnowledgeRepo(items)
    ents = _FakeEntityRepo()
    return SecurityService(knw_repo=knw, entity_repo=ents), knw, ents


VALID_ID = "11010519491231002X"
INVALID_ID = "123456789012345678"
ORDER_NUMBER = "1234567890123456"


@pytest.mark.asyncio
async def test_detect_id_card_high() -> None:
    service, _, _ = _security([])
    score = await service.detect_sensitivity({"note": f"身份证号 {VALID_ID}"})
    assert score == 3


@pytest.mark.asyncio
async def test_detector_valid_id() -> None:
    detail = Detector().detect_detail({"note": f"身份证{VALID_ID}"})
    assert detail.score == 3
    assert "id_card" in detail.types


@pytest.mark.asyncio
async def test_detector_invalid_id_checksum() -> None:
    detail = Detector().detect_detail({"note": INVALID_ID})
    assert detail.score == 0
    assert detail.types == []


@pytest.mark.asyncio
async def test_detector_id_adjacent_cjk_boundary() -> None:
    detail = Detector().detect_detail({"note": f"身份证号{VALID_ID}"})
    assert detail.score == 3
    assert "id_card" in detail.types


@pytest.mark.asyncio
async def test_detect_phone_mid() -> None:
    service, _, _ = _security([])
    score = await service.detect_sensitivity({"phone": "13812345678"})
    assert score == 2


@pytest.mark.asyncio
async def test_detector_bank_card_false_positive_order_number() -> None:
    detail = Detector().detect_detail({"order": ORDER_NUMBER})
    assert "bank_card" not in detail.types


@pytest.mark.asyncio
async def test_detector_multiple_hits() -> None:
    service, _, _ = _security([])
    detail = await service.detect(
        {"text": f"姓名张三，手机13800138000，身份证{VALID_ID}"}
    )
    assert detail.score == 3
    assert set(detail.types) == {"id_card", "phone"}


@pytest.mark.asyncio
async def test_detect_clean() -> None:
    service, _, _ = _security([])
    score = await service.detect_sensitivity({"title": "普通笔记", "body": {}})
    assert score == 0


@pytest.mark.asyncio
async def test_forget_respects_scope_isolation() -> None:
    alice_item = _knowledge_item(title="四月份电费账单", scope="user:alice")
    bob_item = _knowledge_item(title="四月份电费账单", scope="user:bob")
    service, _, _ = _security([alice_item, bob_item])

    pending = await service.forget("忘记四月份电费", confirm=False, scope="user:alice")
    ids = {t["id"] for t in pending.targets}
    assert alice_item.id in ids
    assert bob_item.id not in ids


@pytest.mark.asyncio
async def test_forget_rejects_empty_scope() -> None:
    service, _, _ = _security([_knowledge_item(title="x", scope="user:alice")])
    with pytest.raises(ValueError, match="scope must be a non-empty string"):
        await service.forget("忘记x", confirm=False, scope="")


@pytest.mark.asyncio
async def test_forget_legacy_call_without_scope() -> None:
    item = _knowledge_item(title="四月份电费账单", scope="user:alice")
    service, _, _ = _security([item])

    pending = await service.forget("忘记四月份电费", confirm=False)
    assert [target["id"] for target in pending.targets] == [item.id]


@pytest.mark.asyncio
async def test_forget_multiple_candidates_sorted() -> None:
    low = _knowledge_item(title="家庭支出模板", body={"text": "电费说明"}, scope="user:alice")
    mid = _knowledge_item(title="电费缴纳流程", scope="user:alice")
    high = _knowledge_item(title="四月份电费账单", scope="user:alice")
    service, _, _ = _security([low, mid, high])

    pending = await service.forget("忘记四月份电费", confirm=False, scope="user:alice")
    assert len(pending.targets) >= 2
    scores = [t["score"] for t in pending.targets]
    assert scores == sorted(scores, reverse=True)
    assert pending.targets[0]["id"] == high.id


@pytest.mark.asyncio
async def test_forget_title_match_higher_than_body() -> None:
    title_item = _knowledge_item(title="四月份电费账单", scope="user:alice")
    body_only = _knowledge_item(
        title="家庭支出模板",
        body={"memo": "四月份电费说明"},
        scope="user:alice",
    )
    service, _, _ = _security([title_item, body_only])

    pending = await service.forget("忘记四月份电费", confirm=False, scope="user:alice")
    by_id = {t["id"]: t["score"] for t in pending.targets}
    assert title_item.id in by_id
    if body_only.id in by_id:
        assert by_id[title_item.id] > by_id[body_only.id]


@pytest.mark.asyncio
async def test_forget_month_normalization() -> None:
    item = _knowledge_item(title="2026年4月家庭支出清单", scope="user:alice")
    service, _, _ = _security([item])

    pending_a = await service.forget("忘记四月份支出清单", confirm=False, scope="user:alice")
    pending_b = await service.forget("请帮我忘掉一下四月份的支出记录", confirm=False, scope="user:alice")
    assert any(t["id"] == item.id for t in pending_a.targets)
    assert any(t["id"] == item.id for t in pending_b.targets)


@pytest.mark.asyncio
async def test_forget_no_match_returns_empty_targets() -> None:
    service, _, _ = _security([_knowledge_item(title=" unrelated ", scope="user:alice")])
    pending = await service.forget("忘记火星任务", confirm=False, scope="user:alice")
    assert pending.targets == []


@pytest.mark.asyncio
async def test_forget_pending_then_confirm_only_updates_knowledge() -> None:
    evd_id = gen_evidence_id()
    item = _knowledge_item(
        title="2026年4月家庭支出清单",
        scope="user:alice",
        evidence_ids=[evd_id],
    )
    service, knw, _ = _security([item])

    pending = await service.forget("忘记4月支出清单", confirm=False, scope="user:alice")
    assert pending.status == "pending"
    assert any(t["id"] == item.id for t in pending.targets)
    assert knw.items[item.id].status == KnowledgeStatus.ACTIVE

    done = await service.forget("忘记4月支出清单", confirm=True, scope="user:alice")
    assert done.status == "forgotten"
    assert item.id in done.forgotten_ids
    assert knw.items[item.id].status == KnowledgeStatus.FORGOTTEN


@pytest.mark.asyncio
async def test_forget_does_not_claim_delete_evidence() -> None:
    evd_id = gen_evidence_id()
    item = _knowledge_item(
        title="四月份电费账单",
        scope="user:alice",
        evidence_ids=[evd_id],
    )
    service, knw, _ = _security([item])

    done = await service.forget("忘记四月份电费", confirm=True, scope="user:alice")
    assert done.cascade_preview.get("evidence_count", 0) >= 1
    assert evd_id not in done.forgotten_ids
    # Engine only soft-deletes knowledge; evidence rows are not removed here.
    assert knw.items[item.id].status == KnowledgeStatus.FORGOTTEN


@pytest.mark.asyncio
async def test_forget_repeat_confirm_returns_no_active_targets() -> None:
    item = _knowledge_item(title="四月份电费账单", scope="user:alice")
    service, _, _ = _security([item])

    await service.forget("忘记四月份电费", confirm=True, scope="user:alice")
    again = await service.forget("忘记四月份电费", confirm=True, scope="user:alice")
    assert again.targets == []
    assert again.forgotten_ids == []


def test_legacy_find_matches_labels() -> None:
    labels = Detector().find_matches({"phone": "13812345678", "note": VALID_ID})
    assert "手机号" in labels
    assert "身份证" in labels
