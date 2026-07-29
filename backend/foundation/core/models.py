"""PIXIU Foundation — 共享数据模型 (Pydantic v2)

本文件定义 Module B 和 Module C 共同持有（理解）的全部数据模型。
模型设计遵循总体架构 `docs/ARCHITECTURE.md` §2 核心数据模型定义。
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ─── ID 格式校验 ──────────────────────────────────────────

_ID_PATTERNS: dict[str, str] = {
    "evidence": r"^evd_[a-zA-Z0-9]{26}$",
    "knowledge": r"^knw_[a-zA-Z0-9]{26}$",
    "preference": r"^pref_[a-zA-Z0-9]{26}$",
    "conflict": r"^cfl_[a-zA-Z0-9]{26}$",
    "device": r"^dev_[a-zA-Z0-9]{26}$",
    "entity": r"^ent_[a-zA-Z0-9]{26}$",
    "sync_op": r"^sync_[a-zA-Z0-9]{26}$",
}


def validate_id(prefix: str, value: str) -> str:
    pattern = _ID_PATTERNS.get(prefix)
    if pattern and not re.match(pattern, value):
        raise ValueError(f"Invalid {prefix} id format: {value}")
    return value


# ─── 证据 ──────────────────────────────────────────────────

class Evidence(BaseModel):
    """原始证据（可追溯源）。"""

    id: str
    source_type: str = Field(..., pattern=r"^(OCR|TOOL_RESULT|USER_BEHAVIOR|MANUAL_CONFIG)$")
    raw: dict[str, Any] = Field(default_factory=dict)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    sensitivity: int = Field(default=0, ge=0, le=10)
    scope: str
    created_at: int

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        return validate_id("evidence", v)

    model_config = {"validate_assignment": True}


# ─── 知识条目 ──────────────────────────────────────────────

class KnowledgeItem(BaseModel):
    """结构化知识条目。"""

    id: str
    kind: str = Field(..., pattern=r"^(FACT|WORKFLOW|CASE|TEMPLATE)$")
    title: str
    body: dict[str, Any] = Field(default_factory=dict)
    entities: list[str] = Field(default_factory=list)
    relations: list[dict[str, str]] = Field(default_factory=list)
    embedding_ref: str | None = None
    status: str = Field(default="ACTIVE", pattern=r"^(ACTIVE|SUPERSEDED|FORGOTTEN)$")
    version: int = Field(default=1, ge=1)
    evidence_ids: list[str] = Field(default_factory=list)
    scope: str
    created_at: int
    updated_at: int

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        return validate_id("knowledge", v)

    model_config = {"validate_assignment": True}


# ─── 偏好 ──────────────────────────────────────────────────

class Preference(BaseModel):
    """偏好记忆（版本化）。"""

    id: str
    category: str = Field(..., pattern=r"^(OP_HABIT|OUTPUT_STYLE|SECURITY_POLICY)$")
    key: str
    value: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    version: int = Field(default=1, ge=1)
    scope: str
    created_at: int
    updated_at: int

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        return validate_id("preference", v)

    model_config = {"validate_assignment": True}


class PreferenceSnapshot(BaseModel):
    """偏好历史版本快照。"""

    version: int
    value: dict[str, Any]
    updated_at: int


# ─── 实体与关系 ────────────────────────────────────────────

class Entity(BaseModel):
    """命名实体。"""

    id: str
    name: str
    norm_name: str
    type: str

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        return validate_id("entity", v)


class Relation(BaseModel):
    """实体间关系。"""

    src: str
    dst: str
    type: str


# ─── 冲突审计 ──────────────────────────────────────────────

class ConflictRecord(BaseModel):
    """冲突审计记录。"""

    id: str
    target_knowledge: str
    field: str
    old_value: Any = None
    new_value: Any = None
    resolution: str = Field(default="NEW_WINS", pattern=r"^(NEW_WINS|MERGE|MANUAL)$")
    created_at: int

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        return validate_id("conflict", v)


# ─── 检索结果 ──────────────────────────────────────────────

class MemoryAtom(BaseModel):
    """混合检索的最终返回结构。"""

    answer: str
    source_evidence: list[str] = Field(default_factory=list)
    source_knowledge: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    latency_ms: int = 0


# ─── 同步操作 ──────────────────────────────────────────────

class SyncOp(BaseModel):
    """CRDT 同步操作日志条目。"""

    op_id: str
    entity: str
    payload: dict[str, Any]
    vclock: dict[str, int]
    ts: int

    @field_validator("op_id")
    @classmethod
    def _validate_op_id(cls, v: str) -> str:
        return validate_id("sync_op", v)
