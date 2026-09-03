"""Backend-neutral vector storage seam shared by memory engine and retrieval."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VectorMatch:
    """A vector result mapped back to the canonical knowledge identifier."""

    knowledge_id: str
    score: float


class VectorStore(ABC):
    """Small interface hiding persistence, indexing, mapping, and quantization."""

    @property
    @abstractmethod
    def runtime(self) -> str:
        """Return the active implementation name for capability evidence."""
        ...

    @abstractmethod
    async def upsert(self, knowledge_id: str, vector: list[float]) -> None:
        """Insert or replace one knowledge vector."""
        ...

    @abstractmethod
    async def search(self, vector: list[float], limit: int) -> list[VectorMatch]:
        """Return nearest canonical knowledge identifiers in score order."""
        ...

    @abstractmethod
    async def delete(self, knowledge_id: str) -> None:
        """Remove one knowledge vector; missing identifiers are a no-op."""
        ...


__all__ = ["VectorMatch", "VectorStore"]
