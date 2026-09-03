"""文本向量化适配：麒麟 SDK 优先，Debian 软件实现降级。

底层为 C 接口 SDK（libkysdk-coreai-embedding），经 pybind11 模块
``backend.engine.kylin._kylin_text_embedding`` 暴露给 Python。
构建方式见 ``backend/engine/kylin/cpp/README.md``。
"""

from __future__ import annotations

import hashlib
import logging
import math
import unicodedata
from typing import Protocol, runtime_checkable

from backend.engine.kylin.errors import KylinSDKUnavailableError

logger = logging.getLogger(__name__)


@runtime_checkable
class TextEmbedder(Protocol):
    """文本向量化器协议（embed -> list[float]）。"""

    @property
    def runtime(self) -> str: ...

    def embed(self, text: str) -> list[float]: ...


def _load_native():
    """加载 pybind11 原生扩展；缺失时抛出带构建指引的异常。"""
    try:
        from backend.engine.kylin import _kylin_text_embedding as native
    except ImportError as exc:
        raise KylinSDKUnavailableError(
            "麒麟 coreai/embedding 原生扩展未加载：请确认已在麒麟系统安装 "
            "libkylin-coreai-embedding（含 AI 运行时服务），并按 "
            "backend/engine/kylin/cpp/README.md 构建 _kylin_text_embedding。"
        ) from exc
    return native


class KylinTextEmbedding:
    """麒麟文本向量化客户端（同步接口）。

    封装 text_embedding_create_session / init_session / get_model_list /
    init_model / text_embedding；严格 ``kylin`` 模式下 SDK 缺失时抛错。
    """

    def __init__(self, model_name: str | None = None) -> None:
        native = _load_native()
        try:
            self._impl = native.KylinTextEmbedding(model_name or "")
        except Exception as exc:
            raise KylinSDKUnavailableError(
                "麒麟 coreai/embedding 运行时不可用：请检查 AI 服务与模型配置。"
            ) from exc

    def embed(self, text: str) -> list[float]:
        vector = list(self._impl.embed(text))
        if len(vector) != self.dim:
            raise RuntimeError(
                f"Kylin embedding dimension mismatch: expected {self.dim}, "
                f"got {len(vector)}"
            )
        return vector

    @property
    def runtime(self) -> str:
        return "kylin"

    @property
    def dim(self) -> int:
        return int(self._impl.dim())

    @property
    def model_name(self) -> str:
        return str(self._impl.model_name())


class PortableTextEmbedding:
    """无外部模型依赖的确定性特征哈希向量器。

    这是 Debian 兼容模式的实际软件实现，不模拟麒麟 SDK。它保证写入与检索
    链路可用，但语义质量低于麒麟 coreai 模型，不能替代麒麟环境的性能验收。
    """

    def __init__(self, dim: int = 256) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim
        self.model_name = "portable-feature-hash-v1"

    def embed(self, text: str) -> list[float]:
        normalized = unicodedata.normalize("NFKC", text).strip().casefold()
        vector = [0.0] * self.dim
        if not normalized:
            return vector

        features = list(normalized)
        features.extend(
            normalized[index : index + 2]
            for index in range(max(0, len(normalized) - 1))
        )
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    @property
    def runtime(self) -> str:
        return "portable"


def get_embedder(backend: str = "auto") -> TextEmbedder:
    """按能力选择 embedder。

    ``auto`` 优先使用麒麟 SDK，缺失时降级为可移植实现；``kylin`` 用于麒麟
    验收并保持严格失败；``portable`` 强制使用 Debian 通用软件实现。
    """
    if backend == "portable":
        return PortableTextEmbedding()
    if backend == "kylin":
        return KylinTextEmbedding()
    if backend != "auto":
        raise ValueError("embedding backend must be auto, kylin, or portable")
    try:
        return KylinTextEmbedding()
    except KylinSDKUnavailableError:
        logger.warning(
            "Kylin embedding unavailable; using portable feature-hash fallback"
        )
        return PortableTextEmbedding()


__all__ = [
    "KylinSDKUnavailableError",
    "KylinTextEmbedding",
    "PortableTextEmbedding",
    "TextEmbedder",
    "get_embedder",
]
