"""基于 oplog 摘要与缺失集的反熵对账。"""

from __future__ import annotations

import hashlib
import time

from backend.foundation.core.models import SyncOp


class AntiEntropy:
    def __init__(self, store, apply_remote) -> None:
        self._store = store
        self._apply_remote = apply_remote

    async def summary(self) -> dict:
        op_ids = sorted(await self._store.op_ids())
        digest = hashlib.sha256("\n".join(op_ids).encode("ascii")).hexdigest()
        return {"digest": digest, "op_ids": op_ids}

    async def delta_for(self, remote_op_ids: set[str]) -> list[SyncOp]:
        return [
            op for op in await self._store.list_ops() if op.op_id not in remote_op_ids
        ]

    async def reconcile(
        self,
        remote_ops: list[SyncOp],
        *,
        now: int | None = None,
    ) -> int:
        accepted = await self._apply_remote(remote_ops)
        timestamp = int(time.time()) if now is None else now
        await self._store.set_meta("last_anti_entropy_ts", str(timestamp))
        return accepted
