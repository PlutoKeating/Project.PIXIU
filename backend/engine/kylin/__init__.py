"""kylin/ —— 麒麟 SDK 适配（真实调用，无 mock 降级）。

- 文本向量化：libkysdk-coreai-embedding（C API，pybind11 绑定）
- 向量数据库：libkysdk-vector-engine-client（C++ API，pybind11 绑定）

SDK 不可用时抛出 ``KylinSDKUnavailableError``，附构建指引。
"""

from __future__ import annotations

from backend.engine.kylin.embedding import (
    KylinSDKUnavailableError,
    KylinTextEmbedding,
    TextEmbedder,
    get_embedder,
)
from backend.engine.kylin.vector import VectorEngineClient

__all__ = [
    "KylinSDKUnavailableError",
    "KylinTextEmbedding",
    "TextEmbedder",
    "VectorEngineClient",
    "get_embedder",
]
