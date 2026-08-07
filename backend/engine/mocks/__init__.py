"""V0.2 引擎测试内存仓储 —— 实现 foundation/core Repository ABC。

模型统一来自 ``backend.foundation.core.models``；本包仅提供内存仓储实现。
"""

from __future__ import annotations

from backend.engine.mocks.repository import (
    MockConflictRepository,
    MockEntityRepository,
    MockEvidenceRepository,
    MockKnowledgeRepository,
    MockPreferenceRepository,
)

__all__ = [
    "MockConflictRepository",
    "MockEntityRepository",
    "MockEvidenceRepository",
    "MockKnowledgeRepository",
    "MockPreferenceRepository",
]
