"""PIXIU Foundation — API 网关 (FastAPI)

按 docs/API.md 注册 REST 端点。已接入引擎 Service 的端点返回真实业务结果；
已实现端点均返回真实持久化业务结果。
"""

from __future__ import annotations
import asyncio
import base64
import contextlib
import hashlib
import json
import os
import tempfile
from contextlib import asynccontextmanager
from enum import Enum

import time
from typing import Any

from fastapi import Body, Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, model_validator

from ..core.logger import get_logger
from ..core.models import AgentProvenance, KnowledgeStatus, SourceType
from ..core.repository import KnowledgeVersionConflict
from ..flow import FlowContextNotFound, InvalidFlowTransition, MemoryTier
from ..monitor.config_store import InvalidMonitorConfig
from ..storage.idempotency import (
    ClaimStatus,
    IdempotencyConflict,
    IdempotencyCompleted,
    IdempotencyFailed,
    IdempotencyInProgress,
    IdempotencyNotFound,
)
from ..sync import PairRequestError, PairingError, PairingMethod, PeerNotFound
from .di import (
    get_agent_context_service,
    get_agent_ingest_receipt_store,
    get_conflict_repo,
    get_conflict_service,
    get_db,
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
    get_runtime_settings,
    get_security_service,
    get_sync_discovery,
    get_sync_service,
    get_text_embedder,
    get_vector_store,
    preflight_strict_capabilities,
    apply_sync_runtime_settings,
    start_behavior_collector,
    start_monitor_runtime,
    start_sync_runtime,
    stop_behavior_collector,
    stop_db,
    stop_monitor_runtime,
    stop_sync_runtime,
    stop_vector_store,
)
from .capabilities import capability_report
from backend.engine.kylin.embedding import TextEmbedder
from ..core.vector_store import VectorStore
from .monitor_log import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    broadcast_capture_event,
)
from .ws_manager import ws_manager
from .version import API_VERSION, COMPONENT_NAME, version_report

_log = get_logger(__name__)

@asynccontextmanager
async def _lifespan(_: FastAPI):
    try:
        await preflight_strict_capabilities()
        await start_sync_runtime()
        await start_monitor_runtime()
        await start_behavior_collector()
        yield
    finally:
        try:
            await stop_behavior_collector()
            await stop_monitor_runtime()
            await stop_sync_runtime()
            await stop_vector_store()
        finally:
            await stop_db()



app = FastAPI(
    title="PIXIU Memory API",
    description="面向银河麒麟 OS Agent 的去中心化分布式记忆系统 — API 网关",
    version=API_VERSION,
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


@app.get("/version", tags=["System"], summary="组件与契约版本")
async def version():
    return version_report()


@app.get("/health", tags=["System"], summary="后端就绪状态")
async def health(db=Depends(get_db)):
    cursor = await db.execute("SELECT COALESCE(MAX(version), 0) FROM _schema_version")
    row = await cursor.fetchone()
    schema_version = int(row[0]) if row else 0
    if schema_version != version_report()["schema_version"]:
        raise HTTPException(status_code=503, detail="SCHEMA_NOT_READY")
    report = version_report()
    return {
        "status": "ready",
        "product_version": report["product_version"],
        "component": COMPONENT_NAME,
        "database": "ok",
        "schema_version": schema_version,
    }


@app.get("/capabilities")
async def capabilities(
    embedder: TextEmbedder = Depends(get_text_embedder),
    vector_store: VectorStore = Depends(get_vector_store),
    runtime_settings=Depends(get_runtime_settings),
):
    """Expose acceptance-relevant configured and effective runtimes."""
    return capability_report(
        embedding_configured=runtime_settings.embedding,
        embedder=embedder,
        vector_store_configured=runtime_settings.vector_store,
        vector_store=vector_store,
    )

class MemoryWriteRequest(BaseModel):
    source_type: SourceType
    raw: dict[str, Any] = Field(default_factory=dict)
    scope: str
    context: dict[str, Any] = Field(default_factory=dict)
    provenance: AgentProvenance | None = None
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )

    @model_validator(mode="after")
    def _validate_agent_evidence(self) -> "MemoryWriteRequest":
        provenance = self.provenance
        turn_fields = (
            provenance is not None
            and provenance.session_id
            and provenance.run_id
            and provenance.turn_id
            and provenance.occurred_at is not None
        )
        if self.source_type == SourceType.CONVERSATION:
            if not turn_fields:
                raise ValueError(
                    "CONVERSATION requires session_id, run_id, turn_id and occurred_at"
                )
            if not str(self.raw.get("user") or "").strip() or not str(
                self.raw.get("assistant") or ""
            ).strip():
                raise ValueError("CONVERSATION requires user and assistant text")
            if not self.idempotency_key:
                raise ValueError("CONVERSATION requires idempotency_key")
        if self.source_type == SourceType.TOOL_RESULT and provenance is not None:
            if not (
                turn_fields
                and provenance.tool_call_id
                and provenance.tool_name
                and provenance.approved is not None
            ):
                raise ValueError(
                    "agent TOOL_RESULT requires session/run/turn/time/"
                    "tool_call/tool_name/approved"
                )
            if not self.idempotency_key:
                raise ValueError("agent TOOL_RESULT requires idempotency_key")
        return self


