"""SQLite-backed collision-safe Vector Engine primary-key mapping."""

from __future__ import annotations

import hashlib

import aiosqlite

from backend.foundation.core.vector_id_map import VectorIdMap


class SqliteVectorIdMap(VectorIdMap):
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db
        self._ready = False

    async def _ensure_table(self) -> None:
        if self._ready:
            return
        await self._db.execute(
            """CREATE TABLE IF NOT EXISTS vector_id_map (
                knowledge_id TEXT PRIMARY KEY,
                vector_id    INTEGER NOT NULL UNIQUE
            )"""
        )
        await self._db.commit()
        self._ready = True

    @staticmethod
    def _candidate(knowledge_id: str, attempt: int) -> int:
        digest = hashlib.blake2b(
            f"{attempt}:{knowledge_id}".encode("utf-8"),
            digest_size=8,
            person=b"PIXIUVID",
        ).digest()
        return int.from_bytes(digest, "big") & ((1 << 63) - 1)

    async def get_or_create(self, knowledge_id: str) -> int:
        if not knowledge_id:
            raise ValueError("knowledge_id must not be empty")
        await self._ensure_table()
        existing = await self.get(knowledge_id)
        if existing is not None:
            return existing

        for attempt in range(1024):
            candidate = self._candidate(knowledge_id, attempt)
            await self._db.execute(
                "INSERT OR IGNORE INTO vector_id_map (knowledge_id, vector_id) "
                "VALUES (?, ?)",
                (knowledge_id, candidate),
            )
            await self._db.commit()
            existing = await self.get(knowledge_id)
            if existing is not None:
                return existing
        raise RuntimeError("unable to allocate a unique vector id")

    async def get(self, knowledge_id: str) -> int | None:
        await self._ensure_table()
        cursor = await self._db.execute(
            "SELECT vector_id FROM vector_id_map WHERE knowledge_id = ?",
            (knowledge_id,),
        )
        row = await cursor.fetchone()
        return int(row["vector_id"]) if row is not None else None

    async def resolve(self, vector_ids: list[int]) -> dict[int, str]:
        if not vector_ids:
            return {}
        await self._ensure_table()
        unique_ids = list(dict.fromkeys(vector_ids))
        placeholders = ",".join("?" for _ in unique_ids)
        cursor = await self._db.execute(
            f"SELECT vector_id, knowledge_id FROM vector_id_map "
            f"WHERE vector_id IN ({placeholders})",
            unique_ids,
        )
        rows = await cursor.fetchall()
        return {int(row["vector_id"]): row["knowledge_id"] for row in rows}

    async def remove(self, knowledge_id: str) -> None:
        await self._ensure_table()
        await self._db.execute(
            "DELETE FROM vector_id_map WHERE knowledge_id = ?", (knowledge_id,)
        )
        await self._db.commit()


__all__ = ["SqliteVectorIdMap"]
