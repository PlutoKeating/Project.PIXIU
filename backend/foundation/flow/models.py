"""短/中期记忆流转的数据模型。"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.foundation.core.models import validate_scope

_CONTEXT_ID_PATTERN = re.compile(r"^ctx_[a-zA-Z0-9]{26}$")


class MemoryTier(str, Enum):
    """SQLite 上下文只保存短期与中期；长期记忆由 KnowledgeRepository 管理。"""

    SHORT_TERM = "SHORT_TERM"
    MID_TERM = "MID_TERM"


class ContextStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PROMOTED = "PROMOTED"
    EXPIRED = "EXPIRED"


class MemoryContext(BaseModel):
    """可持久化的短/中期上下文。"""

    id: str
    tier: MemoryTier
    payload: dict[str, Any] = Field(default_factory=dict)
    scope: str
    status: ContextStatus = ContextStatus.ACTIVE
    created_at: int
    updated_at: int
    expires_at: int | None = None
    knowledge_id: str | None = None

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not _CONTEXT_ID_PATTERN.match(value):
            raise ValueError(f"Invalid context id format: {value}")
        return value

    @field_validator("scope")
    @classmethod
    def _validate_scope(cls, value: str) -> str:
        return validate_scope(value)

    @model_validator(mode="after")
    def _validate_state(self) -> "MemoryContext":
        if self.status == ContextStatus.PROMOTED and not self.knowledge_id:
            raise ValueError("PROMOTED context requires knowledge_id")
        if self.expires_at is not None and self.expires_at < self.created_at:
            raise ValueError("expires_at must not be earlier than created_at")
        return self

    model_config = {"validate_assignment": True}
