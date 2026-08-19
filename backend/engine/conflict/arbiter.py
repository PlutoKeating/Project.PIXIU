"""Conflict arbiter — field-level contradiction detection (NEW_WINS decision).

Candidate selection (same entity / scope) lives in ConflictService +
EntityMatcher. This class only compares already-paired items.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from backend.foundation.core.idgen import gen_conflict_id
from backend.foundation.core.models import ConflictRecord, KnowledgeItem

from backend.engine.conflict.field_matcher import FieldMatcher
from backend.engine.conflict.text_detector import TextConflictDetector


class Arbiter:
    """Compare two ACTIVE items that the service already treated as candidates."""

    def __init__(
        self,
        field_matcher: Optional[FieldMatcher] = None,
        text_detector: Optional[TextConflictDetector] = None,
    ) -> None:
        self._fields = field_matcher or FieldMatcher(text_detector=text_detector)

    def detect(
        self,
        new_item: KnowledgeItem,
        existing: KnowledgeItem,
    ) -> Optional[ConflictRecord]:
        if existing.status != "ACTIVE":
            return None
        if existing.scope != new_item.scope:
            return None

        hit = self._fields.find_conflict(existing, new_item)
        if hit is None:
            return None
        return ConflictRecord(
            id=gen_conflict_id(),
            target_knowledge=existing.id,
            field=hit.field,
            old_value=hit.old_value,
            new_value=hit.new_value,
            resolution="NEW_WINS",
            created_at=int(time.time()),
        )

    def _is_contradiction(self, old_val: Any, new_val: Any) -> bool:
        """Kept for callers/tests that used the previous helper."""
        return self._fields.values_conflict(old_val, new_val)
