"""短/中期记忆 TTL 策略与过期清理。"""

from __future__ import annotations

import time

from .models import MemoryTier
from .store import FlowStore

DEFAULT_SHORT_TERM_TTL_SECONDS = 30 * 60
DEFAULT_MID_TERM_TTL_SECONDS = 7 * 24 * 60 * 60


def ttl_for(tier: MemoryTier) -> int:
    if tier == MemoryTier.SHORT_TERM:
        return DEFAULT_SHORT_TERM_TTL_SECONDS
    return DEFAULT_MID_TERM_TTL_SECONDS


class TTLManager:
    def __init__(self, store: FlowStore) -> None:
        self._store = store

    async def sweep(self, *, now: int | None = None) -> list[str]:
        timestamp = int(time.time()) if now is None else now
        due = await self._store.list_due(timestamp)
        for context in due:
            await self._store.expire(context.id, timestamp)
        return [context.id for context in due]
