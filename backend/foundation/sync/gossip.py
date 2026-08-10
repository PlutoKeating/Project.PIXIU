"""Bounded gossip delivery with retransmission through the persistent oplog."""

from __future__ import annotations

import random
import time
from typing import Protocol

from backend.foundation.core.models import SyncOp

from .models import Peer, PeerStatus
from .protocol import MAX_OPERATIONS_PER_MESSAGE
from .transport import TlsJsonTransport, TransportError


class GossipTransport(Protocol):
    async def send(self, peer: Peer, operations: list[SyncOp]) -> list[str]:
        """Return operation IDs acknowledged by the remote peer."""


class NetworkGossipTransport:
    """Resolve only trusted advertisements, then send over mTLS."""

    def __init__(
        self,
        directory,
        transport: TlsJsonTransport,
        *,
        sender_id: str,
    ) -> None:
        self._directory = directory
        self._transport = transport
        self._sender_id = sender_id

    async def send(self, peer: Peer, operations: list[SyncOp]) -> list[str]:
        advertisement = await self._directory.resolve(peer.id)
        if advertisement is None:
            raise TransportError("paired peer has no trusted LAN endpoint")
        message = {
            "type": "push",
            "sender_id": self._sender_id,
            "operations": [
                operation.model_dump(mode="json") for operation in operations
            ],
        }
        last_error: TransportError | None = None
        for address in advertisement.addresses:
            try:
                response = await self._transport.request(
                    address,
                    advertisement.port,
                    message,
                    server_hostname=advertisement.server_name,
                )
            except TransportError as exc:
                last_error = exc
                continue
            acknowledged = response.get("acknowledged")
            if response.get("ok") is not True or not isinstance(acknowledged, list):
                raise TransportError("peer returned an invalid acknowledgment")
            if any(not isinstance(op_id, str) for op_id in acknowledged):
                raise TransportError("peer acknowledgment IDs are invalid")
            return acknowledged
        raise last_error or TransportError("paired peer has no reachable LAN address")


class GossipEngine:
    """Push pending signed operations to a bounded random peer fanout."""

    def __init__(
        self,
        store,
        transport: GossipTransport,
        *,
        fanout: int = 3,
        rng: random.Random | None = None,
    ) -> None:
        if fanout <= 0:
            raise ValueError("gossip fanout must be positive")
        self._store = store
        self._transport = transport
        self._fanout = fanout
        self._rng = rng or random.Random()

    async def run_once(self, *, now: int | None = None) -> dict[str, int]:
        peers = [
            peer
            for peer in await self._store.list_peers()
            if peer.status == PeerStatus.ONLINE
        ]
        if len(peers) > self._fanout:
            peers = self._rng.sample(peers, self._fanout)
        delivered = 0
        failed = 0
        timestamp = int(time.time()) if now is None else now
        for peer in peers:
            pending = (
                await self._store.pending_ops_for_peer(peer.id)
            )[:MAX_OPERATIONS_PER_MESSAGE]
            if not pending:
                continue
            pending_ids = {operation.op_id for operation in pending}
            try:
                acknowledged = await self._transport.send(peer, pending)
            except (TransportError, ConnectionError, OSError, TimeoutError):
                failed += 1
                await self._store.set_peer_status(
                    peer.id, PeerStatus.OFFLINE, timestamp
                )
                continue
            valid_acknowledgments = [
                op_id for op_id in acknowledged if op_id in pending_ids
            ]
            delivered += await self._store.acknowledge(
                peer.id, valid_acknowledgments, timestamp
            )
        return {
            "peers_attempted": len(peers),
            "operations_delivered": delivered,
            "peers_failed": failed,
        }
