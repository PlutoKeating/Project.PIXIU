"""conflict/ —— 冲突仲裁。

对外暴露 ConflictService。公开构造参数保持向后兼容：
``ConflictService(knw_repo, conflict_repo, arbiter=None)``。

``entity_repo`` 为可选注入。foundation 契约没有按 knowledge id 反查实体的
接口，KnowledgeItem.entities 存的是名称；不注入时用名称/identity 字段匹配。
"""

from __future__ import annotations

import time
from typing import Optional

from backend.foundation.core.models import ConflictRecord, KnowledgeItem
from backend.foundation.core.repository import (
    ConflictRepository,
    EntityRepository,
    KnowledgeRepository,
)

from backend.engine.conflict.arbiter import Arbiter
from backend.engine.conflict.entity_matcher import EntityMatcher
from backend.engine.conflict.text_detector import (
    RuleBasedTextConflictDetector,
    TextConflictDetector,
)


class ConflictService:
    def __init__(
        self,
        knw_repo: KnowledgeRepository,
        conflict_repo: ConflictRepository,
        arbiter: Optional[Arbiter] = None,
        entity_repo: Optional[EntityRepository] = None,
        entity_matcher: Optional[EntityMatcher] = None,
        text_detector: Optional[TextConflictDetector] = None,
    ) -> None:
        self._knw_repo = knw_repo
        self._conflict_repo = conflict_repo
        self._entity_repo = entity_repo
        detector = text_detector or RuleBasedTextConflictDetector()
        self._arbiter = arbiter or Arbiter(text_detector=detector)
        self._entity_matcher = entity_matcher or EntityMatcher(entity_repo=entity_repo)

    async def arbitrate(self, new_item: KnowledgeItem) -> Optional[ConflictRecord]:
        """Detect contradiction with ACTIVE knowledge; default NEW_WINS."""
        candidates = await self._knw_repo.list_active()
        for existing in candidates:
            if not await self._is_candidate(new_item, existing):
                continue
            record = self._arbiter.detect(new_item, existing)
            if record is None:
                continue
            await self._apply_new_wins(existing, new_item, record)
            return record

        await self._knw_repo.save(new_item)
        return None

    async def _is_candidate(
        self,
        new_item: KnowledgeItem,
        existing: KnowledgeItem,
    ) -> bool:
        if existing.id == new_item.id:
            return False
        if existing.scope != new_item.scope:
            return False
        return await self._entity_matcher.matches(new_item, existing)

    async def _apply_new_wins(
        self,
        existing: KnowledgeItem,
        new_item: KnowledgeItem,
        record: ConflictRecord,
    ) -> None:
        existing.status = "SUPERSEDED"
        existing.updated_at = int(time.time())
        await self._knw_repo.save(existing)

        new_item.version = max(existing.version + 1, new_item.version)
        new_item.updated_at = int(time.time())
        await self._knw_repo.save(new_item)

        await self._conflict_repo.save(record)


__all__ = ["ConflictService"]
