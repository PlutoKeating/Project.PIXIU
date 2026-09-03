"""Tests for retrieval/ — 混合检索七步管线。"""

from __future__ import annotations

import asyncio
import hashlib
import random
import struct
import time
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.core.models import (
    Entity,
    Evidence,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeStatus,
    SourceType,
)
from backend.foundation.core.vector_store import VectorMatch, VectorStore
from backend.foundation.storage.repository import (
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
)
from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.retrieval import RetrievalService

NOW = int(time.time())


class StubTextEmbedder:
    """确定性文本向量桩（与 engine/tests/fakes.py 一致）：32 维 [-1,1)。"""

    def __init__(self, dim: int = 32) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        rng = random.Random(int.from_bytes(digest[:8], "big"))
        return [rng.uniform(-1.0, 1.0) for _ in range(self.dim)]


class RecordingVectorStore(VectorStore):
    def __init__(self, match: VectorMatch) -> None:
        self.match = match
        self.queries: list[tuple[list[float], int]] = []

    @property
    def runtime(self) -> str:
        return "recording"

    async def upsert(self, knowledge_id: str, vector: list[float]) -> None:
        raise AssertionError("not used by retrieval")

    async def search(self, vector: list[float], limit: int) -> list[VectorMatch]:
        self.queries.append((vector, limit))
        return [self.match]

    async def delete(self, knowledge_id: str) -> None:
        raise AssertionError("not used by retrieval")


def _quantize_bytes(vector: list[float]) -> bytes:
    max_abs = max(abs(x) for x in vector) or 1.0
    scale = 127.0 / max_abs
    q = [max(-127, min(127, int(round(x * scale)))) for x in vector]
    return struct.pack(f"{len(q)}b", *q)


def _knw_id(tag: str) -> str:
    return f"knw_{(tag + '0' * 26)[:26]}"


def _evd_id(tag: str) -> str:
    return f"evd_{(tag + '0' * 26)[:26]}"


def _ent_id(tag: str) -> str:
    return f"ent_{(tag + '0' * 26)[:26]}"


@pytest_asyncio.fixture
async def svc(tmp_path: Path):
    """真实 SQLite 临时库 + RetrievalService（StubTextEmbedder）。"""
    db_path = str(tmp_path / "retrieval.db")
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")

    import sqlite3 as _sqlite3

    sync_conn = _sqlite3.connect(db_path)
    init_db_on_connection(sync_conn)
    sync_conn.close()

    knw_repo = SqliteKnowledgeRepo(db)
    ent_repo = SqliteEntityRepo(db)
    evd_repo = SqliteEvidenceRepo(db)
    embedder = StubTextEmbedder()

    service = RetrievalService(
        knw_repo=knw_repo,
        entity_repo=ent_repo,
        evidence_repo=evd_repo,
        embedder=embedder,
    )
    yield service, knw_repo, ent_repo, evd_repo, embedder
    await db.close()


async def _save_knowledge(knw_repo, embedder, **kwargs) -> KnowledgeItem:
    """保存知识 + 写入其向量（query 与 _to_text 文本一致时相似度最高）。"""
    item = KnowledgeItem(
        id=_knw_id(kwargs.pop("tag", "main")),
        kind=kwargs.pop("kind", KnowledgeKind.FACT),
        title=kwargs.pop("title", "2026年4月家庭支出清单"),
        body=kwargs.pop("body", {"description": "水电燃气支出记录"}),
        scope=kwargs.pop("scope", "shared:home"),
        entities=kwargs.pop("entities", []),
        relations=kwargs.pop("relations", []),
        evidence_ids=kwargs.pop("evidence_ids", []),
        created_at=kwargs.pop("created_at", NOW),
        updated_at=kwargs.pop("updated_at", NOW),
    )
    await knw_repo.save(item)
    text = " ".join(str(p) for p in [item.title, item.kind, item.body])
    await knw_repo.save_vector(item.id, embedder.dim, _quantize_bytes(embedder.embed(text)))
    return item


