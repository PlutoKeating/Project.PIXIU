"""Pydantic models aligned with docs/ARCHITECTURE.md and foundation/core contract."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


SourceType = Literal["OCR", "TOOL_RESULT", "USER_BEHAVIOR", "MANUAL_CONFIG"]
KnowledgeKind = Literal["FACT", "WORKFLOW", "CASE", "TEMPLATE"]
KnowledgeStatus = Literal["ACTIVE", "SUPERSEDED", "FORGOTTEN"]
PreferenceCategory = Literal["OP_HABIT", "OUTPUT_STYLE", "SECURITY_POLICY"]
ConflictResolution = Literal["NEW_WINS", "MERGE", "MANUAL"]


class Evidence(BaseModel):
    id: str
    source_type: SourceType
    raw: dict[str, Any]
    quality_score: float = Field(ge=0.0, le=1.0)
    sensitivity: int = Field(default=0, ge=0, le=3)
    scope: str
    created_at: int


class KnowledgeItem(BaseModel):
    id: str
    kind: KnowledgeKind
    title: str
    body: dict[str, Any]
    entities: list[str] = Field(default_factory=list)
    relations: list[dict[str, str]] = Field(default_factory=list)
    embedding_ref: Optional[str] = None
    status: KnowledgeStatus = "ACTIVE"
    version: int = 1
    evidence_ids: list[str] = Field(default_factory=list)
    scope: str
    updated_at: int = 0


class Preference(BaseModel):
    id: str
    category: PreferenceCategory
    key: str
    value: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    version: int = 1
    scope: str
    updated_at: int = 0


class PreferenceSnapshot(BaseModel):
    version: int
    value: dict[str, Any]
    updated_at: int


class Entity(BaseModel):
    id: str
    name: str
    norm_name: str
    type: str = "UNKNOWN"


class Relation(BaseModel):
    src: str
    dst: str
    type: str  # e.g. BELONG_TO


class ConflictRecord(BaseModel):
    id: str
    target_knowledge: str
    field: str = ""
    old_value: Any = None
    new_value: Any = None
    resolution: ConflictResolution = "NEW_WINS"
    created_at: int = 0


class ForgetResult(BaseModel):
    status: Literal["pending", "forgotten"]
    targets: list[dict[str, Any]] = Field(default_factory=list)
    forgotten_ids: list[str] = Field(default_factory=list)
    cascade: dict[str, int] = Field(default_factory=dict)
    irreversible: bool = True