class PreferenceExtractRequest(BaseModel):
    evidence_ids: list[str] = Field(default_factory=list)


class MemoryUpdateRequest(BaseModel):
    knowledge_id: str = Field(pattern=r"^knw_[A-Za-z0-9_-]{8,128}$")
    expected_version: int = Field(ge=1)
    scope: str = Field(min_length=1, max_length=256)
    title: str | None = Field(default=None, max_length=512)
    body: dict[str, Any] | None = None
    provenance: AgentProvenance | None = None
    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )

    @model_validator(mode="after")
    def _validate_update(self) -> "MemoryUpdateRequest":
        if self.title is None and self.body is None:
            raise ValueError("knowledge update requires title or body")
        if self.title is not None and not self.title.strip():
            raise ValueError("knowledge update title must not be blank")
        provenance = self.provenance
        if provenance is not None and not (
            provenance.session_id
            and provenance.run_id
            and provenance.turn_id
            and provenance.tool_call_id
            and provenance.tool_name
            and provenance.approved is True
            and provenance.occurred_at is not None
        ):
            raise ValueError("agent knowledge update requires approved tool provenance")
        return self


class ForgetRequest(BaseModel):
    command: str
    confirm: bool = False


class MemoryQueryRequest(BaseModel):
    text: str
    context_hint: dict[str, Any] = Field(default_factory=dict)


class AgentContextRequest(BaseModel):
    query: str = Field(min_length=1, max_length=16 * 1024)
    scope: str = Field(pattern=r"^(user|shared):[A-Za-z0-9._-]+$")
    session_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    turn_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    top_k: int = Field(default=5, ge=1, le=20)
    max_chars: int = Field(default=4000, ge=64, le=16000)
    freshness_seconds: int = Field(default=30 * 24 * 3600, ge=0, le=365 * 24 * 3600)


class AgentLifecycleEvent(str, Enum):
    TURN_START = "TURN_START"
    TURN_END = "TURN_END"
    PRE_COMPRESS = "PRE_COMPRESS"
    SESSION_SWITCH = "SESSION_SWITCH"
    SESSION_END = "SESSION_END"
    DELEGATION = "DELEGATION"


class AgentLifecycleRequest(BaseModel):
    event: AgentLifecycleEvent
    scope: str = Field(pattern=r"^(user|shared):[A-Za-z0-9._-]+$")
    session_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    run_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    turn_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    occurred_at: int = Field(ge=0)
    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    data: dict[str, Any] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_turn_for_turn_events(self) -> "AgentLifecycleRequest":
        if self.event in {
            AgentLifecycleEvent.TURN_START,
            AgentLifecycleEvent.TURN_END,
        } and not self.turn_id:
            raise ValueError(f"{self.event.value} requires turn_id")
        return self


