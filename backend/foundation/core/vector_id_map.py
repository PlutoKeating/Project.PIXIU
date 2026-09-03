"""Mapping seam between canonical string IDs and vector-engine int64 IDs."""

from __future__ import annotations

from abc import ABC, abstractmethod


class VectorIdMap(ABC):
    @abstractmethod
    async def get_or_create(self, knowledge_id: str) -> int:
        """Return the stable int64 ID for a canonical knowledge ID."""
        ...

    @abstractmethod
    async def get(self, knowledge_id: str) -> int | None:
        """Return an existing int64 ID without creating one."""
        ...

    @abstractmethod
    async def resolve(self, vector_ids: list[int]) -> dict[int, str]:
        """Resolve known int64 IDs to canonical knowledge IDs."""
        ...

    @abstractmethod
    async def remove(self, knowledge_id: str) -> None:
        """Remove a mapping after its remote vector was deleted."""
        ...


__all__ = ["VectorIdMap"]
