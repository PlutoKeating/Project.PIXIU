"""全网 ACK 后的 tombstone 回收。"""

from __future__ import annotations

import time

DEFAULT_TOMBSTONE_RETENTION_SECONDS = 30 * 24 * 60 * 60


class TombstoneGC:
    def __init__(self, store, retention_seconds: int = DEFAULT_TOMBSTONE_RETENTION_SECONDS):
        if retention_seconds < 0:
            raise ValueError("retention_seconds must be non-negative")
        self._store = store
        self._retention_seconds = retention_seconds

    async def collect(self, *, now: int | None = None) -> list[str]:
        timestamp = int(time.time()) if now is None else now
        candidates = await self._store.tombstones_before(
            timestamp - self._retention_seconds
        )
        collected: list[str] = []
        for record in candidates:
            if await self._store.all_active_peers_acked(record.op_id):
                await self._store.delete_tombstone(record)
                collected.append(record.entity)
        return collected
