"""Phase 3 LAN adapters; tests use encoded objects and in-memory transports only."""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import replace
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.sync import PairingMethod, SqliteSyncStore, SyncService
from backend.foundation.sync.discovery import (
    DiscoveryError,
    PeerAdvertisement,
    TrustedPeerDirectory,
    build_service_info,
    parse_service_info,
)
from backend.foundation.sync.gossip import GossipEngine
from backend.foundation.sync.protocol import SyncProtocol
from backend.foundation.sync.runtime import SyncRuntime
from backend.foundation.sync.transport import (
    MAX_MESSAGE_BYTES,
    TransportError,
    _encode_message,
    create_mtls_context,
)

PASSPHRASE = "phase3-network-test-passphrase"
NOW = 2_000_000_000


async def _node(root: Path, filename: str, name: str):
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
        domain="shared:home",
        key_passphrase=PASSPHRASE,
    )
    return service, store, db


@pytest_asyncio.fixture
async def nodes(tmp_path: Path):
    a = await _node(tmp_path, "network-a.db", "书房工作站")
    b = await _node(tmp_path, "network-b.db", "客厅一体机")
    identity_a = await a[0].initialize()
    identity_b = await b[0].initialize()
    await a[0].pair(
        PairingMethod.QR,
        await b[0].create_pairing_token(PairingMethod.QR, now=NOW),
        now=NOW,
    )
    await b[0].pair(
        PairingMethod.QR,
        await a[0].create_pairing_token(PairingMethod.QR, now=NOW),
        now=NOW,
    )
    yield a, b, identity_a, identity_b
    await a[2].close()
    await b[2].close()


def test_mdns_advertisement_round_trip_contains_public_metadata_only():
    public_key = b"k" * 32
    info = build_service_info(
        device_id="dev_AAAAAAAAAAAAAAAAAAAAAAAAAA",
        name="书房工作站",
        domain="shared:home",
        public_key=public_key,
        addresses=["192.168.1.20", "127.0.0.1"],
        port=8766,
        server_name="study.pixiu.local",
    )
    advertisement = parse_service_info(info)
    assert advertisement.public_key == public_key
    assert advertisement.domain == "shared:home"
    assert advertisement.addresses == ("192.168.1.20", "127.0.0.1")
    assert b"private_key" not in info.properties
    assert b"passphrase" not in info.properties


def test_mdns_rejects_public_or_private_scope_advertisements():
    common = {
        "device_id": "dev_AAAAAAAAAAAAAAAAAAAAAAAAAA",
        "name": "device",
        "public_key": b"k" * 32,
        "port": 8766,
        "server_name": "device.pixiu.local",
    }
    with pytest.raises(DiscoveryError, match="private"):
        build_service_info(
            **common, domain="shared:home", addresses=["8.8.8.8"]
        )
    with pytest.raises(ValueError, match="shared"):
        build_service_info(
            **common, domain="user:alice", addresses=["127.0.0.1"]
        )


@pytest.mark.asyncio
async def test_directory_requires_paired_domain_and_public_key(nodes):
    (a, store_a, _), (_, _, _), _, identity_b = nodes
    directory = TrustedPeerDirectory(store_a, "shared:home")
    advertisement = PeerAdvertisement(
        device_id=identity_b.id,
        name=identity_b.name,
        domain=identity_b.domain,
        public_key=identity_b.public_key,
        addresses=("127.0.0.1",),
        port=8766,
        server_name="peer.pixiu.local",
    )
    assert await directory.accept(advertisement) is True
    assert await directory.resolve(identity_b.id) == advertisement
    assert await directory.accept(
        replace(advertisement, public_key=b"x" * 32)
    ) is False
    await a.revoke(identity_b.id)
    assert await directory.resolve(identity_b.id) is None


def test_transport_enforces_size_and_tls_files(tmp_path: Path):
    with pytest.raises(TransportError, match="1 MiB"):
        _encode_message({"payload": "x" * MAX_MESSAGE_BYTES})
    with pytest.raises(TransportError, match="does not exist"):
        create_mtls_context(
            certfile=str(tmp_path / "missing-cert.pem"),
            keyfile=str(tmp_path / "missing-key.pem"),
            cafile=str(tmp_path / "missing-ca.pem"),
            server_side=False,
        )


@pytest.mark.asyncio
async def test_protocol_accepts_only_paired_sender_and_signed_operations(nodes):
    (a, store_a, _), (b, _, _), _, identity_b = nodes
    operation = await b.record_local(
        "knowledge:shared", {"amount": 434.5}, "shared:home", now=NOW
    )
    protocol = SyncProtocol(a, store_a)
    response = await protocol.handle(
        {
            "type": "push",
            "sender_id": identity_b.id,
            "operations": [operation.model_dump(mode="json")],
        }
    )
    assert response["ok"] is True
    assert response["acknowledged"] == [operation.op_id]
    assert (await store_a.get_state("knowledge:shared")).payload == {
        "amount": 434.5
    }
    with pytest.raises(TransportError, match="paired"):
        await protocol.handle(
            {
                "type": "push",
                "sender_id": "dev_ZZZZZZZZZZZZZZZZZZZZZZZZZZ",
                "operations": [],
            }
        )


