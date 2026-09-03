"""Durable idempotency receipts for OS Agent memory ingestion."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import aiosqlite


class IdempotencyError(RuntimeError):
    """Base class for a rejected idempotent operation."""


class IdempotencyConflict(IdempotencyError):
    """The key already belongs to a different request payload."""


class IdempotencyInProgress(IdempotencyError):
    """The matching request has not reached a terminal state."""


class IdempotencyFailed(IdempotencyError):
    """The original request failed after claiming the key."""


class ClaimStatus(str, Enum):
    NEW = "NEW"
    REPLAY = "REPLAY"


@dataclass(frozen=True)
class ClaimResult:
    status: ClaimStatus
    response: dict[str, Any] | None = None


class AgentIngestReceiptStore:
    """Persist request ownership and completed responses across restarts.

    FAILED and IN_PROGRESS claims are deliberately fail-closed. Retrying them
    automatically could duplicate effects when the original request stopped
    after writing evidence or an external vector.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def claim(self, key: str, request_hash: str) -> ClaimResult:
        now = int(time.time())
        cursor = await self._db.execute(
            """INSERT OR IGNORE INTO agent_ingest_receipts
               (idempotency_key, request_hash, state, response, created_at, updated_at)
               VALUES (?, ?, 'IN_PROGRESS', '{}', ?, ?)""",
            (key, request_hash, now, now),
        )
        await self._db.commit()
        if cursor.rowcount == 1:
            return ClaimResult(ClaimStatus.NEW)

        cursor = await self._db.execute(
            """SELECT request_hash, state, response
               FROM agent_ingest_receipts WHERE idempotency_key = ?""",
            (key,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("idempotency receipt disappeared after claim")
        if row["request_hash"] != request_hash:
            raise IdempotencyConflict(key)
        if row["state"] == "COMPLETED":
            return ClaimResult(ClaimStatus.REPLAY, json.loads(row["response"]))
        if row["state"] == "FAILED":
            raise IdempotencyFailed(key)
        raise IdempotencyInProgress(key)

    async def complete(
        self, key: str, request_hash: str, response: dict[str, Any]
    ) -> None:
        cursor = await self._db.execute(
            """UPDATE agent_ingest_receipts
               SET state = 'COMPLETED', response = ?, updated_at = ?
               WHERE idempotency_key = ? AND request_hash = ?
                 AND state = 'IN_PROGRESS'""",
            (
                json.dumps(response, ensure_ascii=False, sort_keys=True),
                int(time.time()),
                key,
                request_hash,
            ),
        )
        await self._db.commit()
        if cursor.rowcount != 1:
            raise RuntimeError("idempotency claim was not active at completion")

    async def fail(self, key: str, request_hash: str) -> None:
        await self._db.execute(
            """UPDATE agent_ingest_receipts
               SET state = 'FAILED', updated_at = ?
               WHERE idempotency_key = ? AND request_hash = ?
                 AND state = 'IN_PROGRESS'""",
            (int(time.time()), key, request_hash),
        )
        await self._db.commit()