class IdempotencyOperation(str, Enum):
    MEMORY_WRITE = "MEMORY_WRITE"
    MEMORY_UPDATE = "MEMORY_UPDATE"
    LIFECYCLE = "LIFECYCLE"


class AgentRetryRecoveryRequest(BaseModel):
    operation: IdempotencyOperation
    original_request: dict[str, Any]
    confirm_duplicate_risk: bool
    reason: str = Field(min_length=3, max_length=256)

    @model_validator(mode="after")
    def _require_explicit_confirmation(self) -> "AgentRetryRecoveryRequest":
        if not self.confirm_duplicate_risk:
            raise ValueError("duplicate side-effect risk must be explicitly confirmed")
        if len(self.reason.strip()) < 3:
            raise ValueError("recovery reason must contain at least 3 non-space characters")
        return self


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


class SyncPairRequestRequest(BaseModel):
    target_device_id: str


class SyncPairConfirmRequest(BaseModel):
    request_id: str
    accept: bool


class SyncSettingsRequest(BaseModel):
    """SN-4 运行时开关：两者均可缺省，只更新显式传入的键。"""

    enabled: bool | None = None
    paused: bool | None = None


class OcrRequest(BaseModel):
    # 二选一：image_base64（前端拖拽/粘贴上传）或 image_path（本机绝对路径）。
    image_base64: str | None = Field(default=None, max_length=20 * 1024 * 1024)
    image_path: str | None = Field(default=None, max_length=4096)


def _latency_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _canonical_request_hash(body: BaseModel) -> str:
    return hashlib.sha256(
        json.dumps(
            body.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


# ─── 记忆写入 ────────────────────────────────────────────

@app.post("/memory/write", tags=["Memory"], summary="写入一条记忆")
async def memory_write(
    body: MemoryWriteRequest,
    ingestion=Depends(get_ingestion_service),
    knowledge=Depends(get_knowledge_service),
    knowledge_repo=Depends(get_knowledge_repo),
    preference=Depends(get_preference_service),
    conflict=Depends(get_conflict_service),
    security=Depends(get_security_service),
    sync=Depends(get_optional_sync_service),
    idempotency=Depends(get_agent_ingest_receipt_store),
):
    """同步落 evidence，随后执行结构化/偏好提取/冲突仲裁，并推送 memory_ready 事件。"""
    started = time.monotonic()
    try:
        sensitivity = await security.detect_sensitivity(body.raw)
    except Exception as exc:
        _log.exception("sensitivity detector failed")
        raise HTTPException(
            status_code=503,
            detail="SENSITIVITY_CHECK_FAILED",
        ) from exc
    if sensitivity > 0 and body.scope.startswith("shared:"):
        raise HTTPException(status_code=422, detail="SENSITIVE_SHARED_SCOPE")

    request_hash = _canonical_request_hash(body)
    if body.idempotency_key:
        try:
            claim = await idempotency.claim(body.idempotency_key, request_hash)
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from exc
        except IdempotencyInProgress as exc:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_IN_PROGRESS") from exc
        except IdempotencyFailed as exc:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_FAILED") from exc
        if claim.status == ClaimStatus.REPLAY:
            return claim.response

    try:
        evidence = await ingestion.ingest(
            body.source_type.value,
            body.raw,
            body.scope,
            sensitivity=sensitivity,
            provenance=body.provenance,
        )
        item = await knowledge.structure(evidence)
        prefs = await preference.extract(evidence)
        record = await conflict.arbitrate(item)
        persisted_item = await knowledge_repo.get(item.id)
        if persisted_item is None:
            raise RuntimeError("knowledge disappeared after conflict arbitration")
        item = persisted_item
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
                    "severity": record.severity,
                },
            )

        response = {
            "evidence_id": evidence.id,
            "status": "accepted",
            "quality_score": evidence.quality_score,
            "sensitivity": evidence.sensitivity,
            "preference_count": len(prefs),
            "conflict_detected": record is not None,
            "latency_ms": _latency_ms(started),
        }
        if body.idempotency_key:
            await idempotency.complete(body.idempotency_key, request_hash, response)
        return response
    except Exception:
        if body.idempotency_key:
            await idempotency.fail(body.idempotency_key, request_hash)
        raise


