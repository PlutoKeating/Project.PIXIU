"""PIXIU Foundation — API 网关 (FastAPI)

按 docs/API.md 注册 REST 端点。已接入引擎 Service 的端点返回真实业务结果；
已实现端点均返回真实持久化业务结果。
"""

from __future__ import annotations
import asyncio
import base64
import contextlib
import os
import tempfile
from contextlib import asynccontextmanager

import time
from typing import Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..core.models import SourceType
from ..flow import FlowContextNotFound, InvalidFlowTransition, MemoryTier
from ..monitor.config_store import InvalidMonitorConfig
from ..sync import PairingError, PairingMethod, PeerNotFound
from .di import (
    get_conflict_repo,
    get_conflict_service,
    get_evidence_repo,
    get_flow_service,
    get_ingestion_service,
    get_knowledge_service,
    get_knowledge_repo,
    get_monitor_config_store,
    get_monitor_log_store,
    get_ocr_service,
    get_optional_sync_service,
    get_preference_repo,
    get_preference_service,
    get_retrieval_service,
    get_security_service,
    get_sync_service,
    start_monitor_runtime,
    start_sync_runtime,
    stop_monitor_runtime,
    stop_sync_runtime,
)
from .monitor_log import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    broadcast_capture_event,
)
from .ws_manager import ws_manager

@asynccontextmanager
async def _lifespan(_: FastAPI):
    await start_sync_runtime()
    await start_monitor_runtime()
    try:
        yield
    finally:
        await stop_monitor_runtime()
        await stop_sync_runtime()



