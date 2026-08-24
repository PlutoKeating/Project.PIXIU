"""ANN 语义检索通道 — INT8 量化向量的余弦近邻。

无外部向量库依赖：数据量小（端侧 < 1 万条），纯 Python 线性扫描。
embedder 同步调用放入 asyncio.to_thread，不阻塞事件循环。

向量格式与 engine/embed_writer 对齐：symmetric INT8 quantization，
struct.pack("Nb") 存储于 knowledge_vec.vec。
"""

from __future__ import annotations

import asyncio
import struct
from typing import Protocol, runtime_checkable

from backend.foundation.core.models import KnowledgeItem, KnowledgeStatus
from backend.foundation.core.repository import KnowledgeRepository


@runtime_checkable
class Embedder(Protocol):
    """文本向量化协议（与 engine.kylin.TextEmbedder 结构一致，避免跨模块 import）。"""

    def embed(self, text: str) -> list[float]: ...


def quantize_int8(vector: list[float]) -> list[int]:
    """Symmetric INT8 quantization into [-127, 127]（与 embed_writer 一致）。"""
    if not vector:
        return []
    max_abs = max(abs(x) for x in vector) or 1.0
    scale = 127.0 / max_abs
    return [max(-127, min(127, int(round(x * scale)))) for x in vector]


def _unpack_quantized(vec_bytes: bytes) -> list[int]:
    return list(struct.unpack(f"{len(vec_bytes)}b", vec_bytes))


def _cosine(a: list[int], b: list[int]) -> float:
    """量化向量的余弦相似度（0 向量返回 0）。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class ANNChannel:
    """INT8 向量近邻通道。"""

    def __init__(self, knw_repo: KnowledgeRepository, embedder: Embedder) -> None:
        self._knw_repo = knw_repo
        self._embedder = embedder
        # 解码缓存：knowledge_id -> (字节数, 解码后的量化向量)。
        # 避免每次查询对全量向量重复 struct.unpack；以 (id, 字节数) 判定是否复用。
        self._decoded: dict[str, tuple[int, list[int]]] = {}

    async def search(self, text: str, top_k: int = 20) -> list[tuple[KnowledgeItem, float]]:
        """返回 [(KnowledgeItem, similarity)]，按相似度降序。"""
        # 同步 embedding 与扫描放入线程池
        query_vec = await asyncio.to_thread(
            lambda: quantize_int8(self._embedder.embed(text))
        )
        vectors = await self._knw_repo.list_vectors()

        scored: list[tuple[str, float]] = []
        seen_ids: set[str] = set()
        for knowledge_id, _dim, vec_bytes in vectors:
            seen_ids.add(knowledge_id)
            cached = self._decoded.get(knowledge_id)
            if cached is None or cached[0] != len(vec_bytes):
                cached = (len(vec_bytes), _unpack_quantized(vec_bytes))
                self._decoded[knowledge_id] = cached
            sim = _cosine(query_vec, cached[1])
            scored.append((knowledge_id, sim))

        # 清理已删除/被遗忘条目的缓存，防止长期驻留
        if len(self._decoded) > len(seen_ids) * 2:
            self._decoded = {
                k: v for k, v in self._decoded.items() if k in seen_ids
            }

        scored.sort(key=lambda t: t[1], reverse=True)
        top = scored[:top_k]

        items: list[tuple[KnowledgeItem, float]] = []
        for knowledge_id, sim in top:
            if sim <= 0:
                continue
            item = await self._knw_repo.get(knowledge_id)
            if item is not None and item.status == KnowledgeStatus.ACTIVE:
                items.append((item, sim))
        return items
