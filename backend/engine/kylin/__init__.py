"""kylin/ —— 麒麟 SDK 适配与 Debian 可移植降级。

- 文本向量化：libkysdk-coreai-embedding（C API，pybind11 绑定）
- 向量数据库：libkysdk-vector-engine-client（C++ API，pybind11 绑定）

默认优先真实 SDK，缺失时使用可移植向量器；严格麒麟模式会抛出
``KylinSDKUnavailableError`` 并附构建指引。
"""

from __future__ import annotations

from backend.engine.kylin.embedding import (
    KylinSDKUnavailableError,
    KylinTextEmbedding,
    PortableTextEmbedding,
    TextEmbedder,
    get_embedder,
)
from backend.engine.kylin.ocr import KylinOcr, StructuredTextOcr, get_ocr
from backend.engine.kylin.vector import VectorEngineClient

__all__ = [
    "KylinOcr",
    "KylinSDKUnavailableError",
    "KylinTextEmbedding",
    "PortableTextEmbedding",
    "StructuredTextOcr",
    "TextEmbedder",
    "VectorEngineClient",
    "get_embedder",
    "get_ocr",
]