app = FastAPI(
    title="PIXIU Memory API",
    description="面向银河麒麟 OS Agent 的去中心化分布式记忆系统 — API 网关",
    version="0.2.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── request_id 中间件与统一错误响应（对齐 docs/API.md §5）────────

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """为每个请求生成 request_id（响应头 X-Request-Id + request.state）。"""
    from ..core.idgen import gen_request_id

    request_id = gen_request_id()
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


def _error_payload(request: Request, error: str, message: str) -> dict:
    return {
        "error": error,
        "message": message,
        "request_id": getattr(request.state, "request_id", ""),
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(request, str(exc.detail), str(exc.detail)),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content=_error_payload(request, "INVALID_REQUEST", str(exc)),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    from ..core.logger import get_logger

    get_logger(__name__).exception("unhandled error: %s", type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content=_error_payload(request, "INTERNAL_ERROR", "internal server error"),
    )


# ─── 请求模型 ────────────────────────────────────────────

class MemoryWriteRequest(BaseModel):
    source_type: SourceType
    raw: dict[str, Any] = Field(default_factory=dict)
    scope: str
    context: dict[str, Any] = Field(default_factory=dict)


class PreferenceExtractRequest(BaseModel):
    evidence_ids: list[str] = Field(default_factory=list)


class ForgetRequest(BaseModel):
    command: str
    confirm: bool = False


class MemoryQueryRequest(BaseModel):
    text: str
    context_hint: dict[str, Any] = Field(default_factory=dict)


class FlowPromoteRequest(BaseModel):
    source: MemoryTier
    context_ids: list[str] = Field(min_length=1)
    scope: str


class SyncPairRequest(BaseModel):
    method: PairingMethod
    token: str = Field(min_length=1, max_length=16 * 1024)
    pin: str | None = Field(default=None, min_length=6, max_length=6)


class SyncTokenRequest(BaseModel):
    method: PairingMethod
    pin: str | None = Field(default=None, min_length=6, max_length=6)
    ttl_seconds: int = Field(default=300, ge=1, le=900)


class OcrRequest(BaseModel):
    # 二选一：image_base64（前端拖拽/粘贴上传）或 image_path（本机绝对路径）。
    image_base64: str | None = Field(default=None, max_length=20 * 1024 * 1024)
    image_path: str | None = Field(default=None, max_length=4096)


def _latency_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


# ─── 记忆写入 ────────────────────────────────────────────

@app.post("/memory/write", tags=["Memory"], summary="写入一条记忆")
async def memory_write(
    body: MemoryWriteRequest,
    ingestion=Depends(get_ingestion_service),
    knowledge=Depends(get_knowledge_service),
    preference=Depends(get_preference_service),
    conflict=Depends(get_conflict_service),
    sync=Depends(get_optional_sync_service),
):
    """同步落 evidence，随后执行结构化/偏好提取/冲突仲裁，并推送 memory_ready 事件。"""
    started = time.monotonic()
    evidence = await ingestion.ingest(body.source_type.value, body.raw, body.scope)
    item = await knowledge.structure(evidence)
    prefs = await preference.extract(evidence)
    record = await conflict.arbitrate(item)
    if body.scope.startswith("shared:") and sync is not None:
        await sync.record_local(
            f"evidence:{evidence.id}",
            evidence.model_dump(mode="json"),
            evidence.scope,
        )
        await sync.record_local(
            f"knowledge:{item.id}",
            item.model_dump(mode="json"),
            item.scope,
        )
        for extracted in prefs:
            await sync.record_local(
                f"preference:{extracted.id}",
                extracted.model_dump(mode="json"),
                extracted.scope,
            )


    await ws_manager.broadcast(
        "memory_ready",
        {
            "evidence_id": evidence.id,
            "knowledge_id": item.id,
            "title": item.title,
            "scope": evidence.scope,
        },
    )

    if record is not None:
        await ws_manager.broadcast(
            "conflict_detected",
            {
                "conflict_id": record.id,
                "knowledge_title": item.title,
                "field": record.field,
                "old_value": record.old_value,
                "new_value": record.new_value,
            },
        )

    return {
        "evidence_id": evidence.id,
        "status": "accepted",
        "quality_score": evidence.quality_score,
        "sensitivity": evidence.sensitivity,
        "preference_count": len(prefs),
        "conflict_detected": record is not None,
        "latency_ms": _latency_ms(started),
    }


# ─── 证据详情 ────────────────────────────────────────────

@app.get("/evidence/{id}", tags=["Memory"], summary="证据详情")
async def evidence_detail(id: str, evidence_repo=Depends(get_evidence_repo)):
    """按 evidence_id 获取原始证据（供前端 EvidenceCard 查看原文）。"""
    evidence = await evidence_repo.get(id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return evidence.model_dump(mode="json")


# ─── OCR 识别 ────────────────────────────────────────────

@app.post("/memory/ocr", tags=["Memory"], summary="图片文字识别")
async def memory_ocr(
    body: OcrRequest,
    ocr=Depends(get_ocr_service),
):
    """识别图片中的文字（麒麟 kysdk-ocr）；无 SDK 环境返回 OCR_UNAVAILABLE。"""
    from backend.engine.kylin.errors import KylinSDKUnavailableError

    if bool(body.image_base64) == bool(body.image_path):
        raise HTTPException(status_code=400, detail="INVALID_REQUEST")

    started = time.monotonic()
    tmp_path: str | None = None
    image_ref: str
    cleanup = False
    if body.image_base64:
        try:
            data = base64.b64decode(body.image_base64, validate=True)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="INVALID_REQUEST") from exc
        if not data:
            raise HTTPException(status_code=400, detail="INVALID_REQUEST")
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as handle:
            tmp_path = handle.name
            handle.write(data)
        image_ref = tmp_path
        cleanup = True
    else:
        image_ref = str(body.image_path)

    try:
        lines = await asyncio.to_thread(ocr.recognize, image_ref)
    except KylinSDKUnavailableError as exc:
        raise HTTPException(status_code=503, detail="OCR_UNAVAILABLE") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail="INVALID_REQUEST") from exc
    finally:
        if cleanup and tmp_path:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)

    return {
        "text_lines": lines,
        "text": "\n".join(lines),
        "engine": type(ocr).__name__,
        "latency_ms": _latency_ms(started),
    }


# ─── 混合检索 ────────────────────────────────────────────

@app.post("/memory/query", tags=["Memory"], summary="混合检索")
async def memory_query(
    body: MemoryQueryRequest,
    retrieval=Depends(get_retrieval_service),
):
    """BM25 + ANN + Graph 三通道融合检索，返回 MemoryAtom。"""
    atom = await retrieval.query(body.text, body.context_hint)
    return atom.model_dump(mode="json")


# ─── 偏好提取 ────────────────────────────────────────────