@app.post("/memory/update", tags=["Memory"], summary="更新既有记忆")
async def memory_update(
    body: MemoryUpdateRequest,
    ingestion=Depends(get_ingestion_service),
    knowledge=Depends(get_knowledge_service),
    knowledge_repo=Depends(get_knowledge_repo),
    security=Depends(get_security_service),
    sync=Depends(get_optional_sync_service),
    idempotency=Depends(get_agent_ingest_receipt_store),
):
    """Optimistically update one knowledge ID, reindex it, and emit a sync op."""
    started = time.monotonic()
    existing = await knowledge_repo.get(body.knowledge_id)
    if existing is None or existing.scope != body.scope:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    if existing.status != KnowledgeStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="KNOWLEDGE_NOT_ACTIVE")

    title = body.title.strip() if body.title is not None else existing.title
    updated_body = body.body if body.body is not None else existing.body
    update_raw = {
        "title": f"Update: {title}",
        "body": {
            "operation": "knowledge_update",
            "target_knowledge": existing.id,
            "new_title": title,
            "value": updated_body,
        },
    }
    try:
        sensitivity = await security.detect_sensitivity(update_raw)
    except Exception as exc:
        _log.exception("sensitivity detector failed")
        raise HTTPException(
            status_code=503, detail="SENSITIVITY_CHECK_FAILED"
        ) from exc
    if sensitivity > 0 and existing.scope.startswith("shared:"):
        raise HTTPException(status_code=422, detail="SENSITIVE_SHARED_SCOPE")

    request_hash = _canonical_request_hash(body)
    receipt_key = f"update:{body.idempotency_key}"
    try:
        claim = await idempotency.claim(receipt_key, request_hash)
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from exc
    except IdempotencyInProgress as exc:
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_IN_PROGRESS") from exc
    except IdempotencyFailed as exc:
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_FAILED") from exc
    if claim.status == ClaimStatus.REPLAY:
        return claim.response

    try:
        if existing.version != body.expected_version:
            raise HTTPException(status_code=409, detail="VERSION_CONFLICT")
        evidence = await ingestion.ingest(
            (
                SourceType.TOOL_RESULT.value
                if body.provenance is not None
                else SourceType.MANUAL_CONFIG.value
            ),
            update_raw,
            existing.scope,
            sensitivity=sensitivity,
            provenance=body.provenance,
        )
        updated = existing.model_copy(
            update={
                "title": title,
                "body": updated_body,
                "version": existing.version + 1,
                "updated_at": int(time.time()),
                "evidence_ids": [*existing.evidence_ids, evidence.id],
            }
        )
        try:
            updated = await knowledge.update(
                updated, expected_version=body.expected_version
            )
        except KnowledgeVersionConflict as exc:
            raise HTTPException(status_code=409, detail="VERSION_CONFLICT") from exc
        if existing.scope.startswith("shared:") and sync is not None:
            await sync.record_local(
                f"evidence:{evidence.id}",
                evidence.model_dump(mode="json"),
                evidence.scope,
            )
            await sync.record_local(
                f"knowledge:{updated.id}",
                updated.model_dump(mode="json"),
                updated.scope,
            )
        response = {
            "knowledge_id": updated.id,
            "evidence_id": evidence.id,
            "version": updated.version,
            "status": "updated",
            "latency_ms": _latency_ms(started),
        }
        await idempotency.complete(receipt_key, request_hash, response)
        await ws_manager.broadcast(
            "memory_ready",
            {
                "evidence_id": evidence.id,
                "knowledge_id": updated.id,
                "title": updated.title,
                "scope": updated.scope,
                "operation": "update",
            },
        )
        return response
    except Exception:
        await idempotency.fail(receipt_key, request_hash)
        raise


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