# ═══════════════════════════════════════════════════════
# Group 1: BM25 中文检索通道
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_bm25_channel_chinese_hit(svc):
    _, knw_repo, _, _, _ = svc
    await _save_knowledge(knw_repo, StubTextEmbedder(), title="2026年4月家庭支出清单")

    from backend.foundation.retrieval.bm25 import BM25Channel

    results = await BM25Channel(knw_repo).search("家庭支出", limit=10)
    assert len(results) == 1
    assert results[0][0].title == "2026年4月家庭支出清单"
    assert results[0][1] > 0


@pytest.mark.asyncio
async def test_bm25_filters_forgotten(svc):
    _, knw_repo, _, _, _ = svc
    item = await _save_knowledge(knw_repo, StubTextEmbedder(), title="机密记录")
    await knw_repo.update_status(item.id, KnowledgeStatus.FORGOTTEN)

    from backend.foundation.retrieval.bm25 import BM25Channel

    results = await BM25Channel(knw_repo).search("机密记录", limit=10)
    assert results == []


@pytest.mark.asyncio
async def test_bm25_long_sentence_fallback(svc):
    """长句查询（trigram 直接 MATCH 必然 0 命中）应通过滑动窗口回退命中。"""
    _, knw_repo, _, _, _ = svc
    await _save_knowledge(knw_repo, StubTextEmbedder(), title="2026年4月家庭支出清单")

    from backend.foundation.retrieval.bm25 import BM25Channel

    results = await BM25Channel(knw_repo).search(
        "我们家庭支出方面好像花了一些钱花了多少钱来着", limit=10
    )
    # 滑动窗口回退应命中含"家庭支出"的知识
    assert any("家庭支出" in item.title for item, _ in results)


# ═══════════════════════════════════════════════════════
# Group 2: ANN 通道
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ann_channel_hits_same_text(svc):
    _, knw_repo, _, _, embedder = svc
    item = await _save_knowledge(knw_repo, embedder, title="水电燃气月度支出")

    from backend.foundation.retrieval.ann import ANNChannel

    query_text = " ".join(str(p) for p in [item.title, item.kind, item.body])
    results = await ANNChannel(knw_repo, embedder).search(query_text, top_k=5)
    assert len(results) == 1
    assert results[0][0].id == item.id
    assert results[0][1] > 0.9


@pytest.mark.asyncio
async def test_ann_channel_misses_unrelated(svc):
    _, knw_repo, _, _, embedder = svc
    await _save_knowledge(knw_repo, embedder, title="水电燃气月度支出")

    from backend.foundation.retrieval.ann import ANNChannel

    results = await ANNChannel(knw_repo, embedder).search("完全无关的词语文本", top_k=5)
    assert len(results) == 0 or results[0][1] < 0.5


@pytest.mark.asyncio
async def test_ann_channel_queries_injected_vector_store(svc):
    _, knw_repo, _, _, embedder = svc
    item = await _save_knowledge(knw_repo, embedder, title="系统向量库接线")
    store = RecordingVectorStore(VectorMatch(item.id, 0.97))

    from backend.foundation.retrieval.ann import ANNChannel

    results = await ANNChannel(knw_repo, embedder, vector_store=store).search(
        "查询原文", top_k=3
    )

    assert results == [(item, 0.97)]
    assert store.queries == [(embedder.embed("查询原文"), 3)]


# ═══════════════════════════════════════════════════════
# Group 3: Graph 通道
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_graph_channel_entity_hit(svc):
    _, knw_repo, ent_repo, _, _ = svc
    await ent_repo.save_entity(Entity(id=_ent_id("gd"), name="国家电网", norm_name="国家电网", type="ORG"))
    await ent_repo.save_entity(Entity(id=_ent_id("sd"), name="水电燃气", norm_name="水电燃气", type="CATEGORY"))
    await ent_repo.save_relation(_ent_id("gd"), _ent_id("sd"), "BELONG_TO")
    await _save_knowledge(
        knw_repo, StubTextEmbedder(), tag="g1", title="四月账单",
        body={"description": "家庭费用明细"},
        entities=["国家电网"],
        relations=[{"from": "国家电网", "to": "水电燃气", "type": "BELONG_TO"}],
    )

    from backend.foundation.retrieval.graph_search import GraphChannel

    results = await GraphChannel(knw_repo, ent_repo).search(["国家电网"], limit=10)
    assert len(results) == 1
    assert results[0][0].id == _knw_id("g1")
    assert results[0][1] == 1.5  # 精确实体关联 1 + BELONG_TO 一跳关联 0.5