@pytest.mark.asyncio
async def test_gossip_acknowledges_pending_ops_without_network(nodes):
    (a, store_a, _), (_, _, _), _, identity_b = nodes
    operation = await a.record_local(
        "knowledge:offline", {"value": "queued"}, "shared:home", now=NOW
    )

    class MemoryTransport:
        async def send(self, peer, operations):
            assert peer.id == identity_b.id
            assert [item.op_id for item in operations] == [operation.op_id]
            return [operation.op_id, "sync_ZZZZZZZZZZZZZZZZZZZZZZZZZZ"]

    result = await GossipEngine(store_a, MemoryTransport()).run_once(now=NOW + 1)
    assert result == {
        "peers_attempted": 1,
        "operations_delivered": 1,
        "peers_failed": 0,
    }
    assert await store_a.pending_for_peer(identity_b.id) == 0


@pytest.mark.asyncio
async def test_gossip_marks_failed_peer_offline(nodes):
    (_, store_a, _), (_, _, _), _, identity_b = nodes

    class FailingTransport:
        async def send(self, peer, operations):
            raise TransportError("offline")

    service_a = nodes[0][0]
    await service_a.record_local(
        "knowledge:retry", {"value": "queued"}, "shared:home", now=NOW
    )
    result = await GossipEngine(store_a, FailingTransport()).run_once(now=NOW + 1)
    assert result["peers_failed"] == 1
    assert (await store_a.get_peer(identity_b.id)).status.value == "OFFLINE"




@pytest.mark.asyncio
async def test_runtime_lifecycle_uses_in_memory_adapters(nodes):
    (a, store_a, _), (_, _, _), identity_a, identity_b = nodes
    advertisement = PeerAdvertisement(
        device_id=identity_b.id,
        name=identity_b.name,
        domain=identity_b.domain,
        public_key=identity_b.public_key,
        addresses=("127.0.0.1",),
        port=8766,
        server_name="peer.pixiu.local",
    )

    class MemoryDiscovery:
        def __init__(self):
            self.registered = None
            self.closed = False

        async def register(self, info):
            self.registered = info

        async def discover(self, timeout_seconds):
            return [advertisement]

        async def close(self):
            self.closed = True

    class MemoryGossip:
        async def run_once(self):
            return {
                "peers_attempted": 1,
                "operations_delivered": 0,
                "peers_failed": 0,
            }

    class MemoryServer:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    discovery = MemoryDiscovery()
    server = MemoryServer()

    async def start_server():
        return server

    runtime = SyncRuntime(
        identity=identity_a,
        store=store_a,
        discovery=discovery,
        directory=TrustedPeerDirectory(store_a, "shared:home"),
        gossip=MemoryGossip(),
        service_info=object(),
        server_starter=start_server,
        interval_seconds=60,
        discovery_timeout_seconds=0.01,
    )
    result = await runtime.run_once()
    assert result["trusted_peers_discovered"] == 1
    await runtime.start()
    assert runtime.running is True
    assert discovery.registered is not None
    await runtime.stop()
    assert discovery.closed is True
    assert server.closed is True


@pytest.mark.asyncio
async def test_runtime_stop_cancels_an_in_flight_round(nodes):
    (_, store_a, _), _, identity_a, _ = nodes
    round_started = asyncio.Event()

    class BlockingDiscovery:
        def __init__(self):
            self.closed = False

        async def register(self, _info):
            return None

        async def discover(self, _timeout_seconds):
            round_started.set()
            await asyncio.Event().wait()

        async def close(self):
            self.closed = True

    class MemoryServer:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    class UnusedGossip:
        async def run_once(self):
            raise AssertionError("gossip must not run while discovery is blocked")

    discovery = BlockingDiscovery()
    server = MemoryServer()

    async def start_server():
        return server

    runtime = SyncRuntime(
        identity=identity_a,
        store=store_a,
        discovery=discovery,
        directory=TrustedPeerDirectory(store_a, "shared:home"),
        gossip=UnusedGossip(),
        service_info=object(),
        server_starter=start_server,
        interval_seconds=60,
    )
    await runtime.start()
    await asyncio.wait_for(round_started.wait(), timeout=0.5)

    await asyncio.wait_for(runtime.stop(), timeout=0.5)

    assert runtime.running is False
    assert discovery.closed is True
    assert server.closed is True
