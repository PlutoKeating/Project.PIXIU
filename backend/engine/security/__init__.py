"""security/ —— 敏感识别与自然语言遗忘。

对外暴露 SecurityService。
"""

from __future__ import annotations

from typing import Any, Optional

from backend.foundation.core.repository import EntityRepository, KnowledgeRepository

from engine.security.detector import Detector
from engine.security.forget import ForgetEngine
from engine.security.models import ForgetResult


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

    async def forget(self, command: str, confirm: bool) -> ForgetResult:
        return await self._forget_engine.forget(
            command,
            confirm=confirm,
            knw_repo=self._knw_repo,
            entity_repo=self._entity_repo,
        )


__all__ = ["SecurityService", "ForgetResult"]