@app.post("/agent/context", tags=["Agent"], summary="构建 Agent 轮次记忆上下文")
async def agent_context(
    body: AgentContextRequest,
    service=Depends(get_agent_context_service),
):
    """返回受 scope、敏感度和字符预算约束且可追溯的记忆上下文。"""
    return await service.build(
        body.query,
        body.scope,
        session_id=body.session_id,
        turn_id=body.turn_id,
        top_k=body.top_k,
        max_chars=body.max_chars,
        freshness_seconds=body.freshness_seconds,
    )


@app.post("/agent/lifecycle", tags=["Agent"], summary="记录 Agent 生命周期上下文")
async def agent_lifecycle(
    body: AgentLifecycleRequest,
    flow=Depends(get_flow_service),
    idempotency=Depends(get_agent_ingest_receipt_store),
):
    """把上游生命周期事件持久化为服务端选定层级的短/中期上下文。"""
    request_hash = _canonical_request_hash(body)
    receipt_key = f"lifecycle:{body.idempotency_key}"
    try:
        claim = await idempotency.claim(receipt_key, request_hash)
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from exc
    except IdempotencyInProgress as exc:
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_IN_PROGRESS") from exc
    except IdempotencyFailed as exc:
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_FAILED") from exc
    if claim.status == ClaimStatus.REPLAY:
        return claim.response

    tier = (
        MemoryTier.SHORT_TERM
        if body.event in {AgentLifecycleEvent.TURN_START, AgentLifecycleEvent.TURN_END}
        else MemoryTier.MID_TERM
    )
    try:
        context = await flow.remember(
            tier,
            {
                "event": body.event.value,
                "session_id": body.session_id,
                "run_id": body.run_id,
                "turn_id": body.turn_id,
                "occurred_at": body.occurred_at,
                "data": body.data,
            },
            body.scope,
        )
        response = {
            "event": body.event.value,
            "context_id": context.id,
            "tier": context.tier.value,
            "status": context.status.value,
            "expires_at": context.expires_at,
        }
        await idempotency.complete(receipt_key, request_hash, response)
        return response
    except Exception:
        await idempotency.fail(receipt_key, request_hash)
        raise


@app.post(
    "/agent/idempotency/recover",
    tags=["Agent"],
    summary="授权重试一条失败的 Agent 幂等请求",
)
async def agent_idempotency_recover(
    body: AgentRetryRecoveryRequest,
    idempotency=Depends(get_agent_ingest_receipt_store),
):
    """在人工核验副作用后，为完全相同的 FAILED 请求授权一次重试。"""
    try:
        if body.operation == IdempotencyOperation.MEMORY_WRITE:
            original = MemoryWriteRequest.model_validate(body.original_request)
            if not original.idempotency_key:
                raise HTTPException(
                    status_code=400,
                    detail="IDEMPOTENCY_KEY_REQUIRED",
                )
            external_key = original.idempotency_key
            receipt_key = external_key
        elif body.operation == IdempotencyOperation.MEMORY_UPDATE:
            original = MemoryUpdateRequest.model_validate(body.original_request)
            external_key = original.idempotency_key
            receipt_key = f"update:{external_key}"
        else:
            original = AgentLifecycleRequest.model_validate(body.original_request)
            external_key = original.idempotency_key
            receipt_key = f"lifecycle:{external_key}"
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail="INVALID_RECOVERY_REQUEST",
        ) from exc

    try:
        authorization = await idempotency.authorize_retry(
            receipt_key,
            _canonical_request_hash(original),
            body.reason.strip(),
        )
    except IdempotencyNotFound as exc:
        raise HTTPException(status_code=404, detail="IDEMPOTENCY_NOT_FOUND") from exc
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from exc
    except IdempotencyInProgress as exc:
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_IN_PROGRESS") from exc
    except IdempotencyCompleted as exc:
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_COMPLETED") from exc

    return {
        "operation": body.operation.value,
        "idempotency_key": external_key,
        "status": "RETRY_AUTHORIZED",
        "recovery_count": authorization.recovery_count,
        "authorized_at": authorization.authorized_at,
    }


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


