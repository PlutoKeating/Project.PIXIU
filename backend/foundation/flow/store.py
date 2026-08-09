"""短/中期记忆的 SQLite 持久化。"""

from __future__ import annotations

import json
from typing import Protocol

import aiosqlite

from .models import ContextStatus, MemoryContext, MemoryTier


class FlowStore(Protocol):
    async def save(self, context: MemoryContext) -> str: ...
    async def get(self, context_id: str) -> MemoryContext | None: ...
    async def get_many(self, context_ids: list[str]) -> list[MemoryContext]: ...
    async def mark_promoted(self, context_id: str, knowledge_id: str, now: int) -> None: ...
    async def list_due(self, now: int) -> list[MemoryContext]: ...
    async def expire(self, context_id: str, now: int) -> None: ...


def _row_to_context(row: aiosqlite.Row) -> MemoryContext:
    return MemoryContext(
        id=row["id"],
        tier=row["tier"],
        payload=json.loads(row["payload"]),
        scope=row["scope"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        expires_at=row["expires_at"],
        knowledge_id=row["knowledge_id"],
    )


class SqliteFlowStore:
    """memory_contexts 表的异步访问层。"""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, context: MemoryContext) -> str:
        await self._db.execute(
            """INSERT INTO memory_contexts (
                   id, tier, payload, scope, status, created_at, updated_at,
                   expires_at, knowledge_id
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   tier=excluded.tier,
                   payload=excluded.payload,
                   scope=excluded.scope,
                   status=excluded.status,
                   updated_at=excluded.updated_at,
                   expires_at=excluded.expires_at,
                   knowledge_id=excluded.knowledge_id""",
            (
                context.id,
                context.tier.value,
                json.dumps(context.payload, ensure_ascii=False),
                context.scope,
                context.status.value,
                context.created_at,
                context.updated_at,
                context.expires_at,
                context.knowledge_id,
            ),
        )
        await self._db.commit()
        return context.id

    async def get(self, context_id: str) -> MemoryContext | None:
        cursor = await self._db.execute(
            "SELECT * FROM memory_contexts WHERE id = ?", (context_id,)
        )
        row = await cursor.fetchone()
        return _row_to_context(row) if row else None

    async def get_many(self, context_ids: list[str]) -> list[MemoryContext]:
        if not context_ids:
            return []
        placeholders = ",".join("?" * len(context_ids))
        cursor = await self._db.execute(
            f"SELECT * FROM memory_contexts WHERE id IN ({placeholders})",
            context_ids,
        )
        rows = await cursor.fetchall()
        by_id = {row["id"]: _row_to_context(row) for row in rows}
        return [by_id[context_id] for context_id in context_ids if context_id in by_id]

    async def mark_promoted(self, context_id: str, knowledge_id: str, now: int) -> None:
        await self._db.execute(
            """UPDATE memory_contexts
               SET status = ?, knowledge_id = ?, updated_at = ?, expires_at = NULL
               WHERE id = ? AND status = ?""",
            (
                ContextStatus.PROMOTED.value,
                knowledge_id,
                now,
                context_id,
                ContextStatus.ACTIVE.value,
            ),
        )
        await self._db.commit()

    async def list_due(self, now: int) -> list[MemoryContext]:
        cursor = await self._db.execute(
            """SELECT * FROM memory_contexts
               WHERE status = ? AND expires_at IS NOT NULL AND expires_at <= ?
               ORDER BY expires_at, id""",
            (ContextStatus.ACTIVE.value, now),
        )
        rows = await cursor.fetchall()
        return [_row_to_context(row) for row in rows]

    async def expire(self, context_id: str, now: int) -> None:
        """逻辑保留审计行，但清空已过期的上下文内容。"""
        await self._db.execute(
            """UPDATE memory_contexts
               SET status = ?, payload = '{}', updated_at = ?
               WHERE id = ? AND status = ?""",
            (
                ContextStatus.EXPIRED.value,
                now,
                context_id,
                ContextStatus.ACTIVE.value,
            ),
        )
        await self._db.commit()

    async def list_active(
        self,
        scope: str,
        tier: MemoryTier | None = None,
    ) -> list[MemoryContext]:
        if tier is None:
            cursor = await self._db.execute(
                """SELECT * FROM memory_contexts
                   WHERE scope = ? AND status = ? ORDER BY updated_at DESC""",
                (scope, ContextStatus.ACTIVE.value),
            )
        else:
            cursor = await self._db.execute(
                """SELECT * FROM memory_contexts
                   WHERE scope = ? AND tier = ? AND status = ?
                   ORDER BY updated_at DESC""",
                (scope, tier.value, ContextStatus.ACTIVE.value),
            )
        rows = await cursor.fetchall()
        return [_row_to_context(row) for row in rows]
