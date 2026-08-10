"""PIXIU 去中心化同步服务。"""

from __future__ import annotations

import base64
import json
import time

from cryptography.exceptions import InvalidSignature

from backend.foundation.core.idgen import gen_sync_op_id
from backend.foundation.core.models import SyncOp

from .crdt import LWWElementSet, increment_clock, record_from_op
from .identity import IdentityManager
from .models import (
    DeviceIdentity,
    PairingMethod,
    Peer,
    PeerStatus,
    SyncStatus,
    validate_shared_scope,
)
from .pairing import PairingError, PairingManager
from .store import SqliteSyncStore


class PeerNotFound(LookupError):
    """目标 peer 不存在或已撤销。"""


class ScopeNotShareable(ValueError):
    """私有 scope 不允许进入同步队列。"""


class InvalidSyncOperation(ValueError):
    """远端操作结构、签名或信任关系无效。"""


def _operation_message(op: SyncOp) -> bytes:
    payload = dict(op.payload)
    payload.pop("signature", None)
    body = {
        "op_id": op.op_id,
        "entity": op.entity,
        "payload": payload,
        "vclock": op.vclock,
        "ts": op.ts,
    }
    return json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


class SyncService:
    """身份、配对、签名操作、CRDT 与状态查询的统一门面。"""

    def __init__(
        self,
        store: SqliteSyncStore,
        *,
        device_name: str,
        domain: str,
        key_passphrase: str,
        materializer=None,
    ) -> None:
        self._store = store
        self._device_name = device_name
        self._domain = validate_shared_scope(domain)
        self._identity_manager = IdentityManager(store, key_passphrase)
        self._identity: DeviceIdentity | None = None
        self._crdt = LWWElementSet()
        self._materializer = materializer

    async def initialize(self) -> DeviceIdentity:
        if self._identity is None:
            self._identity = await self._identity_manager.load_or_create(
                self._device_name, self._domain
            )
        return self._identity

    async def create_pairing_token(
        self,
        method: PairingMethod,
        *,
        pin: str | None = None,
        ttl_seconds: int = 300,
        now: int | None = None,
    ) -> str:
        identity = await self.initialize()
        return PairingManager(
            self._store, self._identity_manager, identity
        ).create_token(method, pin=pin, ttl_seconds=ttl_seconds, now=now)

    async def pair(
        self,
        method: PairingMethod,
        token: str,
        *,
        pin: str | None = None,
        now: int | None = None,
    ) -> Peer:
        identity = await self.initialize()
        return await PairingManager(
            self._store, self._identity_manager, identity
        ).pair(method, token, pin=pin, now=now)

    async def record_local(
        self,
        entity: str,
        value: dict,
        scope: str,
        *,
        deleted: bool = False,
        now: int | None = None,
    ) -> SyncOp:
        if not isinstance(value, dict):
            raise InvalidSyncOperation("operation value must be an object")
        try:
            validate_shared_scope(scope)
        except ValueError as exc:
            raise ScopeNotShareable(str(exc)) from exc
        identity = await self.initialize()
        if scope != identity.domain:
            raise ScopeNotShareable("scope is outside the local shared domain")
        if "scope" in value and value["scope"] != scope:
            raise InvalidSyncOperation("operation value scope does not match envelope")

        current = await self._store.get_state(entity)
        clock = increment_clock(current.vclock if current else {}, identity.id)
        op = SyncOp(
            op_id=gen_sync_op_id(),
            entity=entity,
            payload={
                "scope": scope,
                "value": value,
                "deleted": deleted,
                "origin": identity.id,
            },
            vclock=clock,
            ts=int(time.time()) if now is None else now,
        )
        signature = self._identity_manager.sign(identity, _operation_message(op))
        op = op.model_copy(
            update={
                "payload": {
                    **op.payload,
                    "signature": base64.b64encode(signature).decode(),
                }
            }
        )
        await self._store.append_op(op)
        await self._store.save_state(self._crdt.resolve(current, op))
        return op

    async def receive_ops(self, operations: list[SyncOp]) -> int:
        identity = await self.initialize()
        # 整批先验签和校验，避免恶意批次产生部分落库副作用。
        for op in operations:
            await self._verify_operation(op, identity)

        accepted = 0
        for op in operations:
            if await self._store.get_op(op.op_id) is not None:
                continue
            current = await self._store.get_state(op.entity)
            resolved = self._crdt.resolve(current, op)
            if (
                self._materializer is not None
                and (current is None or resolved.op_id != current.op_id)
            ):
                await self._materializer(resolved)
            if not await self._store.append_op(op):
                continue
            await self._store.save_state(resolved)
            accepted += 1
        return accepted

    async def _verify_operation(
        self, op: SyncOp, identity: DeviceIdentity
    ) -> None:
        record_from_op(op)
        scope = op.payload.get("scope")
        origin = op.payload.get("origin")
        signature_text = op.payload.get("signature")
        if scope != identity.domain or not isinstance(origin, str):
            raise InvalidSyncOperation("operation scope or origin is invalid")
        if not isinstance(signature_text, str):
            raise InvalidSyncOperation("operation signature is missing")
        value = op.payload.get("value")
        if isinstance(value, dict) and "scope" in value and value["scope"] != scope:
            raise InvalidSyncOperation("operation value scope does not match envelope")

        if origin == identity.id:
            public_key = identity.public_key
        else:
            peer = await self._store.get_peer(origin)
            if peer is None or peer.status == PeerStatus.REVOKED:
                raise InvalidSyncOperation("operation origin is not trusted")
            public_key = peer.public_key
        try:
            signature = base64.b64decode(signature_text, validate=True)
            self._identity_manager.verify(
                public_key, signature, _operation_message(op)
            )
        except (ValueError, InvalidSignature) as exc:
            raise InvalidSyncOperation("operation signature is invalid") from exc

    async def peers(self) -> list[dict]:
        identity = await self.initialize()
        result = [
            {
                "id": identity.id,
                "name": identity.name,
                "is_self": True,
                "status": PeerStatus.ONLINE.value,
                "last_sync_ts": None,
                "pending_ops": 0,
            }
        ]
        result.extend(
            {
                "id": peer.id,
                "name": peer.name,
                "is_self": False,
                "status": peer.status.value,
                "last_sync_ts": peer.last_sync_ts,
                "pending_ops": peer.pending_ops,
            }
            for peer in await self._store.list_peers()
        )
        return result

    async def status(self) -> SyncStatus:
        await self.initialize()
        peers = await self._store.list_peers()
        pending_ids: set[str] = set()
        for peer in peers:
            pending_ids.update(
                op.op_id for op in await self._store.pending_ops_for_peer(peer.id)
            )
        anti_entropy = await self._store.get_meta("last_anti_entropy_ts")
        return SyncStatus(
            domain=self._domain,
            peers_online=1 + sum(peer.status == PeerStatus.ONLINE for peer in peers),
            peers_total=1 + len(peers),
            pending_outgoing_ops=len(pending_ids),
            last_anti_entropy_ts=int(anti_entropy) if anti_entropy else None,
            total_ops_synced=await self._store.total_acknowledgements(),
        )

    async def revoke(self, peer_id: str) -> Peer:
        identity = await self.initialize()
        if peer_id == identity.id:
            raise PeerNotFound(peer_id)
        peer = await self._store.get_peer(peer_id)
        if peer is None or not await self._store.revoke_peer(peer_id):
            raise PeerNotFound(peer_id)
        return peer.model_copy(update={"status": PeerStatus.REVOKED})

    async def acknowledge(
        self, peer_id: str, op_ids: list[str], *, now: int | None = None
    ) -> int:
        peer = await self._store.get_peer(peer_id)
        if peer is None or peer.status == PeerStatus.REVOKED:
            raise PeerNotFound(peer_id)
        return await self._store.acknowledge(
            peer_id, op_ids, int(time.time()) if now is None else now
        )


__all__ = [
    "InvalidSyncOperation",
    "PairingError",
    "PairingMethod",
    "PeerNotFound",
    "ScopeNotShareable",
    "SqliteSyncStore",
    "SyncService",
]
