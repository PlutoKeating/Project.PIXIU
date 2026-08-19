"""security/ —— 敏感识别与自然语言遗忘。

对外暴露 SecurityService。
"""

from __future__ import annotations

from typing import Any, Optional

from backend.foundation.core.repository import EntityRepository, KnowledgeRepository

from backend.engine.security.detector import DetectionResult, Detector
from backend.engine.security.forget import ForgetEngine
from backend.engine.security.models import ForgetResult


class SecurityService:
    def __init__(
        self,
        knw_repo: KnowledgeRepository,
        entity_repo: EntityRepository,
        detector: Optional[Detector] = None,
        forget_engine: Optional[ForgetEngine] = None,
    ) -> None:
        self._knw_repo = knw_repo
        self._entity_repo = entity_repo
        self._detector = detector or Detector()
        self._forget_engine = forget_engine or ForgetEngine()

    async def detect_sensitivity(self, raw: dict[str, Any]) -> int:
        return self._detector.detect(raw)

    async def detect(self, raw: dict[str, Any]) -> DetectionResult:
        """Structured sensitivity result (score + matched type keys)."""
        return self._detector.detect_detail(raw)

    async def forget(self, command: str, confirm: bool, scope: str) -> ForgetResult:
        return await self._forget_engine.forget(
            command,
            scope=scope,
            confirm=confirm,
            knw_repo=self._knw_repo,
            entity_repo=self._entity_repo,
        )


__all__ = ["DetectionResult", "ForgetResult", "SecurityService"]
