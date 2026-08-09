"""Phase 3 sync 核心：身份、版本向量、LWW 与 SQLite 状态。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio
from cryptography.exceptions import InvalidSignature

from backend.foundation.core.models import SyncOp
from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.sync.crdt import (
    ClockRelation,
    LWWElementSet,
    compare_clocks,
    increment_clock,
    merge_clocks,
)
from backend.foundation.sync.identity import (
    IdentityConfigurationError,
    IdentityManager,
)
from backend.foundation.sync.models import Peer, PeerStatus
from backend.foundation.sync.store import SqliteSyncStore

PASSPHRASE = "phase3-test-passphrase"
NOW = 2_000_000_000


def _device(tag: str) -> str:
    return f"dev_{(tag + '0' * 26)[:26]}"


def _op_id(tag: str) -> str:
    return f"sync_{(tag + '0' * 26)[:26]}"


def _op(
    tag: str,
    *,
    clock: dict[str, int],
    ts: int = NOW,
    value: dict | None = None,
    deleted: bool = False,
) -> SyncOp:
    return SyncOp(
        op_id=_op_id(tag),
        entity="knowledge:knw_demo",
        payload={
            "scope": "shared:home",
            "value": value or {},
            "deleted": deleted,
            "origin": next(iter(clock), "unknown"),
        },
        vclock=clock,
        ts=ts,
    )


@pytest_asyncio.fixture
async def sync_store(tmp_path: Path):
    db_path = str(tmp_path / "sync.db")
    sync_db = sqlite3.connect(db_path)
    init_db_on_connection(sync_db)
    sync_db.close()
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    yield SqliteSyncStore(db)
    await db.close()


def test_vector_clock_relations_and_merge():
    assert compare_clocks({"a": 1}, {"a": 1}) == ClockRelation.EQUAL
    assert compare_clocks({"a": 1}, {"a": 2}) == ClockRelation.BEFORE
    assert compare_clocks({"a": 2}, {"a": 1}) == ClockRelation.AFTER
    assert compare_clocks({"a": 2}, {"b": 1}) == ClockRelation.CONCURRENT
    assert merge_clocks({"a": 1}, {"a": 2, "b": 1}) == {"a": 2, "b": 1}
    assert increment_clock({"a": 2}, "b") == {"a": 2, "b": 1}


def test_lww_concurrent_operations_converge_independent_of_arrival_order():
    first = _op("A", clock={"dev_a": 1}, value={"amount": 156})
    second = _op("B", clock={"dev_b": 1}, value={"amount": 186})
    crdt = LWWElementSet()

    left = crdt.resolve(crdt.resolve(None, first), second)
    right = crdt.resolve(crdt.resolve(None, second), first)

    assert left == right
    assert left.payload == {"amount": 186}


def test_lww_causal_update_beats_newer_wall_clock():
    current = _op("A", clock={"dev_a": 1}, ts=NOW + 100, value={"v": 1})
    causal = _op("B", clock={"dev_a": 2}, ts=NOW, value={"v": 2})
    state = LWWElementSet.resolve(LWWElementSet.resolve(None, current), causal)
    assert state.payload == {"v": 2}


@pytest.mark.asyncio
async def test_identity_is_stable_encrypted_and_signs(sync_store):
    manager = IdentityManager(sync_store, PASSPHRASE)
    identity = await manager.load_or_create("书房工作站", "shared:home", now=NOW)
    again = await manager.load_or_create("书房工作站", "shared:home", now=NOW + 1)
    assert again.id == identity.id
    assert identity.encrypted_private_key.startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----")
    assert len(identity.public_key) == 32

    message = b"pixiu-pairing"
    signature = manager.sign(identity, message)
    manager.verify(identity.public_key, signature, message)
    with pytest.raises(InvalidSignature):
        manager.verify(identity.public_key, signature, b"tampered")

    with pytest.raises(IdentityConfigurationError):
        await IdentityManager(sync_store, "another-passphrase").load_or_create(
            "书房工作站", "shared:home"
        )


@pytest.mark.asyncio
async def test_identity_rejects_private_or_changed_configuration(sync_store):
    with pytest.raises(ValueError, match="shared"):
        await IdentityManager(sync_store, PASSPHRASE).load_or_create(
            "private", "user:alice"
        )
    manager = IdentityManager(sync_store, PASSPHRASE)
    await manager.load_or_create("device-a", "shared:home")
    with pytest.raises(IdentityConfigurationError):
        await manager.load_or_create("device-b", "shared:home")


@pytest.mark.asyncio
async def test_store_persists_ops_state_peers_and_ack(sync_store):
    peer = Peer(
        id=_device("peer"),
        name="客厅一体机",
        domain="shared:home",
        public_key=b"p" * 32,
        status=PeerStatus.ONLINE,
        paired_at=NOW,
    )
    await sync_store.save_peer(peer)
    operation = _op("persist", clock={_device("self"): 1}, value={"x": 1})
    assert await sync_store.append_op(operation) is True
    assert await sync_store.append_op(operation) is False
    record = LWWElementSet.resolve(None, operation)
    await sync_store.save_state(record)

    assert (await sync_store.get_state(operation.entity)).payload == {"x": 1}
    assert await sync_store.pending_for_peer(peer.id) == 1
    assert await sync_store.acknowledge(peer.id, [operation.op_id], NOW + 1) == 1
    assert await sync_store.acknowledge(peer.id, [operation.op_id], NOW + 2) == 0
    saved_peer = await sync_store.get_peer(peer.id)
    assert saved_peer.pending_ops == 0
    assert saved_peer.total_ops_synced == 1


@pytest.mark.asyncio
async def test_revoke_peer_is_idempotent(sync_store):
    peer = Peer(
        id=_device("peer"),
        name="笔记本",
        domain="shared:home",
        public_key=b"p" * 32,
        paired_at=NOW,
    )
    await sync_store.save_peer(peer)
    assert await sync_store.revoke_peer(peer.id) is True
    assert await sync_store.revoke_peer(peer.id) is False
    assert await sync_store.list_peers() == []
