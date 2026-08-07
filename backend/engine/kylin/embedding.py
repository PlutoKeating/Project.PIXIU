"""Kylin embedding shim — real C bindings deferred; V0.1 uses MockEmbedding."""

from __future__ import annotations

from backend.engine.kylin.mock_embedding import KylinTextEmbedding, MockEmbedding, get_embedder

__all__ = ["KylinTextEmbedding", "MockEmbedding", "get_embedder"]
