"""Portable SQLite implementation of the vector storage seam."""

from __future__ import annotations

import math
import struct

import aiosqlite

from backend.foundation.core.vector_store import VectorMatch, VectorStore


def _quantize(vector: list[float]) -> list[int]:
    if not vector:
        raise ValueError("vector must not be empty")
    if not all(math.isfinite(value) for value in vector):
        raise ValueError("vector values must be finite")
    max_abs = max(abs(value) for value in vector) or 1.0
    scale = 127.0 / max_abs
    return [max(-127, min(127, int(round(value * scale)))) for value in vector]


def _cosine(left: list[int], right: list[int]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class SqliteVectorStore(VectorStore):
    """INT8 vector store used by the explicit portable compatibility path."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db
        self._ready = False

    @property
    def runtime(self) -> str:
        return "portable"

    async def _ensure_table(self) -> None:
        if self._ready:
            return
        await self._db.execute(
            """CREATE TABLE IF NOT EXISTS knowledge_vec (
                knowledge_id TEXT PRIMARY KEY,
                dim          INTEGER NOT NULL,
                vec          BLOB NOT NULL,
                FOREIGN KEY (knowledge_id)
                    REFERENCES knowledge_items(id) ON DELETE CASCADE
            )"""
        )
        await self._db.commit()
        self._ready = True

    async def upsert(self, knowledge_id: str, vector: list[float]) -> None:
        quantized = _quantize(vector)
        packed = struct.pack(f"{len(quantized)}b", *quantized)
        await self._ensure_table()
        await self._db.execute(
            """INSERT INTO knowledge_vec (knowledge_id, dim, vec)
               VALUES (?, ?, ?)
               ON CONFLICT(knowledge_id) DO UPDATE SET
                   dim = excluded.dim,
                   vec = excluded.vec""",
            (knowledge_id, len(quantized), packed),
        )
        await self._db.commit()

    async def search(self, vector: list[float], limit: int) -> list[VectorMatch]:
        if limit <= 0:
            return []
        query = _quantize(vector)
        await self._ensure_table()
        cursor = await self._db.execute(
            "SELECT knowledge_id, dim, vec FROM knowledge_vec"
        )
        rows = await cursor.fetchall()
        matches = [
            VectorMatch(
                knowledge_id=row["knowledge_id"],
                score=_cosine(query, list(struct.unpack(f"{row['dim']}b", row["vec"]))),
            )
            for row in rows
            if row["dim"] == len(query) and len(row["vec"]) == row["dim"]
        ]
        matches.sort(key=lambda match: match.score, reverse=True)
        return matches[:limit]

    async def delete(self, knowledge_id: str) -> None:
        await self._ensure_table()
        await self._db.execute(
            "DELETE FROM knowledge_vec WHERE knowledge_id = ?", (knowledge_id,)
        )
        await self._db.commit()


__all__ = ["SqliteVectorStore"]
