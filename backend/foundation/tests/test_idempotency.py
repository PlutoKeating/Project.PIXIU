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
    IdempotencyCompleted,
    IdempotencyFailed,
    IdempotencyInProgress,
    IdempotencyNotFound,
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
async def test_authorized_failed_claim_can_retry_once_with_audit(store):
    await store.claim("turn-1", "hash-1")
    await store.fail("turn-1", "hash-1")

    authorization = await store.authorize_retry(
        "turn-1", "hash-1", "operator verified downstream state"
    )
    retry = await store.claim("turn-1", "hash-1")

    assert authorization.recovery_count == 1
    assert authorization.authorized is True
    assert retry.status == ClaimStatus.NEW
    with pytest.raises(IdempotencyInProgress):
        await store.claim("turn-1", "hash-1")


@pytest.mark.asyncio
async def test_retry_authorization_is_idempotent_until_consumed(store):
    await store.claim("turn-1", "hash-1")
    await store.fail("turn-1", "hash-1")

    first = await store.authorize_retry("turn-1", "hash-1", "checked once")
    second = await store.authorize_retry("turn-1", "hash-1", "checked twice")

    assert first.recovery_count == 1
    assert second.recovery_count == 1
    assert second.authorized_at == first.authorized_at


@pytest.mark.asyncio
async def test_retry_authorization_rejects_wrong_or_nonfailed_receipt(store):
    with pytest.raises(IdempotencyNotFound):
        await store.authorize_retry("missing", "hash-1", "checked")

    await store.claim("active", "hash-1")
    with pytest.raises(IdempotencyConflict):
        await store.authorize_retry("active", "hash-2", "checked")
    with pytest.raises(IdempotencyInProgress):
        await store.authorize_retry("active", "hash-1", "checked")

    await store.complete("active", "hash-1", {"ok": True})
    with pytest.raises(IdempotencyCompleted):
        await store.authorize_retry("active", "hash-1", "checked")


@pytest.mark.asyncio
async def test_failed_retry_can_be_reauthorized_after_another_failure(store):
    await store.claim("turn-1", "hash-1")
    await store.fail("turn-1", "hash-1")
    await store.authorize_retry("turn-1", "hash-1", "first recovery")
    await store.claim("turn-1", "hash-1")
    await store.fail("turn-1", "hash-1")

    authorization = await store.authorize_retry(
        "turn-1", "hash-1", "second recovery"
    )

    assert authorization.recovery_count == 2


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


@pytest.mark.asyncio
async def test_retry_authorization_survives_connection_restart(tmp_path):
    path = str(tmp_path / "pixiu.db")
    sync_db = sqlite3.connect(path)
    init_db_on_connection(sync_db)
    sync_db.close()

    first_db = await aiosqlite.connect(path)
    first_db.row_factory = aiosqlite.Row
    first = AgentIngestReceiptStore(first_db)
    await first.claim("turn-1", "hash-1")
    await first.fail("turn-1", "hash-1")
    await first.authorize_retry("turn-1", "hash-1", "restart verified")
    await first_db.close()

    second_db = await aiosqlite.connect(path)
    second_db.row_factory = aiosqlite.Row
    try:
        retry = await AgentIngestReceiptStore(second_db).claim("turn-1", "hash-1")
    finally:
        await second_db.close()

    assert retry.status == ClaimStatus.NEW