@pytest.mark.asyncio
async def test_graph_channel_survives_database_restart(tmp_path):
    from backend.foundation.retrieval.graph_search import GraphChannel

    db_path = str(tmp_path / "graph-restart.db")
    import sqlite3 as _sqlite3

    sync_conn = _sqlite3.connect(db_path)
    init_db_on_connection(sync_conn)
    sync_conn.close()

    first_db = await aiosqlite.connect(db_path)
    first_db.row_factory = aiosqlite.Row
    first_knw = SqliteKnowledgeRepo(first_db)
    first_entities = SqliteEntityRepo(first_db)
    await first_entities.save_entity(
        Entity(id=_ent_id("vendor"), name="国家电网", norm_name="国家电网", type="ORG")
    )
    await first_entities.save_entity(
        Entity(id=_ent_id("category"), name="水电燃气", norm_name="水电燃气", type="CATEGORY")
    )
    await first_entities.save_relation(_ent_id("vendor"), _ent_id("category"), "BELONG_TO")
    item = await _save_knowledge(
        first_knw, StubTextEmbedder(), tag="restart", title="四月账单",
        entities=["国家电网"],
        relations=[{"from": "国家电网", "to": "水电燃气", "type": "BELONG_TO"}],
    )
    await first_db.close()

    reopened_db = await aiosqlite.connect(db_path)
    reopened_db.row_factory = aiosqlite.Row
    results = await GraphChannel(
        SqliteKnowledgeRepo(reopened_db), SqliteEntityRepo(reopened_db)
    ).search(["水电燃气"], limit=10)
    await reopened_db.close()

    assert [knowledge.id for knowledge, _ in results] == [item.id]


# ═══════════════════════════════════════════════════════
# Group 4: RRF 融合
# ═══════════════════════════════════════════════════════

def test_fuse_rrf_merges_rankings():
    from backend.foundation.retrieval.fuse import fuse_rrf

    # knw_b 同时出现在两通道（rank0+rank1），应高于单通道 rank0 的 knw_a
    fused = fuse_rrf({"bm25": ["knw_a", "knw_b", "knw_c"], "ann": ["knw_b"]})
    assert fused["knw_b"] > fused["knw_a"] > fused["knw_c"]
    assert "knw_c" in fused


def test_fuse_scope_is_hard_filter():
    from backend.foundation.retrieval.fuse import fuse_candidates

    allowed = KnowledgeItem(
        id=_knw_id("scopeok"), kind=KnowledgeKind.FACT, title="允许",
        scope="user:alice", created_at=NOW, updated_at=NOW,
    )
    forbidden = KnowledgeItem(
        id=_knw_id("scopeno"), kind=KnowledgeKind.FACT, title="禁止",
        scope="user:bob", created_at=NOW, updated_at=NOW,
    )
    result = fuse_candidates(
        bm25=[(forbidden, 1.0), (allowed, 0.5)],
        scope="user:alice",
    )
    assert [item.id for item, _ in result] == [allowed.id]