@app.post("/preference/extract", tags=["Preference"], summary="触发偏好提取")
async def preference_extract(
    body: PreferenceExtractRequest,
    preference=Depends(get_preference_service),
    evidence_repo=Depends(get_evidence_repo),
):
    started = time.monotonic()
    extracted: list[dict[str, Any]] = []
    for evidence_id in body.evidence_ids:
        evidence = await evidence_repo.get(evidence_id)
        if evidence is None:
            continue
        for pref in await preference.extract(evidence):
            extracted.append(
                {
                    "id": pref.id,
                    "category": pref.category.value,
                    "key": pref.key,
                    "value": pref.value,
                    "confidence": pref.confidence,
                }
            )
    return {
        "extracted_preferences": extracted,
        "latency_ms": _latency_ms(started),
    }


# ─── 偏好版本回溯 ────────────────────────────────────────

@app.get("/preference/{id}/history", tags=["Preference"], summary="偏好版本回溯")
async def preference_history(id: str, pref_repo=Depends(get_preference_repo)):
    pref = await pref_repo.get(id)
    if pref is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    history = await pref_repo.get_history(id)
    return {
        "id": pref.id,
        "key": pref.key,
        "current_version": pref.version,
        "history": [
            {"version": s.version, "value": s.value, "updated_at": s.updated_at}
            for s in history
        ],
    }


# ─── 偏好列表 ────────────────────────────────────────────

@app.get("/preferences", tags=["Preference"], summary="偏好列表")
async def preferences_list(
    scope: str | None = None,
    pref_repo=Depends(get_preference_repo),
):
    """列出偏好，支持按 scope 过滤，供前端 MemoryPanel 选择器使用。"""
    prefs = await pref_repo.list(scope=scope)
    return {"preferences": [p.model_dump(mode="json") for p in prefs]}


# ─── 自然语言遗忘 ────────────────────────────────────────

@app.post("/forget", tags=["Memory"], summary="自然语言遗忘")
async def forget(
    body: ForgetRequest,
    security=Depends(get_security_service),
    knowledge_repo=Depends(get_knowledge_repo),
    sync=Depends(get_optional_sync_service),
):
    started = time.monotonic()
    result = await security.forget(body.command, confirm=body.confirm)
    if result.status == "pending":
        return {
            "targets": result.targets,
            "cascade": result.cascade,
            "irreversible": result.irreversible,
        }
    if sync is not None:
        for forgotten_id in result.forgotten_ids:
            item = await knowledge_repo.get(forgotten_id)
            if item is not None and item.scope.startswith("shared:"):
                await sync.record_local(
                    f"knowledge:{item.id}", {}, item.scope, deleted=True
                )
    await ws_manager.broadcast(
        "forget_confirmation",
        {
            "command": body.command,
            "targets": result.targets,
            "forgotten_ids": result.forgotten_ids,
            "expires_at": int(time.time()) + 10,
        },
    )
    return {
        "status": "forgotten",
        "forgotten_ids": result.forgotten_ids,
        "latency_ms": _latency_ms(started),
    }


# ─── 同步配对 Token 生成 ───────────────────────────────────

@app.post("/sync/token", tags=["Sync"], summary="生成配对令牌")
async def sync_token(body: SyncTokenRequest, sync=Depends(get_sync_service)):
    """生成设备配对令牌（QR/PIN），供前端 PairDialog 使用。"""
    token = await sync.create_pairing_token(body.method, pin=body.pin, ttl_seconds=body.ttl_seconds)
    return {"token": token, "method": body.method.value, "ttl_seconds": body.ttl_seconds}


# ─── 冲突审计 ────────────────────────────────────────────

@app.get("/conflicts", tags=["Memory"], summary="冲突审计列表")
async def conflicts(conflict_repo=Depends(get_conflict_repo)):
    records = await conflict_repo.list()
    return {"conflicts": [r.model_dump(mode="json") for r in records]}


# ─── 记忆流转 ───────────────────────────────────────────

