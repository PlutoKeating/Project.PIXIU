"""EmbedWriter — Mock embedding → INT8 quantize → attach embedding_ref."""

from __future__ import annotations

from typing import Any

from engine.kylin.mock_embedding import TextEmbedder
from engine.mocks.models import KnowledgeItem


def quantize_int8(vector: list[float]) -> list[int]:
    """Symmetric INT8 quantization into [-127, 127]."""
    if not vector:
        return []
    max_abs = max(abs(x) for x in vector) or 1.0
    scale = 127.0 / max_abs
    return [max(-127, min(127, int(round(x * scale)))) for x in vector]


class EmbedWriter:
    """V0.1: produce embedding + INT8 blob and store on the KnowledgeItem (mock)."""

    def __init__(self, embedder: TextEmbedder) -> None:
        self._embedder = embedder
        # In-memory mock vector store: embedding_ref -> int8 list
        self.vectors: dict[str, list[int]] = {}

    def write(self, item: KnowledgeItem) -> KnowledgeItem:
        text = self._to_text(item)
        vec = self._embedder.embed(text)
        q = quantize_int8(vec)
        ref = f"vec_{item.id}"
        self.vectors[ref] = q
        item.embedding_ref = ref
        return item

    @staticmethod
    def _to_text(item: KnowledgeItem) -> str:
        parts: list[Any] = [item.title, item.kind, item.body]
        return " ".join(str(p) for p in parts)
