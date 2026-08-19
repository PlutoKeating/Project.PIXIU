"""Unit tests for Conflict engine logic.

Uses in-memory Fake repositories so these tests do not depend on SQLite FTS5
trigram. Original SQLite integration tests in test_conflict.py are kept.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest

from backend.engine.conflict import ConflictService
from backend.foundation.core.idgen import gen_knowledge_id
from backend.foundation.core.models import ConflictRecord, KnowledgeItem, KnowledgeStatus


class FakeKnowledgeRepo:
    def __init__(self) -> None:
        self.items: dict[str, KnowledgeItem] = {}

    async def save(self, item: KnowledgeItem) -> str:
        self.items[item.id] = item
        return item.id

    async def get(self, id: str) -> Optional[KnowledgeItem]:
        return self.items.get(id)

    async def list_active(self) -> list[KnowledgeItem]:
        return [item for item in self.items.values() if item.status == "ACTIVE"]

    async def update_status(self, id: str, status: KnowledgeStatus) -> None:
        item = self.items.get(id)
        if item is not None:
            item.status = status


class FakeConflictRepo:
    def __init__(self) -> None:
        self.records: list[ConflictRecord] = []

    async def save(self, record: ConflictRecord) -> str:
        self.records.append(record)
        return record.id

    async def get(self, id: str) -> Optional[ConflictRecord]:
        for record in self.records:
            if record.id == id:
                return record
        return None

    async def list(self) -> list[ConflictRecord]:
        return list(self.records)


def _item(
    *,
    title: str,
    body: dict[str, Any],
    entities: list[str] | None = None,
    scope: str = "user:alice",
    status: str = "ACTIVE",
    version: int = 1,
) -> KnowledgeItem:
    now = 1_700_000_000
    return KnowledgeItem(
        id=gen_knowledge_id(),
        kind="FACT",
        title=title,
        body=body,
        entities=list(entities or []),
        relations=[],
        status=status,
        version=version,
        evidence_ids=[],
        scope=scope,
        created_at=now,
        updated_at=now,
    )


def _service(
    knw: FakeKnowledgeRepo | None = None,
    cfl: FakeConflictRepo | None = None,
) -> tuple[ConflictService, FakeKnowledgeRepo, FakeConflictRepo]:
    knw = knw or FakeKnowledgeRepo()
    cfl = cfl or FakeConflictRepo()
    return ConflictService(knw_repo=knw, conflict_repo=cfl), knw, cfl


@pytest.mark.asyncio
async def test_numeric_conflict_same_entity_same_field() -> None:
    service, knw, _ = _service()
    old = _item(
        title="utility statement",
        entities=["AlphaPower"],
        body={"items": [{"vendor": "AlphaPower", "amount": 210}]},
    )
    new = _item(
        title="utility statement",
        entities=["AlphaPower"],
        body={"items": [{"vendor": "AlphaPower", "amount": 230}]},
    )
    await knw.save(old)

    record = await service.arbitrate(new)
    assert record is not None
    assert "amount" in record.field
    assert record.old_value == 210
    assert record.new_value == 230
    assert record.resolution == "NEW_WINS"


@pytest.mark.asyncio
async def test_numeric_conflict_same_entity_different_title() -> None:
    service, knw, _ = _service()
    old = _item(
        title="2026年4月家庭支出清单",
        entities=["AlphaPower"],
        body={"items": [{"vendor": "AlphaPower", "amount": 210}]},
    )
    new = _item(
        title="4月电费修正版",
        entities=["AlphaPower"],
        body={"items": [{"vendor": "AlphaPower", "amount": 230}]},
    )
    await knw.save(old)

    record = await service.arbitrate(new)
    assert record is not None
    assert "amount" in record.field
    assert record.old_value == 210
    assert record.new_value == 230


@pytest.mark.asyncio
async def test_no_conflict_different_entity_same_title() -> None:
    service, knw, _ = _service()
    old = _item(
        title="monthly bill",
        entities=["AlphaPower"],
        body={"items": [{"vendor": "AlphaPower", "amount": 210}]},
    )
    new = _item(
        title="monthly bill",
        entities=["BetaGas"],
        body={"items": [{"vendor": "BetaGas", "amount": 230}]},
    )
    await knw.save(old)

    record = await service.arbitrate(new)
    assert record is None
    stored_old = await knw.get(old.id)
    assert stored_old is not None
    assert stored_old.status == "ACTIVE"


@pytest.mark.asyncio
async def test_no_conflict_identical_text() -> None:
    service, knw, _ = _service()
    old = _item(
        title="style note",
        entities=["OutputStyle"],
        body={"text": "喜欢简洁回答"},
    )
    new = _item(
        title="style note v2",
        entities=["OutputStyle"],
        body={"text": "喜欢简洁回答"},
    )
    await knw.save(old)

    record = await service.arbitrate(new)
    assert record is None


@pytest.mark.asyncio
async def test_no_conflict_synonymous_text() -> None:
    service, knw, _ = _service()
    old = _item(
        title="style note",
        entities=["OutputStyle"],
        body={"text": "喜欢简洁回答"},
    )
    new = _item(
        title="style note v2",
        entities=["OutputStyle"],
        body={"text": "偏好简短回复"},
    )
    await knw.save(old)

    record = await service.arbitrate(new)
    assert record is None


@pytest.mark.asyncio
async def test_conflict_antonym_text() -> None:
    service, knw, _ = _service()
    old = _item(
        title="style note",
        entities=["OutputStyle"],
        body={"text": "喜欢简洁回答"},
    )
    new = _item(
        title="style note v2",
        entities=["OutputStyle"],
        body={"text": "喜欢非常详细的回答"},
    )
    await knw.save(old)

    record = await service.arbitrate(new)
    assert record is not None
    assert record.old_value == "喜欢简洁回答"
    assert record.new_value == "喜欢非常详细的回答"
    assert record.resolution == "NEW_WINS"


@pytest.mark.asyncio
async def test_no_conflict_without_comparable_fields() -> None:
    service, knw, _ = _service()
    old = _item(
        title="record a",
        entities=["AlphaPower"],
        body={"amount": 210},
    )
    new = _item(
        title="record b",
        entities=["AlphaPower"],
        body={"note": "corrected description only"},
    )
    await knw.save(old)

    record = await service.arbitrate(new)
    assert record is None
    stored_old = await knw.get(old.id)
    assert stored_old is not None
    assert stored_old.status == "ACTIVE"


@pytest.mark.asyncio
async def test_new_wins_supersedes_old_and_saves_record() -> None:
    service, knw, cfl = _service()
    old = _item(
        title="bill",
        entities=["AlphaPower"],
        body={"items": [{"vendor": "AlphaPower", "amount": 156}]},
        version=1,
    )
    new = _item(
        title="bill correction",
        entities=["AlphaPower"],
        body={"items": [{"vendor": "AlphaPower", "amount": 186}]},
        version=1,
    )
    await knw.save(old)

    record = await service.arbitrate(new)
    assert record is not None
    assert record.resolution == "NEW_WINS"
    assert record.target_knowledge == old.id
    assert record.id.startswith("cfl_")
    assert "amount" in record.field
    assert record.old_value == 156
    assert record.new_value == 186

    stored_old = await knw.get(old.id)
    assert stored_old is not None
    assert stored_old.status == "SUPERSEDED"

    stored_new = await knw.get(new.id)
    assert stored_new is not None
    assert stored_new.status == "ACTIVE"
    assert stored_new.version >= 2

    assert len(cfl.records) == 1
    assert cfl.records[0].id == record.id


@pytest.mark.asyncio
async def test_title_fallback_numeric_conflict_without_entities() -> None:
    """When neither item has instance entities, title remains an auxiliary key."""
    service, knw, _ = _service()
    old = _item(
        title="same title only",
        entities=[],
        body={"items": [{"amount": 156}]},
    )
    new = _item(
        title="same title only",
        entities=[],
        body={"items": [{"amount": 186}]},
    )
    await knw.save(old)

    record = await service.arbitrate(new)
    assert record is not None
    assert "amount" in record.field
    assert record.old_value == 156
    assert record.new_value == 186