def test_fuse_time_range_filters_structured_dates():
    from backend.foundation.retrieval.fuse import fuse_candidates, matches_time_range

    april = KnowledgeItem(
        id=_knw_id("april"), kind=KnowledgeKind.FACT, title="四月账单",
        body={"items": [{"date": "2026-04-10", "amount": 1}]},
        scope="shared:home", created_at=NOW, updated_at=NOW,
    )
    march = KnowledgeItem(
        id=_knw_id("march"), kind=KnowledgeKind.FACT, title="三月账单",
        body={"items": [{"date": "2026-03-10", "amount": 1}]},
        scope="shared:home", created_at=NOW, updated_at=NOW,
    )
    now_ts = datetime(2026, 5, 15, tzinfo=timezone.utc).timestamp()
    assert matches_time_range(april, "last_month", now_ts=now_ts)
    assert not matches_time_range(march, "last_month", now_ts=now_ts)

    result = fuse_candidates(
        bm25=[(march, 1.0), (april, 0.5)],
        time_range={"start": "2026-04-01", "end": "2026-05-01"},
    )
    assert [item.id for item, _ in result] == [april.id]


# ═══════════════════════════════════════════════════════
# Group 5: rerank 词面重叠
# ═══════════════════════════════════════════════════════

def test_rerank_boosts_overlap():
    from backend.foundation.retrieval.rerank import overlap_score, rerank

    item_a = KnowledgeItem(
        id=_knw_id("r1"), kind=KnowledgeKind.FACT, title="水电燃气支出清单",
        body={}, scope="shared:home", created_at=NOW, updated_at=NOW,
    )
    item_b = KnowledgeItem(
        id=_knw_id("r2"), kind=KnowledgeKind.FACT, title="项目周报",
        body={}, scope="user:a", created_at=NOW, updated_at=NOW,
    )
    assert overlap_score("水电燃气支出", item_a) > overlap_score("水电燃气支出", item_b)

    reranked = rerank([(item_b, 0.5), (item_a, 0.4)], "水电燃气支出")
    assert reranked[0][0].id == item_a.id


# ═══════════════════════════════════════════════════════
# Group 6: assembler 聚合
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_assembler_aggregates_amount(svc):
    _, knw_repo, _, evd_repo, _ = svc
    evd = Evidence(
        id=_evd_id("e1"), source_type=SourceType.OCR, raw={"title": "清单"},
        scope="shared:home", created_at=NOW,
    )
    await evd_repo.save(evd)
    item = await _save_knowledge(
        knw_repo, StubTextEmbedder(), tag="agg", title="家庭支出清单",
        body={"items": [
            {"category": "食品", "amount": 328.5, "tags": ["生鲜"]},
            {"category": "水电燃气", "amount": 210.0, "tags": ["电费"]},
            {"category": "水电燃气", "amount": 68.5, "tags": ["水费"]},
            {"category": "水电燃气", "amount": 156.0, "tags": ["燃气费"]},
        ]},
        evidence_ids=[evd.id],
    )

    from backend.foundation.retrieval.assembler import Assembler

    atom = await Assembler(evd_repo).assemble(item, 0.9, "水电燃气花了多少钱", 42)
    assert "434.50" in atom.answer
    assert "763.00" not in atom.answer
    assert "电费 210.00 元" in atom.answer
    assert atom.source_evidence == [evd.id]
    assert atom.source_knowledge == item.id
    assert atom.confidence == 0.9
    assert atom.latency_ms == 42


@pytest.mark.asyncio
async def test_assembler_falls_back_to_title(svc):
    _, knw_repo, _, evd_repo, _ = svc
    item = await _save_knowledge(knw_repo, StubTextEmbedder(), tag="t2", title="简单知识")

    from backend.foundation.retrieval.assembler import Assembler

    atom = await Assembler(evd_repo).assemble(item, 0.5, "随便问问", 10)
    assert atom.answer == "简单知识"


# ═══════════════════════════════════════════════════════
# Group 7: RetrievalService 端到端
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_service_query_end_to_end(svc):
    service, knw_repo, _, _, embedder = svc
    await _save_knowledge(knw_repo, embedder, tag="e2e", title="2026年4月水电燃气支出",
                          body={"items": [{"category": "电费", "amount": 210.0}]})

    atom = await service.query("水电燃气花了多少钱", {"top_k": 5, "scope": "shared:home"})
    assert atom.source_knowledge
    assert atom.latency_ms >= 0
    assert "210.00" in atom.answer


