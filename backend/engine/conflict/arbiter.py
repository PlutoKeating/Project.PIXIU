"""Conflict arbiter — detect field-level contradictions and decide NEW_WINS."""

from __future__ import annotations

import time
from typing import Any, Optional

from backend.foundation.core.idgen import gen_conflict_id
from backend.foundation.core.models import ConflictRecord, KnowledgeItem


def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            flat.update(_flatten(v, key))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            key = f"{prefix}[{i}]"
            flat.update(_flatten(v, key))
    else:
        flat[prefix] = obj
    return flat


class Arbiter:
    """Compare new knowledge against an existing ACTIVE item with same title/scope."""

    def detect(
        self,
        new_item: KnowledgeItem,
        existing: KnowledgeItem,
    ) -> Optional[ConflictRecord]:
        if existing.status != "ACTIVE":
            return None
        if existing.scope != new_item.scope:
            return None

        old_flat = _flatten(existing.body)
        new_flat = _flatten(new_item.body)

        for field, new_val in new_flat.items():
            if field not in old_flat:
                continue
            old_val = old_flat[field]
            if self._is_contradiction(old_val, new_val):
                return ConflictRecord(
                    id=gen_conflict_id(),
                    target_knowledge=existing.id,
                    field=field,
                    old_value=old_val,
                    new_value=new_val,
                    resolution="NEW_WINS",
                    created_at=int(time.time()),
                )
        return None

    @staticmethod
    def _is_contradiction(old_val: Any, new_val: Any) -> bool:
        if old_val == new_val:
            return False
        # Numeric compare
        if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
            return float(old_val) != float(new_val)
        # Enum / string: treat different non-empty strings as contradiction
        if old_val is None or new_val is None:
            return False
        return str(old_val) != str(new_val)