@app.get("/sync/discover", tags=["Sync"], summary="发现局域网设备")
async def sync_discover(
    sync=Depends(get_sync_service),
    discovery=Depends(get_sync_discovery),
):
    """列出局域网内已发现设备（含未配对），paired 标注本地信任关系。"""
    identity = await sync.initialize()
    advertisements = await discovery.list_advertisements()
    known = {peer["id"] for peer in await sync.peers()}
    devices = [
        {
            "device_id": adv.device_id,
            "device_name": adv.name,
            "addresses": list(adv.addresses),
            "port": adv.port,
            "pairable": adv.pairable,
            "paired": adv.device_id in known,
        }
        for adv in advertisements
        if adv.device_id != identity.id
    ]
    return {"devices": devices}


@app.post("/sync/pair/request", tags=["Sync"], summary="发起配对请求")
async def sync_pair_request(
    body: SyncPairRequestRequest, sync=Depends(get_sync_service)
):
    """发起确认式配对请求（含 6 位 PIN，TTL 60s）；确认由目标机弹窗完成。"""
    try:
        result = await sync.create_pair_request(body.target_device_id)
    except PairRequestError as exc:
        raise HTTPException(status_code=400, detail="INVALID_REQUEST") from exc
    await ws_manager.broadcast(
        "pair_request",
        {
            "type": "INCOMING",
            "request_id": result["request_id"],
            "from_device_id": result["target_device_id"],
            "from_name": "",
            "pin": result["pin"],
            "expires_at": result["expires_at"],
        },
    )
    return result


@app.post("/sync/pair/confirm", tags=["Sync"], summary="确认/拒绝配对请求")
async def sync_pair_confirm(
    body: SyncPairConfirmRequest, sync=Depends(get_sync_service)
):
    status = await sync.confirm_pair_request(
        body.request_id, accept=body.accept
    )
    if status == "not_found":
        raise HTTPException(status_code=404, detail="REQUEST_NOT_FOUND")
    return {"status": status}


@app.get("/sync/status", tags=["Sync"], summary="同步状态")
async def sync_status(sync=Depends(get_sync_service)):
    status = await sync.status()
    return status.model_dump(mode="json")


@app.get(
    "/sync/state/knowledge/{knowledge_id}",
    tags=["Sync"],
    summary="查询知识的去载荷 CRDT 状态",
)
async def sync_knowledge_state(
    knowledge_id: str = Path(pattern=r"^knw_[A-Za-z0-9_-]{8,128}$"),
    sync=Depends(get_sync_service),
):
    """仅返回墓碑、版本计数和操作摘要，不暴露同步载荷或设备身份。"""
    return await sync.entity_state(f"knowledge:{knowledge_id}")


@app.put("/sync/settings", tags=["Sync"], summary="更新同步开关")
async def sync_settings_put(
    body: SyncSettingsRequest, sync=Depends(get_sync_service)
):
    """运行时开关（enabled/paused）KV 持久化 + 热生效。

    enabled=false 停止 runtime（mDNS 注册与监听停）；enabled=true 启动
    （若未启动）；paused 暂停 gossip 数据流（保留发现与配对）。
    """
    result = await sync.set_settings(
        enabled=body.enabled, paused=body.paused
    )
    await apply_sync_runtime_settings(
        enabled=result["enabled"], paused=result["paused"]
    )
    return result


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

    # store.put 已持久化 + 热生效：后续写日志/广播属旁路副作用，失败只记日志、
    # 不改变已生效配置，也不向客户端谎报 500（对齐 _make_capture_callback 的
    # 隔离语义，di.py:314-356）。
    summary = "监控已开启" if normalized["enabled"] else "监控已暂停"
    ts = int(time.time())
    try:
        log_store.write_event(
            source="system", status="state_changed", summary=summary, ts=ts
        )
    except Exception:
        _log.exception("monitor state_changed log write failed")
    try:
        await broadcast_capture_event(
            source="system", status="state_changed", summary=summary, ts=ts
        )
    except Exception:
        _log.exception("monitor state_changed broadcast failed")
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

# 递送层端点（B4-1）：delivery.py 导入 app 并注册 /delivery/insights。
from . import delivery as _delivery  # noqa: E402,F401


if __name__ == "__main__":
    import uvicorn

    from ..core.config import settings

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