@app.post("/memory/flow/promote", tags=["Flow"], summary="短/中期记忆沉淀到长期")
async def flow_promote(
    body: FlowPromoteRequest,
    flow=Depends(get_flow_service),
):
    started = time.monotonic()
    try:
        knowledge_ids = await flow.promote(
            body.source,
            body.context_ids,
            body.scope,
        )
    except FlowContextNotFound as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
    except InvalidFlowTransition as exc:
        raise HTTPException(status_code=400, detail="INVALID_REQUEST") from exc
    return {
        "promoted_count": len(knowledge_ids),
        "knowledge_ids": knowledge_ids,
        "latency_ms": _latency_ms(started),
    }


# ─── 设备同步 ────────────────────────────────────────────

@app.post("/sync/pair", tags=["Sync"], summary="设备配对")
async def sync_pair(body: SyncPairRequest, sync=Depends(get_sync_service)):
    try:
        peer = await sync.pair(body.method, body.token, pin=body.pin)
    except PairingError as exc:
        raise HTTPException(status_code=422, detail="PAIRING_FAILED") from exc
    await ws_manager.broadcast(
        "sync_event",
        {
            "type": "PEER_ONLINE",
            "peer_id": peer.id,
            "peer_name": peer.name,
            "timestamp": int(time.time()),
        },
    )
    return {
        "peer_id": peer.id,
        "device_name": peer.name,
        "domain": peer.domain,
        "status": "paired",
    }


@app.get("/sync/peers", tags=["Sync"], summary="节点列表")
async def sync_peers(sync=Depends(get_sync_service)):
    return {"peers": await sync.peers()}


@app.get("/sync/status", tags=["Sync"], summary="同步状态")
async def sync_status(sync=Depends(get_sync_service)):
    status = await sync.status()
    return status.model_dump(mode="json")


@app.post("/sync/peers/{id}/revoke", tags=["Sync"], summary="解绑设备")
async def sync_revoke(id: str, sync=Depends(get_sync_service)):
    try:
        peer = await sync.revoke(id)
    except PeerNotFound as exc:
        raise HTTPException(status_code=404, detail="PEER_NOT_FOUND") from exc
    await ws_manager.broadcast(
        "sync_event",
        {
            "type": "PEER_OFFLINE",
            "peer_id": peer.id,
            "peer_name": peer.name,
            "timestamp": int(time.time()),
        },
    )
    return {"status": "revoked", "peer_id": peer.id, "domain": peer.domain}


# ─── 监控配置与活动日志（批次② BE-3，对齐 MONITOR_API_REQUIREMENTS.md）──

@app.get("/monitor/config", tags=["Monitor"], summary="读取监控配置")
async def monitor_config_get(store=Depends(get_monitor_config_store)):
    """读取当前监控配置（daemon 视角的全量状态）。"""
    return store.get()


@app.put("/monitor/config", tags=["Monitor"], summary="写入监控配置（热生效）")
async def monitor_config_put(
    body: dict = Body(...),
    store=Depends(get_monitor_config_store),
    log_store=Depends(get_monitor_log_store),
):
    """全量写入监控配置：持久化 + 热生效 + 写 state_changed 日志 + 广播。

    校验委托 MonitorConfigStore（白名单/类型/相对路径），非法 → 400
    INVALID_REQUEST；热生效由 store.subscribe 驱动 watcher（无需重启 daemon）。
    """
    try:
        normalized = await store.put(body)
    except InvalidMonitorConfig as exc:
        raise HTTPException(status_code=400, detail="INVALID_REQUEST") from exc

    summary = "监控已开启" if normalized["enabled"] else "监控已暂停"
    ts = int(time.time())
    log_store.write_event(
        source="system", status="state_changed", summary=summary, ts=ts
    )
    await broadcast_capture_event(
        source="system", status="state_changed", summary=summary, ts=ts
    )
    return normalized


@app.get("/monitor/log", tags=["Monitor"], summary="监控活动日志（分页）")
async def monitor_log_get(
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
    log_store=Depends(get_monitor_log_store),
):
    """分页查询监控活动记录（按时间倒序，最新在前；空日志返回空数组）。"""
    return {"events": log_store.list_events(limit=limit, offset=offset)}


# WebSocket routes live in a separate module, but the actual uvicorn entrypoint is
# this module. Import only after ``app`` exists to register /events safely.
from . import ws as _ws  # noqa: E402,F401


if __name__ == "__main__":
    import uvicorn

    from ..core.config import settings

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
