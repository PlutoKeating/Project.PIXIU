"""Tests for flow/ — 短/中/长期记忆生命周期。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.core.models import KnowledgeItem, KnowledgeKind, KnowledgeStatus
from backend.foundation.flow import (
    ContextStatus,
    FlowContextNotFound,
    FlowService,
    InvalidFlowTransition,
    KnowledgeNotFound,
    MemoryTier,
    SqliteFlowStore,
)
from backend.foundation.flow.ttl import (
    DEFAULT_MID_TERM_TTL_SECONDS,
    DEFAULT_SHORT_TERM_TTL_SECONDS,
)
from backend.foundation.storage.repository import SqliteKnowledgeRepo
from backend.foundation.storage.schema import init_db_on_connection

NOW = 2_000_000_000


def _knw_id(tag: str) -> str:
    return f"knw_{(tag + '0' * 26)[:26]}"


@pytest_asyncio.fixture
async def flow_env(tmp_path: Path):
    db_path = str(tmp_path / "flow.db")
    sync_db = sqlite3.connect(db_path)
    init_db_on_connection(sync_db)
    sync_db.close()

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    store = SqliteFlowStore(db)
    knowledge_repo = SqliteKnowledgeRepo(db)
    promoted: list[str] = []

    async def handler(context):
        knowledge_id = _knw_id(f"p{len(promoted)}")
        await knowledge_repo.save(
            KnowledgeItem(
                id=knowledge_id,
                kind=KnowledgeKind.FACT,
                title=str(context.payload.get("title", "context")),
                body=dict(context.payload),
                scope=context.scope,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        promoted.append(context.id)
        return knowledge_id

    service = FlowService(store, handler, knowledge_repo)
    yield service, store, knowledge_repo, promoted, db_path
    await db.close()


@pytest.mark.asyncio
async def test_remember_uses_tier_default_ttls(flow_env):
    service, store, _, _, _ = flow_env
    short = await service.remember(
        MemoryTier.SHORT_TERM, {"title": "short"}, "user:alice", now=NOW
    )
    mid = await service.remember(
        MemoryTier.MID_TERM, {"title": "mid"}, "user:alice", now=NOW
    )
    assert short.expires_at == NOW + DEFAULT_SHORT_TERM_TTL_SECONDS
    assert mid.expires_at == NOW + DEFAULT_MID_TERM_TTL_SECONDS
    assert (await store.get(short.id)).payload == {"title": "short"}


@pytest.mark.asyncio
async def test_context_survives_database_reopen(tmp_path: Path):
    db_path = str(tmp_path / "reopen.db")
    sync_db = sqlite3.connect(db_path)
    init_db_on_connection(sync_db)
    sync_db.close()

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row

    async def unused_handler(context):
        raise AssertionError("promotion is not part of this test")

    service = FlowService(SqliteFlowStore(db), unused_handler)
    context = await service.remember(
        MemoryTier.SHORT_TERM, {"text": "persisted"}, "user:alice", now=NOW
    )
    await db.close()

    reopened = await aiosqlite.connect(db_path)
    reopened.row_factory = aiosqlite.Row
    try:
        saved = await SqliteFlowStore(reopened).get(context.id)
        assert saved is not None
        assert saved.payload == {"text": "persisted"}
    finally:
        await reopened.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", [MemoryTier.SHORT_TERM, MemoryTier.MID_TERM])
async def test_promote_short_and_mid_term_is_idempotent(flow_env, tier):
    service, store, knowledge_repo, promoted, _ = flow_env
    context = await service.remember(tier, {"title": tier.value}, "user:alice", now=NOW)

    first = await service.promote(tier, [context.id], "user:alice", now=NOW + 1)
    second = await service.promote(tier, [context.id], "user:alice", now=NOW + 2)

    assert second == first
    assert promoted == [context.id]
    saved = await store.get(context.id)
    assert saved.status == ContextStatus.PROMOTED
    assert saved.expires_at is None
    assert await knowledge_repo.get(first[0]) is not None


@pytest.mark.asyncio
async def test_promote_prevalidates_entire_batch_and_hides_other_scope(flow_env):
    service, _, _, promoted, _ = flow_env
    context = await service.remember(
        MemoryTier.SHORT_TERM, {"title": "private"}, "user:alice", now=NOW
    )
    with pytest.raises(FlowContextNotFound):
        await service.promote(
            MemoryTier.SHORT_TERM,
            [context.id, "ctx_ZZZZZZZZZZZZZZZZZZZZZZZZZZ"],
            "user:alice",
        )
    with pytest.raises(FlowContextNotFound):
        await service.promote(MemoryTier.SHORT_TERM, [context.id], "user:bob")
    assert promoted == []


@pytest.mark.asyncio
async def test_promote_rejects_wrong_tier(flow_env):
    service, _, _, _, _ = flow_env
    context = await service.remember(
        MemoryTier.MID_TERM, {"title": "mid"}, "shared:home", now=NOW
    )
    with pytest.raises(InvalidFlowTransition):
        await service.promote(MemoryTier.SHORT_TERM, [context.id], "shared:home")


@pytest.mark.asyncio
async def test_demote_creates_snapshot_without_mutating_long_term(flow_env):
    service, _, knowledge_repo, _, _ = flow_env
    item = KnowledgeItem(
        id=_knw_id("source"),
        kind=KnowledgeKind.WORKFLOW,
        title="报销流程",
        body={"steps": ["提交", "审批"]},
        scope="shared:team",
        created_at=NOW,
        updated_at=NOW,
    )
    await knowledge_repo.save(item)

    context = await service.demote(
        item.id,
        MemoryTier.MID_TERM,
        "shared:team",
        ttl_seconds=60,
        now=NOW,
    )
    assert context.payload["raw"]["source_knowledge"] == item.id
    assert context.expires_at == NOW + 60
    assert (await knowledge_repo.get(item.id)).status == KnowledgeStatus.ACTIVE

    with pytest.raises(KnowledgeNotFound):
        await service.demote(item.id, MemoryTier.SHORT_TERM, "user:alice")


@pytest.mark.asyncio
async def test_ttl_sweep_expires_at_boundary_and_wipes_payload(flow_env):
    service, store, _, _, _ = flow_env
    context = await service.remember(
        MemoryTier.SHORT_TERM,
        {"secret": "ephemeral"},
        "user:alice",
        ttl_seconds=10,
        now=NOW,
    )
    assert await service.sweep_expired(now=NOW + 9) == []
    assert await service.sweep_expired(now=NOW + 10) == [context.id]
    expired = await store.get(context.id)
    assert expired.status == ContextStatus.EXPIRED
    assert expired.payload == {}
    with pytest.raises(InvalidFlowTransition):
        await service.promote(MemoryTier.SHORT_TERM, [context.id], "user:alice")


@pytest.mark.asyncio
async def test_ttl_never_expires_promoted_context(flow_env):
    service, store, _, _, _ = flow_env
    context = await service.remember(
        MemoryTier.SHORT_TERM,
        {"title": "keep audit"},
        "user:alice",
        ttl_seconds=1,
        now=NOW,
    )
    await service.promote(MemoryTier.SHORT_TERM, [context.id], "user:alice", now=NOW)
    assert await service.sweep_expired(now=NOW + 100) == []
    assert (await store.get(context.id)).status == ContextStatus.PROMOTED
