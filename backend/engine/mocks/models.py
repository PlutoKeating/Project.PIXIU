"""V0.2 契约兼容垫片 —— 数据模型统一来自 foundation core。

保留 ``engine.mocks.models`` 导入路径以兼容既有测试/演示代码，
实际模型全部为 ``backend.foundation.core.models`` 中的定义。
"""

from __future__ import annotations

from backend.engine.security.models import ForgetResult
from backend.foundation.core.models import (
    ConflictRecord,
    ConflictResolution,
    Entity,
    Evidence,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeStatus,
    Preference,
    PreferenceCategory,
    PreferenceSnapshot,
    Relation,
    SourceType,
)

__all__ = [
    "ConflictRecord",
    "ConflictResolution",
    "Entity",
    "Evidence",
    "ForgetResult",
    "KnowledgeItem",
    "KnowledgeKind",
    "KnowledgeStatus",
    "Preference",
    "PreferenceCategory",
    "PreferenceSnapshot",
    "Relation",
    "SourceType",
]
