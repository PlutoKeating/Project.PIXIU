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


class IdempotencyNotFound(IdempotencyError):
    """No receipt exists for the requested recovery target."""


class IdempotencyCompleted(IdempotencyError):
    """A completed receipt cannot be authorized for replay."""


class ClaimStatus(str, Enum):
    NEW = "NEW"
    REPLAY = "REPLAY"


@dataclass(frozen=True)
class ClaimResult:
    status: ClaimStatus
    response: dict[str, Any] | None = None


@dataclass(frozen=True)
class RetryAuthorization:
    recovery_count: int
    authorized_at: int
    authorized: bool = True


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
            """SELECT request_hash, state, response, retry_authorized
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
            if row["retry_authorized"]:
                cursor = await self._db.execute(
                    """UPDATE agent_ingest_receipts
                       SET state = 'IN_PROGRESS', retry_authorized = 0,
                           updated_at = ?
                       WHERE idempotency_key = ? AND request_hash = ?
                         AND state = 'FAILED' AND retry_authorized = 1""",
                    (now, key, request_hash),
                )
                await self._db.commit()
                if cursor.rowcount == 1:
                    return ClaimResult(ClaimStatus.NEW)
                raise IdempotencyInProgress(key)
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

    async def authorize_retry(
        self,
        key: str,
        request_hash: str,
        reason: str,
    ) -> RetryAuthorization:
        """Authorize one retry of an exact FAILED request and retain audit data."""
        cursor = await self._db.execute(
            """SELECT request_hash, state, retry_authorized, recovery_count,
                      recovered_at
               FROM agent_ingest_receipts WHERE idempotency_key = ?""",
            (key,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise IdempotencyNotFound(key)
        if row["request_hash"] != request_hash:
            raise IdempotencyConflict(key)
        if row["state"] == "COMPLETED":
            raise IdempotencyCompleted(key)
        if row["state"] == "IN_PROGRESS":
            raise IdempotencyInProgress(key)
        if row["retry_authorized"]:
            return RetryAuthorization(
                recovery_count=row["recovery_count"],
                authorized_at=row["recovered_at"],
            )

        now = int(time.time())
        cursor = await self._db.execute(
            """UPDATE agent_ingest_receipts
               SET retry_authorized = 1,
                   recovery_count = recovery_count + 1,
                   recovery_reason = ?, recovered_at = ?, updated_at = ?
               WHERE idempotency_key = ? AND request_hash = ?
                 AND state = 'FAILED' AND retry_authorized = 0""",
            (reason, now, now, key, request_hash),
        )
        await self._db.commit()
        if cursor.rowcount != 1:
            cursor = await self._db.execute(
                """SELECT recovery_count, recovered_at
                   FROM agent_ingest_receipts WHERE idempotency_key = ?""",
                (key,),
            )
            current = await cursor.fetchone()
            if current is None:
                raise IdempotencyNotFound(key)
            return RetryAuthorization(
                recovery_count=current["recovery_count"],
                authorized_at=current["recovered_at"],
            )
        return RetryAuthorization(
            recovery_count=row["recovery_count"] + 1,
            authorized_at=now,
        )
