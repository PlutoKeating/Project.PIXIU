"""Persist reviewable document corrections; approval is a desktop API, not an Agent tool."""
import json
import secrets
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .di import (get_db, get_knowledge_repo, get_ingestion_service, get_knowledge_service,
                 get_security_service, get_optional_sync_service, get_agent_ingest_receipt_store)
from .documents import authorized_source
from .ws_manager import ws_manager
from ..documents.registry import DocumentRegistry, DocumentUnavailable
from ..core.models import KnowledgeStatus

router = APIRouter(prefix="/dreaming/plans", tags=["Dreaming"])


class PlanSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    version: str
    block_id: str


class ReviewPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["update"]
    scope: str = Field(pattern=r"^user:[A-Za-z0-9._-]+$")
    knowledge_id: str = Field(pattern=r"^knw_[A-Za-z0-9_-]{8,128}$")
    expected_version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=512)
    text: str = Field(min_length=1, max_length=60000)
    source_refs: list[PlanSource] = Field(min_length=1, max_length=100)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool


@router.post("")
async def propose_plan(body: ReviewPlan, db=Depends(get_db), knowledge=Depends(get_knowledge_repo)):
    item = await knowledge.get(body.knowledge_id)
    if item is None or item.scope != body.scope or item.status != KnowledgeStatus.ACTIVE:
        raise HTTPException(404, "MEMORY_UNAVAILABLE")
    if item.version != body.expected_version:
        raise HTTPException(409, "VERSION_CONFLICT")
    registry = DocumentRegistry(db, authorized_source)
    sources, paths = [], set()
    try:
        for ref in body.source_refs:
            document = await registry._get(ref.document_id)
            if document["version"] != ref.version:
                raise HTTPException(409, "DOCUMENT_VERSION_CONFLICT")
            block = next((entry for entry in document["blocks"] if entry["id"] == ref.block_id), None)
            if block is None:
                raise HTTPException(422, "SOURCE_BLOCK_UNAVAILABLE")
            sources.append({**ref.model_dump(), "block": block})
            if document.get("source_path"):
                paths.add(document["source_path"])
    except DocumentUnavailable as exc:
        raise HTTPException(404, "DOCUMENT_UNAVAILABLE") from exc
    # Copy verified source blocks before attachment staging is revoked. The review
    # keeps the evidence it actually displays; directory grants are checked again.
    plan = {**body.model_dump(), "before": {"title": item.title, "body": item.body, "version": item.version},
            "sources": sources, "source_paths": sorted(paths)}
    encoded = json.dumps(plan, ensure_ascii=False)
    if len(encoded.encode()) > 100 * 1024 * 1024:
        raise HTTPException(422, "PLAN_TOO_LARGE")
    identifier = secrets.token_hex(16)
    await db.execute("INSERT INTO dreaming_plans(id,payload,status,created_at) VALUES(?,?,?,?)",
                     (identifier, encoded, "pending", int(time.time())))
    await db.commit()
    await ws_manager.broadcast("dreaming_review", {"plan_id": identifier, "status": "pending"})
    return {"plan_id": identifier, "status": "awaiting_approval"}


@router.get("")
async def list_plans(db=Depends(get_db)):
    cursor = await db.execute("SELECT id,payload,status,created_at FROM dreaming_plans WHERE status IN ('pending','executing','failed') ORDER BY created_at")
    result = []
    for identifier, payload, status, created_at in await cursor.fetchall():
        plan = json.loads(payload)
        result.append({"plan_id": identifier, "status": status, "created_at": created_at,
                       "operation": plan["operation"], "title": plan["title"], "text": plan["text"],
                       "before": plan["before"], "scope": plan["scope"]})
    return {"plans": result}


@router.post("/{plan_id}/decision")
async def decide_plan(plan_id: str, decision: Decision, db=Depends(get_db),
                      ingestion=Depends(get_ingestion_service), knowledge=Depends(get_knowledge_service),
                      knowledge_repo=Depends(get_knowledge_repo), security=Depends(get_security_service),
                      sync=Depends(get_optional_sync_service), receipts=Depends(get_agent_ingest_receipt_store)):
    cursor = await db.execute("SELECT payload,status,result FROM dreaming_plans WHERE id=?", (plan_id,))
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(404, "PLAN_UNAVAILABLE")
    plan, status, result = json.loads(row[0]), row[1], row[2]
    if status in {"completed", "rejected"}:
        return {"plan_id": plan_id, "status": status, "result": json.loads(result) if result else None}
    if not decision.approve:
        if status == "executing":
            raise HTTPException(409, "PLAN_EXECUTING")
        cursor = await db.execute("UPDATE dreaming_plans SET status='rejected' WHERE id=? AND status IN ('pending','failed')", (plan_id,))
        await db.commit()
        if not cursor.rowcount:
            raise HTTPException(409, "PLAN_STATE_CHANGED")
        await ws_manager.broadcast("dreaming_review", {"plan_id": plan_id, "status": "rejected"})
        return {"plan_id": plan_id, "status": "rejected"}
    if status == "failed":
        raise HTTPException(409, "PLAN_REQUIRES_NEW_REVIEW")
    if any(not authorized_source(path) for path in plan["source_paths"]):
        raise HTTPException(409, "SOURCE_AUTHORIZATION_REVOKED")
    await db.execute("UPDATE dreaming_plans SET status='executing' WHERE id=? AND status='pending'", (plan_id,))
    await db.commit()
    cursor = await db.execute("SELECT status FROM dreaming_plans WHERE id=?", (plan_id,))
    if (await cursor.fetchone())[0] != "executing":
        raise HTTPException(409, "PLAN_STATE_CHANGED")
    from .http_app import MemoryUpdateRequest, memory_update
    try:
        result = await memory_update(MemoryUpdateRequest(knowledge_id=plan["knowledge_id"], scope=plan["scope"],
            expected_version=plan["expected_version"], title=plan["title"],
            body={"content": plan["text"], "document_sources": plan["sources"]},
            idempotency_key="dreaming-review:" + plan_id), ingestion=ingestion, knowledge=knowledge,
            knowledge_repo=knowledge_repo, security=security, sync=sync, idempotency=receipts)
    except HTTPException as exc:
        # An in-flight duplicate must not overwrite the first request's outcome.
        if exc.detail != "IDEMPOTENCY_IN_PROGRESS":
            await db.execute("UPDATE dreaming_plans SET status='failed' WHERE id=? AND status='executing'", (plan_id,))
            await db.commit()
        raise
    await db.execute("UPDATE dreaming_plans SET status='completed',result=? WHERE id=?",
                     (json.dumps(result), plan_id))
    await db.commit()
    await ws_manager.broadcast("dreaming_review", {"plan_id": plan_id, "status": "completed"})
    return {"plan_id": plan_id, "status": "completed", "result": result}
