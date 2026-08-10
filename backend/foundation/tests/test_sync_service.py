"""Phase 3 SyncService：配对、签名操作、反熵、GC 与调度。"""

from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.sync import (
    InvalidSyncOperation,
    PairingError,
    PairingMethod,
    ScopeNotShareable,
    SqliteSyncStore,
    SyncService,
)
from backend.foundation.sync.anti_entropy import AntiEntropy
from backend.foundation.sync.gc import TombstoneGC
from backend.foundation.sync.scheduler import BackoffPolicy, SyncScheduler

NOW = 2_000_000_000
PASSPHRASE = "phase3-service-test-passphrase"


async def _node(
    root: Path,
    filename: str,
    name: str,
    domain: str = "shared:home",
):
    db_path = str(root / filename)
    sync_db = sqlite3.connect(db_path)
    init_db_on_connection(sync_db)
    sync_db.close()
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    store = SqliteSyncStore(db)
    service = SyncService(
        store,
        device_name=name,
        domain=domain,
        key_passphrase=PASSPHRASE,
    )
    return service, store, db


@pytest_asyncio.fixture
async def nodes(tmp_path: Path):
    a = await _node(tmp_path, "a.db", "书房工作站")
    b = await _node(tmp_path, "b.db", "客厅一体机")
    yield a, b
    await a[2].close()
    await b[2].close()


async def _pair_both(a: SyncService, b: SyncService) -> None:
    token_b = await b.create_pairing_token(PairingMethod.QR, now=NOW)
    await a.pair(PairingMethod.QR, token_b, now=NOW)
    token_a = await a.create_pairing_token(PairingMethod.QR, now=NOW)
    await b.pair(PairingMethod.QR, token_a, now=NOW)


@pytest.mark.asyncio
async def test_qr_pairing_builds_trust_and_peer_views(nodes):
    (a, _, _), (b, _, _) = nodes
    token = await b.create_pairing_token(PairingMethod.QR, now=NOW)
    peer = await a.pair(PairingMethod.QR, token, now=NOW)
    assert peer.name == "客厅一体机"
    assert peer.domain == "shared:home"
    peers = await a.peers()
    assert len(peers) == 2
    assert peers[0]["is_self"] is True
    assert peers[1]["id"] == peer.id


@pytest.mark.asyncio
async def test_pin_pairing_rejects_wrong_pin_and_replay(nodes):
    (a, _, _), (b, _, _) = nodes
    token = await b.create_pairing_token(
        PairingMethod.PIN, pin="123456", now=NOW
    )
    with pytest.raises(PairingError, match="PIN"):
        await a.pair(PairingMethod.PIN, token, pin="654321", now=NOW)
    await a.pair(PairingMethod.PIN, token, pin="123456", now=NOW)
    with pytest.raises(PairingError, match="already"):
        await a.pair(PairingMethod.PIN, token, pin="123456", now=NOW)


@pytest.mark.asyncio
async def test_pairing_rejects_tamper_expiry_and_domain(nodes, tmp_path: Path):
    (a, _, _), (b, _, _) = nodes
    token = await b.create_pairing_token(PairingMethod.QR, now=NOW)
    payload = json.loads(base64.urlsafe_b64decode(token))
    payload["device_name"] = "伪造设备"
    tampered = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode()
    with pytest.raises(PairingError, match="signature"):
        await a.pair(PairingMethod.QR, tampered, now=NOW)
    with pytest.raises(PairingError, match="expired"):
        await a.pair(PairingMethod.QR, token, now=NOW + 301)

    other, _, other_db = await _node(
        tmp_path, "other.db", "办公电脑", domain="shared:office"
    )
    try:
        with pytest.raises(PairingError, match="domain"):
            await other.pair(PairingMethod.QR, token, now=NOW)
    finally:
        await other_db.close()


@pytest.mark.asyncio
async def test_private_scope_never_enters_oplog(nodes):
    (a, store, _), _ = nodes
    with pytest.raises(ScopeNotShareable):
        await a.record_local("knowledge:private", {"x": 1}, "user:alice")
    assert await store.list_ops() == []


@pytest.mark.asyncio
async def test_signed_concurrent_updates_converge(nodes):
    (a, store_a, _), (b, store_b, _) = nodes
    await _pair_both(a, b)
    op_a = await a.record_local(
        "knowledge:expense", {"amount": 156}, "shared:home", now=NOW
    )
    op_b = await b.record_local(
        "knowledge:expense", {"amount": 186}, "shared:home", now=NOW
    )

    assert await a.receive_ops([op_b]) == 1
    assert await b.receive_ops([op_a]) == 1
    state_a = await store_a.get_state("knowledge:expense")
    state_b = await store_b.get_state("knowledge:expense")
    assert state_a == state_b
    assert set(state_a.vclock) == {(await a.initialize()).id, (await b.initialize()).id}


@pytest.mark.asyncio
async def test_remote_batch_is_verified_before_any_write(nodes):
    (a, store_a, _), (b, _, _) = nodes
    await _pair_both(a, b)
    valid = await b.record_local("knowledge:one", {"v": 1}, "shared:home", now=NOW)
    signed = await b.record_local("knowledge:two", {"v": 2}, "shared:home", now=NOW)
    tampered = signed.model_copy(
        update={"payload": {**signed.payload, "value": {"v": 999}}}
    )
    with pytest.raises(InvalidSyncOperation, match="signature"):
        await a.receive_ops([valid, tampered])
    assert await store_a.list_ops() == []


@pytest.mark.asyncio
async def test_anti_entropy_returns_delta_and_reconciles(nodes):
    (a, store_a, _), (b, store_b, _) = nodes
    await _pair_both(a, b)
    operation = await b.record_local(
        "knowledge:offline", {"value": "created offline"}, "shared:home", now=NOW
    )
    anti_a = AntiEntropy(store_a, a.receive_ops)
    anti_b = AntiEntropy(store_b, b.receive_ops)
    summary_a = await anti_a.summary()
    delta = await anti_b.delta_for(set(summary_a["op_ids"]))
    assert [op.op_id for op in delta] == [operation.op_id]
    assert await anti_a.reconcile(delta, now=NOW + 10) == 1
    assert (await anti_a.summary())["digest"] == (await anti_b.summary())["digest"]
    assert (await a.status()).last_anti_entropy_ts == NOW + 10


@pytest.mark.asyncio
async def test_tombstone_gc_waits_for_all_active_peer_acks(nodes):
    (a, store_a, _), (b, _, _) = nodes
    await _pair_both(a, b)
    peer_b = await b.initialize()
    tombstone = await a.record_local(
        "knowledge:forgotten",
        {},
        "shared:home",
        deleted=True,
        now=NOW,
    )
    gc = TombstoneGC(store_a, retention_seconds=0)
    assert await gc.collect(now=NOW) == []
    await a.acknowledge(peer_b.id, [tombstone.op_id], now=NOW)
    assert await gc.collect(now=NOW) == ["knowledge:forgotten"]
    assert await store_a.get_state("knowledge:forgotten") is None


@pytest.mark.asyncio
async def test_scheduler_uses_bounded_backoff_and_resets():
    outcomes = iter([False, False, True])

    async def run_round():
        if not next(outcomes):
            raise ConnectionError("offline")

    scheduler = SyncScheduler(
        run_round,
        interval_seconds=30,
        backoff=BackoffPolicy(base_seconds=1, max_seconds=2),
    )
    assert await scheduler.run_once() == 1
    assert await scheduler.run_once() == 2
    assert await scheduler.run_once() == 30
