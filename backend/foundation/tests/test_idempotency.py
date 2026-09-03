"""Durable Agent memory ingestion idempotency tests."""

from __future__ import annotations

import sqlite3

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.storage.idempotency import (
    AgentIngestReceiptStore,
    ClaimStatus,
    IdempotencyConflict,
    IdempotencyFailed,
    IdempotencyInProgress,
)
from backend.foundation.storage.schema import init_db_on_connection


@pytest_asyncio.fixture
async def store(tmp_path):
    path = str(tmp_path / "pixiu.db")
    sync_db = sqlite3.connect(path)
    init_db_on_connection(sync_db)
    sync_db.close()
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    try:
        yield AgentIngestReceiptStore(db)
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_completed_claim_replays_persisted_response(store):
    first = await store.claim("turn-1", "hash-1")
    await store.complete("turn-1", "hash-1", {"evidence_id": "evd_1"})

    replay = await store.claim("turn-1", "hash-1")

    assert first.status == ClaimStatus.NEW
    assert replay.status == ClaimStatus.REPLAY
    assert replay.response == {"evidence_id": "evd_1"}


@pytest.mark.asyncio
async def test_claim_rejects_same_key_with_different_hash(store):
    await store.claim("turn-1", "hash-1")

    with pytest.raises(IdempotencyConflict):
        await store.claim("turn-1", "hash-2")


@pytest.mark.asyncio
async def test_claim_rejects_unfinished_request(store):
    await store.claim("turn-1", "hash-1")

    with pytest.raises(IdempotencyInProgress):
        await store.claim("turn-1", "hash-1")


@pytest.mark.asyncio
async def test_failed_claim_stays_fail_closed(store):
    await store.claim("turn-1", "hash-1")
    await store.fail("turn-1", "hash-1")

    with pytest.raises(IdempotencyFailed):
        await store.claim("turn-1", "hash-1")


@pytest.mark.asyncio
async def test_completed_response_survives_connection_restart(tmp_path):
    path = str(tmp_path / "pixiu.db")
    sync_db = sqlite3.connect(path)
    init_db_on_connection(sync_db)
    sync_db.close()

    first_db = await aiosqlite.connect(path)
    first_db.row_factory = aiosqlite.Row
    first = AgentIngestReceiptStore(first_db)
    await first.claim("turn-1", "hash-1")
    await first.complete("turn-1", "hash-1", {"evidence_id": "evd_1"})
    await first_db.close()

    second_db = await aiosqlite.connect(path)
    second_db.row_factory = aiosqlite.Row
    try:
        replay = await AgentIngestReceiptStore(second_db).claim("turn-1", "hash-1")
    finally:
        await second_db.close()

    assert replay.status == ClaimStatus.REPLAY
    assert replay.response == {"evidence_id": "evd_1"}
