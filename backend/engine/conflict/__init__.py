"""conflict/ —— 冲突仲裁。

对外暴露 ConflictService。
"""

from __future__ import annotations

import time
from typing import Optional

from backend.foundation.core.models import ConflictRecord, KnowledgeItem
from backend.foundation.core.repository import ConflictRepository, KnowledgeRepository

from backend.engine.conflict.arbiter import Arbiter


class ConflictService:
    def __init__(
        self,
        knw_repo: KnowledgeRepository,
        conflict_repo: ConflictRepository,
        arbiter: Optional[Arbiter] = None,
    ) -> None:
        self._knw_repo = knw_repo
        self._conflict_repo = conflict_repo
        self._arbiter = arbiter or Arbiter()

    async def arbitrate(self, new_item: KnowledgeItem) -> Optional[ConflictRecord]:
        """Detect semantic conflict with existing ACTIVE knowledge; NEW_WINS by default."""
        candidates = await self._knw_repo.list_active()
        for existing in candidates:
            if existing.id == new_item.id:
                continue
            # Match by identical title within same scope (V0.1 heuristic)
            if existing.title != new_item.title or existing.scope != new_item.scope:
                continue

            record = self._arbiter.detect(new_item, existing)
            if record is None:
                continue

            # Mark old as SUPERSEDED, bump new version lineage
            existing.status = "SUPERSEDED"
            existing.updated_at = int(time.time())
            await self._knw_repo.save(existing)

            new_item.version = max(existing.version + 1, new_item.version)
            new_item.updated_at = int(time.time())
            await self._knw_repo.save(new_item)

            await self._conflict_repo.save(record)
            return record

        # No conflict — ensure new item is persisted if caller hasn't yet
        await self._knw_repo.save(new_item)
        return None


__all__ = ["ConflictService"]
