"""同步轮次调度与有界指数退避。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


class BackoffPolicy:
    def __init__(self, base_seconds: float = 1.0, max_seconds: float = 60.0) -> None:
        if base_seconds <= 0 or max_seconds < base_seconds:
            raise ValueError("invalid backoff bounds")
        self.base_seconds = base_seconds
        self.max_seconds = max_seconds

    def delay(self, failures: int) -> float:
        return min(self.max_seconds, self.base_seconds * (2 ** max(0, failures)))


class SyncScheduler:
    def __init__(
        self,
        round_callback: Callable[[], Awaitable[None]],
        *,
        interval_seconds: float = 30.0,
        backoff: BackoffPolicy | None = None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self._round_callback = round_callback
        self._interval = interval_seconds
        self._backoff = backoff or BackoffPolicy()
        self._failures = 0
        self._stop = asyncio.Event()

    async def run_once(self) -> float:
        try:
            await self._round_callback()
        except Exception:
            delay = self._backoff.delay(self._failures)
            self._failures += 1
            return delay
        self._failures = 0
        return self._interval

    async def run(self) -> None:
        self._stop.clear()
        while not self._stop.is_set():
            delay = await self.run_once()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                continue

    def stop(self) -> None:
        self._stop.set()
