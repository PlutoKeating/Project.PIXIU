"""PIXIU Foundation — 共享数据模型 (Pydantic v2, Python 3.10+)

本文件定义 Module B 和 Module C 共同持有（理解）的全部数据模型。
字段定义遵循：
  - docs/ARCHITECTURE.md §2 核心数据模型
  - backend/foundation/docs/ARCHITECTURE.md §1.1
  - docs/DEVELOPMENT_PLAN.md §3.2

所有时间戳统一为 UTC Unix 秒（int）。
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ══════════════════════════════════════════════════════════
# 枚举（Python 3.10 兼容 str + Enum）
# ══════════════════════════════════════════════════════════


class SourceType(str, Enum):
    """证据来源类型。"""

    OCR = "OCR"
    TOOL_RESULT = "TOOL_RESULT"
    USER_BEHAVIOR = "USER_BEHAVIOR"
    MANUAL_CONFIG = "MANUAL_CONFIG"


class KnowledgeKind(str, Enum):
    """知识条目类型。"""

    FACT = "FACT"
    WORKFLOW = "WORKFLOW"
    CASE = "CASE"
    TEMPLATE = "TEMPLATE"


class KnowledgeStatus(str, Enum):
    """知识条目状态。"""

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    FORGOTTEN = "FORGOTTEN"


class PreferenceCategory(str, Enum):
    """偏好类别。"""

    OP_HABIT = "OP_HABIT"
    OUTPUT_STYLE = "OUTPUT_STYLE"
    SECURITY_POLICY = "SECURITY_POLICY"


class ConflictResolution(str, Enum):
    """冲突裁决方式。"""

    NEW_WINS = "NEW_WINS"
    MERGE = "MERGE"
    MANUAL = "MANUAL"


# ══════════════════════════════════════════════════════════
# ID 格式校验
# ══════════════════════════════════════════════════════════

_ID_PATTERNS: dict[str, str] = {
    "evidence": r"^evd_[a-zA-Z0-9]{26}$",
    "knowledge": r"^knw_[a-zA-Z0-9]{26}$",
    "preference": r"^pref_[a-zA-Z0-9]{26}$",
    "conflict": r"^cfl_[a-zA-Z0-9]{26}$",
    "device": r"^dev_[a-zA-Z0-9]{26}$",
    "entity": r"^ent_[a-zA-Z0-9]{26}$",
    "sync_op": r"^sync_[a-zA-Z0-9]{26}$",
}

_SCOPE_PATTERN = re.compile(r"^(user|shared):[a-zA-Z0-9_-]+$")


def validate_id(prefix: str, value: str) -> str:
    pattern = _ID_PATTERNS.get(prefix)
    if pattern and not re.match(pattern, value):
        raise ValueError(f"Invalid {prefix} id format: {value}")
    return value


def validate_scope(v: str) -> str:
    if not _SCOPE_PATTERN.match(v):
        raise ValueError(f"Invalid scope format: {v}")
    return v


# ══════════════════════════════════════════════════════════
# Evidence — 原始证据（可追溯源）
# ══════════════════════════════════════════════════════════


class Evidence(BaseModel):
    """原始证据（可追溯源）。

    source_type — OCR / TOOL_RESULT / USER_BEHAVIOR / MANUAL_CONFIG
    quality_score — 0.0~1.0 质量评分
    sensitivity — 0~10 敏感度
    scope — 格式 user:xxx 或 shared:xxx
    """

    id: str
    source_type: SourceType
    raw: dict[str, Any] = Field(default_factory=dict)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    sensitivity: int = Field(default=0, ge=0, le=10)
    scope: str
    created_at: int

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        return validate_id("evidence", v)

    @field_validator("scope")
    @classmethod
    def _validate_scope(cls, v: str) -> str:
        return validate_scope(v)

    model_config = {"validate_assignment": True}


# ══════════════════════════════════════════════════════════
# KnowledgeItem — 结构化知识条目
# ══════════════════════════════════════════════════════════


class KnowledgeItem(BaseModel):
    """结构化知识条目。

    kind — FACT / WORKFLOW / CASE / TEMPLATE
    status — ACTIVE / SUPERSEDED / FORGOTTEN
    scope — 格式 user:xxx 或 shared:xxx
    """

    id: str
    kind: KnowledgeKind
    title: str
    body: dict[str, Any] = Field(default_factory=dict)
    entities: list[str] = Field(default_factory=list)
    relations: list[dict[str, str]] = Field(default_factory=list)
    embedding_ref: str | None = None
    status: KnowledgeStatus = Field(default=KnowledgeStatus.ACTIVE)
    version: int = Field(default=1, ge=1)
    evidence_ids: list[str] = Field(default_factory=list)
    scope: str
    created_at: int
    updated_at: int

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        return validate_id("knowledge", v)

    @field_validator("scope")
    @classmethod
    def _validate_scope(cls, v: str) -> str:
        return validate_scope(v)

    model_config = {"validate_assignment": True}


# ══════════════════════════════════════════════════════════
# Preference — 偏好记忆（版本化）
# ══════════════════════════════════════════════════════════


class Preference(BaseModel):
    """偏好记忆（版本化）。

    category — OP_HABIT / OUTPUT_STYLE / SECURITY_POLICY
    confidence — 0.0~1.0
    scope — 格式 user:xxx 或 shared:xxx
    """

    id: str
    category: PreferenceCategory
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

    @field_validator("scope")
    @classmethod
    def _validate_scope(cls, v: str) -> str:
        return validate_scope(v)

    model_config = {"validate_assignment": True}


class PreferenceSnapshot(BaseModel):
    """偏好历史版本快照。"""

    version: int = Field(ge=1)
    value: dict[str, Any] = Field(default_factory=dict)
    updated_at: int


# ══════════════════════════════════════════════════════════
# Entity / Relation — 实体关系图
# ══════════════════════════════════════════════════════════


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
    """实体间关系（e.g. BELONG_TO）。"""

    src: str
    dst: str
    type: str


# ══════════════════════════════════════════════════════════
# ConflictRecord — 冲突审计
# ══════════════════════════════════════════════════════════


class ConflictRecord(BaseModel):
    """冲突审计记录。

    resolution — NEW_WINS / MERGE / MANUAL
    source — write（本地写入）/ sync（同步分叉转人工，SN-3 mainline）
    severity — low / medium / high（B3-3 S3.1，按 resolution 映射；
               默认 high 保证旧构造路径向后兼容且最保守）
    """

    id: str
    target_knowledge: str
    field: str
    old_value: Any = None
    new_value: Any = None
    resolution: ConflictResolution = Field(default=ConflictResolution.NEW_WINS)
    created_at: int
    source: str = "write"
    severity: str = "high"

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        return validate_id("conflict", v)


def conflict_severity_for(resolution: ConflictResolution | str) -> str:
    """按裁决方式映射冲突打扰级别（B3-3 [S3.1]）。

    - MERGE    → low：自动合并，静默
    - NEW_WINS → medium：自动裁决，但用户应知晓
    - MANUAL   → high：需人工确认

    未知值保守回落 high（宁可打扰不漏报）。str 输入供 DB 回读路径使用
    （repository._row_to_conflict 的 row["resolution"] 是 str）。
    """
    key = resolution.value if isinstance(resolution, ConflictResolution) else str(resolution)
    return {
        ConflictResolution.MERGE.value: "low",
        ConflictResolution.NEW_WINS.value: "medium",
        ConflictResolution.MANUAL.value: "high",
    }.get(key, "high")


# ══════════════════════════════════════════════════════════
# MemoryAtom — 混合检索结果
# ══════════════════════════════════════════════════════════


class MemoryAtom(BaseModel):
    """混合检索的最终返回结构。

    confidence — 0.0~1.0
    latency_ms — 检索耗时（毫秒）
    """

    answer: str
    source_evidence: list[str] = Field(default_factory=list)
    source_knowledge: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    latency_ms: int = Field(default=0, ge=0)


# ══════════════════════════════════════════════════════════
# SyncOp — 同步操作日志
# ══════════════════════════════════════════════════════════


class SyncOp(BaseModel):
    """CRDT 同步操作日志条目。"""

    op_id: str
    entity: str
    payload: dict[str, Any] = Field(default_factory=dict)
    vclock: dict[str, int] = Field(default_factory=dict)
    ts: int

    @field_validator("op_id")
    @classmethod
    def _validate_op_id(cls, v: str) -> str:
        return validate_id("sync_op", v)
