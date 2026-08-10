"""Authenticated sync wire protocol. It accepts signed operations only."""

from __future__ import annotations

import time
from typing import Any

from pydantic import ValidationError

from backend.foundation.core.models import SyncOp

from .models import PeerStatus
from .transport import MAX_MESSAGE_BYTES, TransportError

MAX_OPERATIONS_PER_MESSAGE = 256


class SyncProtocol:
    """Server-side push protocol with paired-peer admission control."""

    def __init__(self, service, store) -> None:
        self._service = service
        self._store = store

    async def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        if set(message) != {"type", "sender_id", "operations"}:
            raise TransportError("wire message fields are invalid")
        if message["type"] != "push" or not isinstance(message["sender_id"], str):
            raise TransportError("wire message type or sender is invalid")
        peer = await self._store.get_peer(message["sender_id"])
        if peer is None or peer.status == PeerStatus.REVOKED:
            raise TransportError("wire sender is not a paired peer")
        operations_raw = message["operations"]
        if (
            not isinstance(operations_raw, list)
            or len(operations_raw) > MAX_OPERATIONS_PER_MESSAGE
        ):
            raise TransportError("wire operation batch is invalid")
        try:
            operations = [
                SyncOp.model_validate(operation) for operation in operations_raw
            ]
        except ValidationError as exc:
            raise TransportError("wire operation is invalid") from exc
        accepted = await self._service.receive_ops(operations)
        await self._store.set_peer_status(
            peer.id, PeerStatus.ONLINE, int(time.time())
        )
        return {
            "ok": True,
            "acknowledged": [operation.op_id for operation in operations],
            "accepted": accepted,
        }
