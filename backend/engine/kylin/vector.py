"""麒麟向量数据库客户端（libkysdk-vector-engine-client）真实调用。

底层为 C++ SDK（Milvus 式 gRPC 客户端），经 pybind11 模块
``backend.engine.kylin._kylin_vector_client`` 暴露给 Python。
构建方式见 ``backend/engine/kylin/cpp/README.md``。
"""

from __future__ import annotations

from typing import Any

from backend.engine.kylin.errors import KylinSDKUnavailableError


def _load_native():
    """加载 pybind11 原生扩展；缺失时抛出带构建指引的异常。"""
    try:
        from backend.engine.kylin import _kylin_vector_client as native
    except ImportError as exc:
        raise KylinSDKUnavailableError(
            "麒麟向量数据库 SDK 原生扩展未加载：请确认已安装 "
            "libkysdk-vector-engine-client 及其依赖（gRPC/protobuf/"
            "nlohmann_json/SQLiteCpp/sqlcipher/KylinAiProto），并按 "
            "backend/engine/kylin/cpp/README.md 构建 _kylin_vector_client。"
        ) from exc
    return native


class VectorEngineClient:
    """麒麟向量数据库客户端（Milvus 式）。

    提供集合与向量生命周期操作。向量引擎服务未运行或 SDK 缺失时抛错，
    无任何降级。
    """

    def __init__(
        self,
        app_id: str = "pixiu",
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        native = _load_native()
        if (host is None) != (port is None):
            raise ValueError("host and port must be configured together")
        if host is None:
            self._impl = native.VectorEngineClient(app_id)
        else:
            self._impl = native.VectorEngineClient(app_id, host, port)

    def has_collection(self, name: str) -> bool:
        return bool(self._impl.has_collection(name))

    def create_collection(
        self, name: str, dim: int, auto_id: bool = True, dynamic: bool = True
    ) -> None:
        self._impl.create_collection(name, dim, auto_id, dynamic)

    def drop_collection(self, name: str) -> None:
        self._impl.drop_collection(name)

    def load_collection(self, name: str) -> None:
        """将集合装载到查询节点。"""
        self._impl.load_collection(name)

    def insert(
        self, name: str, vectors: list[list[float]], ids: list[int] | None = None
    ) -> int:
        """插入向量，返回写入行数。id 自增时可不传 ids。"""
        return int(self._impl.insert(name, vectors, ids or []))

    def upsert(
        self, name: str, vectors: list[list[float]], ids: list[int]
    ) -> int:
        """按显式整数主键插入或替换向量，返回受影响行数。"""
        if len(vectors) != len(ids):
            raise ValueError("vector and id counts must match")
        if not ids:
            return 0
        return int(self._impl.upsert(name, vectors, ids))

    def delete(self, name: str, ids: list[int]) -> int:
        """按整数主键删除向量，不向调用方暴露 SDK 过滤表达式。"""
        if not ids:
            return 0
        return int(self._impl.delete(name, ids))

    def search(
        self, name: str, query: list[float], top_k: int = 10
    ) -> list[dict[str, Any]]:
        """按 query 向量检索，返回 [{id, score}, ...]。"""
        return [dict(item) for item in self._impl.search(name, query, top_k)]


__all__ = ["KylinSDKUnavailableError", "VectorEngineClient"]
