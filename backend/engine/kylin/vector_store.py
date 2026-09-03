"""VectorStore adapter backed by the required Kylin Vector Engine SDK."""

from __future__ import annotations

import asyncio
import math
from typing import Any

from backend.foundation.core.vector_id_map import VectorIdMap
from backend.foundation.core.vector_store import VectorMatch, VectorStore


class KylinVectorStore(VectorStore):
    """Hide collection lifecycle and int64 mapping behind the shared seam."""

    def __init__(
        self,
        client: Any,
        id_map: VectorIdMap,
        *,
        collection: str = "pixiu_memory",
    ) -> None:
        if not collection:
            raise ValueError("collection must not be empty")
        self._client = client
        self._id_map = id_map
        self._collection = collection
        self._dimension: int | None = None
        self._ready_lock = asyncio.Lock()
        self._closed = False

    @property
    def runtime(self) -> str:
        return "kylin"

    @staticmethod
    def _validate_vector(vector: list[float]) -> None:
        if not vector:
            raise ValueError("vector must not be empty")
        if not all(math.isfinite(value) for value in vector):
            raise ValueError("vector values must be finite")

    async def _ensure_collection(self, dimension: int) -> None:
        if self._closed:
            raise RuntimeError("Vector Engine store is closed")
        async with self._ready_lock:
            if self._dimension is not None:
                if self._dimension != dimension:
                    raise ValueError(
                        f"vector dimension mismatch: expected {self._dimension}, "
                        f"got {dimension}"
                    )
                return
            exists = await asyncio.to_thread(
                self._client.has_collection, self._collection
            )
            if not exists:
                await asyncio.to_thread(
                    self._client.create_collection,
                    self._collection,
                    dimension,
                    False,
                    True,
                )
            await asyncio.to_thread(self._client.load_collection, self._collection)
            self._dimension = dimension

    async def upsert(self, knowledge_id: str, vector: list[float]) -> None:
        self._validate_vector(vector)
        vector_id = await self._id_map.get_or_create(knowledge_id)
        await self._ensure_collection(len(vector))
        count = await asyncio.to_thread(
            self._client.upsert,
            self._collection,
            [vector],
            [vector_id],
        )
        if count != 1:
            raise RuntimeError(f"Vector Engine upsert affected {count} rows, expected 1")

    async def search(self, vector: list[float], limit: int) -> list[VectorMatch]:
        if limit <= 0:
            return []
        self._validate_vector(vector)
        await self._ensure_collection(len(vector))
        rows = await asyncio.to_thread(
            self._client.search, self._collection, vector, limit
        )
        vector_ids = [int(row["id"]) for row in rows]
        resolved = await self._id_map.resolve(vector_ids)
        return [
            VectorMatch(resolved[vector_id], float(row["score"]))
            for row, vector_id in zip(rows, vector_ids)
            if vector_id in resolved
        ]

    async def delete(self, knowledge_id: str) -> None:
        vector_id = await self._id_map.get(knowledge_id)
        if vector_id is None:
            return
        count = await asyncio.to_thread(
            self._client.delete, self._collection, [vector_id]
        )
        if count not in (0, 1):
            raise RuntimeError(
                f"Vector Engine delete affected {count} rows, expected at most 1"
            )
        await self._id_map.remove(knowledge_id)

    async def close(self) -> None:
        """Release the SDK connection owned by this store exactly once."""
        async with self._ready_lock:
            if self._closed:
                return
            await asyncio.to_thread(self._client.disconnect)
            self._closed = True


__all__ = ["KylinVectorStore"]
