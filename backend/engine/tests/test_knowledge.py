"""Basic tests for knowledge structuring."""

from __future__ import annotations

from typing import Optional

import pytest
import pytest_asyncio

from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.knowledge.graph import GraphBuilder
from backend.engine.knowledge.structurer import Structurer
from backend.engine.tests.fakes import StubTextEmbedder
from backend.foundation.core.idgen import gen_evidence_id, gen_knowledge_id
from backend.foundation.core.models import (
    Entity,
    Evidence,
    KnowledgeItem,
    KnowledgeStatus,
    Relation,
)
from backend.foundation.core.repository import EntityRepository, KnowledgeRepository
from backend.foundation.core.vector_store import VectorMatch, VectorStore
from backend.foundation.storage.repository import (
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
)


class _FakeKnowledgeRepo(KnowledgeRepository):
    def __init__(self, fail_save: bool = False) -> None:
        self.items: dict[str, KnowledgeItem] = {}
        self.vectors: dict[str, tuple[int, bytes]] = {}
        self.fail_save = fail_save

    async def save(self, item: KnowledgeItem) -> str:
        if self.fail_save:
            raise RuntimeError("forced knowledge_save failure")
        self.items[item.id] = item
        return item.id

    async def get(self, id: str) -> Optional[KnowledgeItem]:
        return self.items.get(id)

    async def search_fts(self, query: str, limit: int) -> list[KnowledgeItem]:
        return []

    async def search_by_title(self, query: str, limit: int) -> list[KnowledgeItem]:
        return []

    async def save_vector(self, knowledge_id: str, dim: int, vec: bytes) -> None:
        self.vectors[knowledge_id] = (dim, vec)

    async def update_status(self, id: str, status: KnowledgeStatus) -> None:
        item = self.items.get(id)
        if item is not None:
            item.status = status

    async def list_active(self) -> list[KnowledgeItem]:
        return [i for i in self.items.values() if str(i.status) == "ACTIVE"]

    async def list_vectors(self) -> list[tuple[str, int, bytes]]:
        return [(kid, dim, vec) for kid, (dim, vec) in self.vectors.items()]


class _FakeEntityRepo(EntityRepository):
    def __init__(self) -> None:
        self.entities: dict[str, Entity] = {}
        self.relations: list[Relation] = []
        self.save_calls = 0

    async def save_entity(self, entity: Entity) -> str:
        self.save_calls += 1
        self.entities[entity.id] = entity
        return entity.id

    async def get_entity(self, id: str) -> Optional[Entity]:
        return self.entities.get(id)

    async def save_relation(self, src: str, dst: str, type: str) -> None:
        self.relations.append(Relation(src=src, dst=dst, type=type))

    async def get_relations(self, entity_id: str) -> list[Relation]:
        return [r for r in self.relations if r.src == entity_id or r.dst == entity_id]

    async def find_entity_by_name(self, name: str) -> Optional[Entity]:
        key = name.strip().casefold()
        for entity in self.entities.values():
            if entity.name.casefold() == key or entity.norm_name.casefold() == key:
                return entity
        return None

    async def list_relations(self) -> list[Relation]:
        return list(self.relations)


class _FakeVectorStore(VectorStore):
    def __init__(self) -> None:
        self.vectors: dict[str, list[float]] = {}

    @property
    def runtime(self) -> str:
        return "fake"

    async def upsert(self, knowledge_id: str, vector: list[float]) -> None:
        self.vectors[knowledge_id] = list(vector)

    async def search(self, vector: list[float], limit: int) -> list[VectorMatch]:
        return []

    async def delete(self, knowledge_id: str) -> None:
        self.vectors.pop(knowledge_id, None)


def _evidence(
    *,
    source_type: str = "OCR",
    raw: Optional[dict] = None,
    scope: str = "user:alice",
) -> Evidence:
    return Evidence(
        id=gen_evidence_id(),
        source_type=source_type,
        raw=raw or {},
        quality_score=1.0,
        sensitivity=0,
        scope=scope,
        created_at=1,
    )


def _knowledge_service(
    knw_repo: Optional[_FakeKnowledgeRepo] = None,
    entity_repo: Optional[_FakeEntityRepo] = None,
) -> tuple[KnowledgeService, _FakeKnowledgeRepo, _FakeEntityRepo]:
    knw = knw_repo or _FakeKnowledgeRepo()
    ents = entity_repo or _FakeEntityRepo()
    service = KnowledgeService(
        knw_repo=knw,
        entity_repo=ents,
        embedder=StubTextEmbedder(dim=8),
    )
    return service, knw, ents


