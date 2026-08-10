"""PIXIU Foundation — D-Bus 服务 (com.kylin.pixiu.Memory)

桌面 D-Bus 接口，镜像核心 HTTP 能力：Write / Query / Forget / SyncStatus。
业务逻辑复用 api/di.py 注入的引擎 Service 与检索 Service，不复制实现。

分层：
- PixiuMemoryHandler：业务方法（复用 Service，可脱离总线独立测试）
- PixiuDBusInterface：dbus-next ServiceInterface 子类（方法注册 + 参数映射）
- PixiuDBusService：生命周期（总线连接、bus name 申请与冲突处理）

无麒麟 SDK 时 Query 经 RetrievalService → get_embedder() 明确抛
KylinSDKUnavailableError，不会静默使用生产 mock。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from dbus_next import RequestNameReply
from dbus_next.aio import MessageBus

from ..core.logger import get_logger

log = get_logger(__name__)

BUS_NAME = "com.kylin.pixiu.Memory"
OBJECT_PATH = "/com/kylin/pixiu/Memory"


class PixiuError(Exception):
    """D-Bus 服务层错误（携带错误码，随 reply 返回）。"""

    def __init__(self, error: str, message: str) -> None:
        super().__init__(message)
        self.error = error
        self.message = message


class PixiuMemoryHandler:
    """D-Bus 业务方法：复用引擎/检索 Service，返回可 JSON 序列化的 dict。"""

    def __init__(
        self,
        *,
        ingestion=None,
        knowledge=None,
        preference=None,
        conflict=None,
        security=None,
        retrieval=None,
        sync_status=None,
    ) -> None:
        self._ingestion = ingestion
        self._knowledge = knowledge
        self._preference = preference
        self._conflict = conflict
        self._security = security
        self._retrieval = retrieval
        self._sync_status_fn = sync_status

    async def write(self, source_type: str, raw: dict, scope: str) -> dict:
        """镜像 POST /memory/write：落 evidence + 结构化 + 偏好 + 冲突仲裁。"""
        if self._ingestion is None or self._knowledge is None:
            raise PixiuError("INTERNAL_ERROR", "memory services not available")
        evidence = await self._ingestion.ingest(source_type, raw, scope)
        item = await self._knowledge.structure(evidence)
        pref_count = 0
        if self._preference is not None:
            prefs = await self._preference.extract(evidence)
            pref_count = len(prefs)
        conflict_detected = False
        if self._conflict is not None:
            conflict_detected = (await self._conflict.arbitrate(item)) is not None
        return {
            "evidence_id": evidence.id,
            "status": "accepted",
            "quality_score": evidence.quality_score,
            "sensitivity": evidence.sensitivity,
            "preference_count": pref_count,
            "conflict_detected": conflict_detected,
        }

    async def query(self, text: str, context_hint: dict | None = None) -> dict:
        """镜像 POST /memory/query：混合检索 → MemoryAtom。"""
        if self._retrieval is None:
            raise PixiuError("INTERNAL_ERROR", "retrieval service not available")
        atom = await self._retrieval.query(text, context_hint or {})
        return atom.model_dump(mode="json")

    async def forget(self, command: str, confirm: bool = False) -> dict:
        """镜像 POST /forget：自然语言遗忘（确认/执行两阶段）。"""
        if self._security is None:
            raise PixiuError("INTERNAL_ERROR", "security service not available")
        result = await self._security.forget(command, confirm=confirm)
        if result.status == "pending":
            return {
                "targets": result.targets,
                "cascade": result.cascade,
                "irreversible": result.irreversible,
            }
        return {
            "status": "forgotten",
            "forgotten_ids": result.forgotten_ids,
        }

    async def sync_status(self) -> dict:
        """镜像 GET /sync/status：同步状态。"""
        if self._sync_status_fn is None:
            raise PixiuError("INTERNAL_ERROR", "sync service not available")
        status = await self._sync_status_fn()
        if hasattr(status, "model_dump"):
            return status.model_dump(mode="json")
        return dict(status)


def _to_json_payload(value: Any) -> str:
    """dbus-next 的 's' 类型传 JSON 字符串（结构化参数走 HTTP 更合适）。"""
    return json.dumps(value, ensure_ascii=False)


class PixiuDBusInterface:
    """dbus-next 总线接口：方法注册与参数/返回映射。

    基于 dbus-next ServiceInterface 子类：@method() 装饰 + 字符串类型注解
    （'s'=string, 'b'=bool），结构化参数经 JSON 字符串传输。
    """

    def __init__(self, handler: PixiuMemoryHandler) -> None:
        from dbus_next.service import ServiceInterface, method

        class _MemoryInterface(ServiceInterface):
            @method()
            async def Write(self, source_type: "s", raw_json: "s", scope: "s") -> "s":  # type: ignore[no-untyped-def]
                try:
                    raw = json.loads(raw_json)
                except json.JSONDecodeError as exc:
                    raise PixiuError("INVALID_REQUEST", f"raw must be valid JSON: {exc}") from exc
                return _to_json_payload(await handler.write(source_type, raw, scope))

            @method()
            async def Query(self, text: "s", context_json: "s") -> "s":  # type: ignore[no-untyped-def]
                try:
                    hint = json.loads(context_json) if context_json else {}
                except json.JSONDecodeError as exc:
                    raise PixiuError("INVALID_REQUEST", f"context_hint must be valid JSON: {exc}") from exc
                return _to_json_payload(await handler.query(text, hint))

            @method()
            async def Forget(self, command: "s", confirm: "b") -> "s":  # type: ignore[no-untyped-def]
                return _to_json_payload(await handler.forget(command, confirm))

            @method()
            async def SyncStatus(self) -> "s":  # type: ignore[no-untyped-def]
                return _to_json_payload(await handler.sync_status())

        self._interface_class = _MemoryInterface

    def create(self) -> Any:
        """实例化 dbus-next ServiceInterface 子类（接口名 = com.kylin.pixiu.Memory）。"""
        return self._interface_class(BUS_NAME)


class PixiuDBusService:
    """D-Bus 服务生命周期：连接、注册、bus name 冲突处理。"""

    def __init__(self, handler: PixiuMemoryHandler) -> None:
        self._handler = handler
        self._bus = None
        self._interface = None

    async def start(self, bus=None) -> str:
        """连接并注册到会话总线；返回申请到的 bus name。

        bus name 已被占用（非 PRIMARY_OWNER）时抛 PixiuError，不静默接管。
        """
        self._bus = bus if bus is not None else await MessageBus().connect()

        self._interface = PixiuDBusInterface(self._handler).create()
        self._bus.export(OBJECT_PATH, self._interface)

        request = await self._bus.request_name(BUS_NAME)
        if request != RequestNameReply.PRIMARY_OWNER:
            raise PixiuError(
                "BUS_NAME_CONFLICT",
                f"bus name {BUS_NAME} is already owned by another process",
            )
        log.info("D-Bus service registered: %s", BUS_NAME)
        return BUS_NAME

    async def stop(self) -> None:
        """注销并断开总线连接。"""
        if self._bus is not None:
            if self._interface is not None:
                self._bus.unexport(self._interface, OBJECT_PATH)
            self._bus.disconnect()
            self._bus = None
            self._interface = None
        log.info("D-Bus service stopped")


__all__ = [
    "BUS_NAME",
    "OBJECT_PATH",
    "PixiuDBusInterface",
    "PixiuDBusService",
    "PixiuError",
    "PixiuMemoryHandler",
]
