"""kylin/ —— KylinSDK embedding 适配（V0.1: Mock + stub）."""

from backend.engine.kylin.embedding import KylinTextEmbedding, MockEmbedding, get_embedder

__all__ = ["KylinTextEmbedding", "MockEmbedding", "get_embedder"]