def _item_with_entities(names: list[str], relations: Optional[list[dict]] = None) -> KnowledgeItem:
    now = 1
    return KnowledgeItem(
        id=gen_knowledge_id(),
        kind="FACT",
        title="t",
        body={},
        entities=names,
        relations=relations or [],
        status="ACTIVE",
        version=1,
        evidence_ids=[],
        scope="user:alice",
        created_at=now,
        updated_at=now,
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


@pytest.mark.asyncio
async def test_structure_writes_original_embedding_through_vector_store() -> None:
    vector_store = _FakeVectorStore()
    service = KnowledgeService(
        knw_repo=_FakeKnowledgeRepo(),
        entity_repo=_FakeEntityRepo(),
        vector_store=vector_store,
        embedder=StubTextEmbedder(dim=8),
    )

    item = await service.structure(_evidence(raw={"title": "向量原文"}))

    assert len(vector_store.vectors[item.id]) == 8
    assert any(not float(value).is_integer() for value in vector_store.vectors[item.id])


@pytest.mark.asyncio
async def test_update_preserves_identity_and_reindexes_vector() -> None:
    knowledge = _FakeKnowledgeRepo()
    vector_store = _FakeVectorStore()
    service = KnowledgeService(
        knw_repo=knowledge,
        entity_repo=_FakeEntityRepo(),
        vector_store=vector_store,
        embedder=StubTextEmbedder(dim=8),
    )
    original = await service.structure(_evidence(raw={"title": "old value"}))
    old_vector = vector_store.vectors[original.id]
    updated = original.model_copy(
        update={"title": "new value", "version": 2, "updated_at": 2}
    )

    result = await service.update(updated)

    assert result.id == original.id
    assert knowledge.items[original.id].title == "new value"
    assert vector_store.vectors[original.id] != old_vector


@pytest.mark.asyncio
async def test_update_rejects_unknown_identity() -> None:
    service, _knowledge, _entities = _knowledge_service()
    with pytest.raises(KeyError):
        await service.update(_item_with_entities([]))


def test_explicit_kind_overrides_heuristics() -> None:
    evidence = _evidence(
        source_type="OCR",
        raw={
            "kind": "CASE",
            "title": "历史案例",
            "body": {
                "kind": "CASE",
                "case": {"summary": "上次设计稿修改"},
                "items": [{"vendor": "国家电网"}],
                "steps": ["a", "b"],
            },
        },
    )
    item = Structurer().structure(evidence)
    assert item.kind == "CASE"


def test_workflow_priority_over_items() -> None:
    evidence = _evidence(
        source_type="OCR",
        raw={
            "title": "带步骤的清单",
            "body": {
                "items": [{"vendor": "国家电网", "amount": 1}],
                "steps": ["识别", "入账"],
            },
        },
    )
    item = Structurer().structure(evidence)
    assert item.kind == "WORKFLOW"


def test_infer_kind_template_from_template_field() -> None:
    evidence = _evidence(
        source_type="MANUAL_CONFIG",
        raw={"title": "报销单模板", "body": {"template": {"fields": ["日期", "金额"]}}},
    )
    item = Structurer().structure(evidence)
    assert item.kind == "TEMPLATE"


def test_infer_kind_case_from_case_field() -> None:
    evidence = _evidence(
        source_type="USER_BEHAVIOR",
        raw={"title": "设计稿修改过程", "body": {"case": {"title": "上次修改"}}},
    )
    item = Structurer().structure(evidence)
    assert item.kind == "CASE"


@pytest.mark.asyncio
async def test_structure_ocr_items_is_fact_without_sqlite() -> None:
    service, knw, ents = _knowledge_service()
    evidence = _evidence(
        source_type="OCR",
        raw={
            "title": "2026年4月家庭支出清单",
            "body": {"items": [{"category": "水电燃气", "vendor": "国家电网", "amount": 210.0}]},
        },
    )
    item = await service.structure(evidence)
    assert item.kind == "FACT"
    assert "国家电网" in item.entities
    assert item.id in knw.items
    assert await ents.find_entity_by_name("国家电网") is not None


@pytest.mark.asyncio
async def test_structure_steps_is_workflow_without_sqlite() -> None:
    service, _knw, _ents = _knowledge_service()
    evidence = _evidence(
        source_type="TOOL_RESULT",
        raw={"title": "报销流程", "body": {"steps": ["填写报销单", "上传发票", "主管审批"]}},
    )
    item = await service.structure(evidence)
    assert item.kind == "WORKFLOW"


def test_workflow_invalid_steps_falls_back_to_fact() -> None:
    evidence = _evidence(
        source_type="TOOL_RESULT",
        raw={"title": "坏流程", "body": {"steps": "not-a-list"}},
    )
    item = Structurer().structure(evidence)
    assert item.kind == "FACT"


@pytest.mark.asyncio
async def test_vendor_identity_matches_entities() -> None:
    service, _knw, ents = _knowledge_service()
    evidence = _evidence(
        source_type="OCR",
        raw={
            "title": "账单",
            "body": {"items": [{"category": "水电燃气", "vendor": "国网"}]},
            "entities": [],
        },
    )
    item = await service.structure(evidence)
    assert item.body["items"][0]["vendor"] == "国家电网"
    assert "国家电网" in item.entities
    assert item.entities.count("国家电网") == 1
    found = await ents.find_entity_by_name("国家电网")
    assert found is not None


@pytest.mark.asyncio
async def test_vendor_alias_does_not_create_duplicate_entity() -> None:
    service, _knw, ents = _knowledge_service()
    evidence = _evidence(
        raw={
            "title": "账单",
            "body": {"items": [{"vendor": "国网"}]},
            "entities": ["国家电网"],
        }
    )
    item = await service.structure(evidence)
    assert item.entities == ["国家电网"]
    assert ents.save_calls == 1


@pytest.mark.asyncio
async def test_graph_reuses_entity_by_name() -> None:
    repo = _FakeEntityRepo()
    graph = GraphBuilder()
    first = _item_with_entities(["国家电网"])
    second = _item_with_entities(["国家电网"])
    await graph.build(first, repo)
    await graph.build(second, repo)
    assert repo.save_calls == 1
    assert len(repo.entities) == 1


@pytest.mark.asyncio
async def test_graph_skips_empty_entity_names() -> None:
    repo = _FakeEntityRepo()
    graph = GraphBuilder()
    item = _item_with_entities(
        ["", "  ", "国家电网"],
        relations=[{"from": "", "to": "水电燃气", "type": "belong_to"}],
    )
    entities, relations = await graph.build(item, repo)
    assert [e.name for e in entities] == ["国家电网"]
    assert relations == []
    assert repo.save_calls == 1


@pytest.mark.asyncio
async def test_graph_normalizes_relation_type() -> None:
    repo = _FakeEntityRepo()
    graph = GraphBuilder()
    item = _item_with_entities(
        ["国家电网", "水电燃气"],
        relations=[{"from": "国家电网", "to": "水电燃气", "type": "belong_to"}],
    )
    _entities, relations = await graph.build(item, repo)
    assert relations[0].type == "BELONG_TO"


@pytest.mark.asyncio
async def test_structure_empty_evidence_defaults_to_fact() -> None:
    service, knw, _ents = _knowledge_service()
    evidence = _evidence(raw={})
    item = await service.structure(evidence)
    assert item.kind == "FACT"
    assert item.title == "untitled"
    assert item.entities == []
    assert item.id in knw.items


@pytest.mark.asyncio
async def test_structure_same_evidence_twice_two_ids() -> None:
    service, knw, _ents = _knowledge_service()
    evidence = _evidence(raw={"title": "同一条", "body": {"items": [{"vendor": "国网"}]}})
    first = await service.structure(evidence)
    second = await service.structure(evidence)
    assert first.id != second.id
    assert len(knw.items) == 2


@pytest.mark.asyncio
async def test_structure_logs_knowledge_save_failure(caplog: pytest.LogCaptureFixture) -> None:
    service, _knw, _ents = _knowledge_service(knw_repo=_FakeKnowledgeRepo(fail_save=True))
    evidence = _evidence(raw={"title": "x", "body": {}})
    with caplog.at_level("WARNING", logger="backend.engine.knowledge"):
        with pytest.raises(RuntimeError, match="forced knowledge_save failure"):
            await service.structure(evidence)
    assert any("step=knowledge_save" in rec.getMessage() for rec in caplog.records)
