"""EmbedWriter — embedding → INT8 quantize → 向量序列化。"""

from __future__ import annotations

import struct
from typing import Any, Optional

from backend.engine.kylin.embedding import TextEmbedder
from backend.foundation.core.models import KnowledgeItem


def quantize_int8(vector: list[float]) -> list[int]:
    """Symmetric INT8 quantization into [-127, 127]."""
    if not vector:
        return []
    max_abs = max(abs(x) for x in vector) or 1.0
    scale = 127.0 / max_abs
    return [max(-127, min(127, int(round(x * scale)))) for x in vector]


class EmbedWriter:
    """生成 embedding + INT8 量化，并向调用方提供可持久化的 bytes。"""

    def __init__(self, embedder: TextEmbedder) -> None:
        self._embedder = embedder
        # 内存向量缓冲（按知识 id 索引）：embedding_ref 写入 KnowledgeItem，
        # bytes 由 KnowledgeService 调用 knw_repo.save_vector 持久化。
        self._vectors: dict[str, list[int]] = {}
        self._raw_vectors: dict[str, list[float]] = {}
        self._dims: dict[str, int] = {}

    def write(self, item: KnowledgeItem) -> KnowledgeItem:
        text = self._to_text(item)
        vec = self._embedder.embed(text)
        q = quantize_int8(vec)
        ref = f"vec_{item.id}"
        item.embedding_ref = ref
        self._vectors[item.id] = q
        self._raw_vectors[item.id] = list(vec)
        self._dims[item.id] = len(q)
        return item

    def dim(self, item: KnowledgeItem) -> int:
        """返回已写入向量的维度（未生成时为 0）。"""
        return self._dims.get(item.id, 0)

    def vector_bytes(self, item: KnowledgeItem) -> Optional[bytes]:
        """返回 INT8 量化向量的紧凑 bytes（signed int8 pack），未生成时返回 None。"""
        q = self._vectors.get(item.id)
        if not q:
            return None
        return struct.pack(f"{len(q)}b", *q)

    def vector(self, item: KnowledgeItem) -> Optional[list[float]]:
        """返回未量化 embedding，供 VectorStore 适配器选择原生存储格式。"""
        vector = self._raw_vectors.get(item.id)
        return list(vector) if vector else None

    @staticmethod
    def _to_text(item: KnowledgeItem) -> str:
        parts: list[Any] = [item.title, item.kind, item.body]
        return " ".join(str(p) for p in parts)
