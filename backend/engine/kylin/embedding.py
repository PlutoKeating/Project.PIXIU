"""麒麟 coreai/embedding 文本向量化真实调用（无 mock 降级）。

底层为 C 接口 SDK（libkysdk-coreai-embedding），经 pybind11 模块
``backend.engine.kylin._kylin_text_embedding`` 暴露给 Python。
构建方式见 ``backend/engine/kylin/cpp/README.md``。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.engine.kylin.errors import KylinSDKUnavailableError


@runtime_checkable
class TextEmbedder(Protocol):
    """文本向量化器协议（embed -> list[float]）。"""

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
    init_model / text_embedding，无任何 mock 降级；SDK 缺失时直接抛错。
    """

    def __init__(self, model_name: str | None = None) -> None:
        native = _load_native()
        self._impl = native.KylinTextEmbedding(model_name or "")

    def embed(self, text: str) -> list[float]:
        return list(self._impl.embed(text))

    @property
    def dim(self) -> int:
        return int(self._impl.dim())

    @property
    def model_name(self) -> str:
        return str(self._impl.model_name())


def get_embedder() -> KylinTextEmbedding:
    """构建生产环境 embedder（麒麟 SDK，无 mock）。"""
    return KylinTextEmbedding()


__all__ = ["KylinSDKUnavailableError", "KylinTextEmbedding", "TextEmbedder", "get_embedder"]