@pytest.mark.asyncio
async def test_service_query_empty_db(svc):
    service, _, _, _, _ = svc
    atom = await service.query("什么都没有")
    assert atom.answer == ""
    assert atom.source_evidence == []
    assert atom.latency_ms >= 0


@pytest.mark.asyncio
async def test_service_filters_forgotten(svc):
    service, knw_repo, _, _, embedder = svc
    item = await _save_knowledge(knw_repo, embedder, tag="fgt", title="应被遗忘的内容")
    await knw_repo.update_status(item.id, KnowledgeStatus.FORGOTTEN)

    atom = await service.query("应被遗忘的内容")
    assert atom.source_knowledge != item.id


@pytest.mark.asyncio
async def test_service_runs_three_channels_concurrently(svc, monkeypatch):
    service, _, _, _, _ = svc
    from backend.foundation import retrieval as retrieval_module

    started = 0
    all_started = asyncio.Event()

    async def wait_for_other_channels(*_args, **_kwargs):
        nonlocal started
        started += 1
        if started == 3:
            all_started.set()
        await all_started.wait()
        return []

    monkeypatch.setattr(retrieval_module.BM25Channel, "search", wait_for_other_channels)
    monkeypatch.setattr(retrieval_module.ANNChannel, "search", wait_for_other_channels)
    monkeypatch.setattr(retrieval_module.GraphChannel, "search", wait_for_other_channels)

    atom = await asyncio.wait_for(service.query("并发事实查询"), timeout=0.5)
    assert started == 3
    assert atom.answer == ""


@pytest.mark.asyncio
async def test_service_never_returns_other_scope(svc):
    service, knw_repo, _, _, embedder = svc
    allowed = await _save_knowledge(
        knw_repo, embedder, tag="alice", title="隔离账单", scope="user:alice"
    )
    await _save_knowledge(
        knw_repo, embedder, tag="bob", title="隔离账单", scope="user:bob"
    )

    atom = await service.query("隔离账单", {"scope": "user:alice"})
    assert atom.source_knowledge == allowed.id


# ═══════════════════════════════════════════════════════
# Group 8: /memory/query API 端点
# ═══════════════════════════════════════════════════════

def test_api_memory_query_endpoint(tmp_path):
    from fastapi.testclient import TestClient

    from backend.foundation.api.http_app import app
    from backend.foundation.api import di as di_module

    # 覆盖 DI：注入 StubTextEmbedder 的 RetrievalService
    async def override_get_retrieval_service():
        db_path = str(tmp_path / "api.db")
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row

        import sqlite3 as _sqlite3

        sync_conn = _sqlite3.connect(db_path)
        init_db_on_connection(sync_conn)
        sync_conn.close()

        knw_repo = SqliteKnowledgeRepo(db)
        ent_repo = SqliteEntityRepo(db)
        evd_repo = SqliteEvidenceRepo(db)
        embedder = StubTextEmbedder()

        item = KnowledgeItem(
            id=_knw_id("api"), kind=KnowledgeKind.FACT, title="家庭支出清单",
            body={"items": [{"category": "电费", "amount": 210.0}]},
            scope="shared:home", created_at=NOW, updated_at=NOW,
        )
        await knw_repo.save(item)
        text = " ".join(str(p) for p in [item.title, item.kind, item.body])
        await knw_repo.save_vector(item.id, embedder.dim, _quantize_bytes(embedder.embed(text)))

        return RetrievalService(knw_repo, ent_repo, evd_repo, embedder)

    app.dependency_overrides[di_module.get_retrieval_service] = override_get_retrieval_service
    try:
        with TestClient(app) as client:
            resp = client.post("/memory/query", json={"text": "家庭支出清单花了多少钱", "context_hint": {"top_k": 5}})
            assert resp.status_code == 200
            data = resp.json()
            assert data["source_knowledge"]
            assert data["latency_ms"] >= 0
    finally:
        app.dependency_overrides.clear()
