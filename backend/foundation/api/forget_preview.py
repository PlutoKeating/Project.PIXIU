"""Bounded, process-local, single-use human review receipts.

Restart or a different worker invalidates previews rather than permitting an
unreviewed operation. Receipts are consumed before any asynchronous side effect.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Preview:
    command: str
    scope: str | None
    targets: dict[str, int]
    deadline: float


class ForgetPreviews:
    def __init__(self, *, ttl: int = 120, capacity: int = 256, clock=time.monotonic):
        self.ttl = ttl
        self.capacity = capacity
        self.clock = clock
        self._pending: dict[str, Preview] = {}

    def issue(self, command: str, scope: str | None, targets: dict[str, int]) -> str:
        now = self.clock()
        self._pending = {key: value for key, value in self._pending.items() if value.deadline > now}
        if len(self._pending) >= self.capacity:
            raise ValueError("preview capacity exceeded")
        token = secrets.token_urlsafe(32)
        self._pending[token] = Preview(command, scope, dict(targets), now + self.ttl)
        return token

    def consume(self, token: str | None, command: str, scope: str | None) -> dict[str, int]:
        preview = self._pending.pop(token, None)
        if preview is None or preview.deadline <= self.clock() or preview.command != command or preview.scope != scope:
            raise ValueError("preview missing, expired, used or mismatched")
        return dict(preview.targets)


forget_previews = ForgetPreviews()
