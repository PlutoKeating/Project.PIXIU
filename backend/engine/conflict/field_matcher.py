"""FieldMatcher — same-entity, same-field comparison.

Flattening by list index (items[0].amount) mis-aligns records when the same
entity appears at different positions. This matcher groups scalar fields by
the record's instance identity (vendor/entity/org/…) and only compares values
that share both that identity and the field name.

Numeric / bool / closed enum: inequality is a contradiction.
Text: delegated to TextConflictDetector (not raw string !=).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from backend.foundation.core.models import KnowledgeItem

from backend.engine.conflict.entity_matcher import (
    category_keys,
    identity_keys,
    normalize_entity_key,
)
from backend.engine.conflict.text_detector import (
    RuleBasedTextConflictDetector,
    TextConflictDetector,
)

_ENUM_VALUES = frozenset(
    {
        "true",
        "false",
        "yes",
        "no",
        "on",
        "off",
        "enabled",
        "disabled",
        "active",
        "inactive",
        "开启",
        "关闭",
        "是",
        "否",
        "开",
        "关",
        "允许",
        "禁止",
        "启用",
        "禁用",
    }
)

FactKey = tuple[Optional[str], str]


@dataclass(frozen=True)
class FieldConflict:
    field: str
    old_value: Any
    new_value: Any


class FieldMatcher:
    """Find the first contradictory (entity, field) pair between two items."""

    def __init__(
        self,
        text_detector: Optional[TextConflictDetector] = None,
    ) -> None:
        self._text = text_detector or RuleBasedTextConflictDetector()

    def find_conflict(
        self,
        existing: KnowledgeItem,
        new_item: KnowledgeItem,
    ) -> Optional[FieldConflict]:
        old_facts = self.extract_facts(existing)
        new_facts = self.extract_facts(new_item)
        shared = set(old_facts) & set(new_facts)
        if not shared:
            return None
        for key in sorted(shared, key=lambda item: (item[0] or "", item[1])):
            old_val = old_facts[key]
            new_val = new_facts[key]
            if not self.values_conflict(old_val, new_val):
                continue
            entity, field = key
            field_name = f"{entity}.{field}" if entity else field
            return FieldConflict(field=field_name, old_value=old_val, new_value=new_val)
        return None

    def extract_facts(self, item: KnowledgeItem) -> dict[FactKey, Any]:
        facts: dict[FactKey, Any] = {}
        self._walk(item.body, facts, current_entity=None)
        return facts

    def _walk(
        self,
        obj: Any,
        facts: dict[FactKey, Any],
        current_entity: Optional[str],
    ) -> None:
        if isinstance(obj, dict):
            entity = self._record_identity(obj) or current_entity
            skip_keys = self._grouping_keys_of(obj)
            for key, value in obj.items():
                if str(key).casefold() in skip_keys:
                    continue
                if isinstance(value, (dict, list)):
                    self._walk(value, facts, entity)
                elif value is not None:
                    facts[(entity, str(key))] = value
            return
        if isinstance(obj, list):
            for element in obj:
                self._walk(element, facts, current_entity)

    @staticmethod
    def _record_identity(record: dict[str, Any]) -> Optional[str]:
        """Primary: vendor/entity/org. Secondary: category, only if no primary."""
        for key, value in record.items():
            if str(key).casefold() in identity_keys() and isinstance(value, str):
                ident = normalize_entity_key(value)
                if ident:
                    return ident
        for key, value in record.items():
            if str(key).casefold() in category_keys() and isinstance(value, str):
                ident = normalize_entity_key(value)
                if ident:
                    return ident
        return None

    @staticmethod
    def _grouping_keys_of(record: dict[str, Any]) -> set[str]:
        """Do not compare the identity/grouping field against itself."""
        skipped: set[str] = set()
        for key, value in record.items():
            folded = str(key).casefold()
            if folded in identity_keys() and isinstance(value, str) and value.strip():
                skipped.add(folded)
        if skipped:
            return skipped
        for key, value in record.items():
            folded = str(key).casefold()
            if folded in category_keys() and isinstance(value, str) and value.strip():
                skipped.add(folded)
        return skipped

    def values_conflict(self, old_val: Any, new_val: Any) -> bool:
        if old_val == new_val:
            return False
        if old_val is None or new_val is None:
            return False
        if isinstance(old_val, bool) or isinstance(new_val, bool):
            return old_val != new_val
        if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
            return float(old_val) != float(new_val)
        if _both_enum(old_val, new_val):
            return str(old_val).strip().casefold() != str(new_val).strip().casefold()
        return self._text.is_conflict(str(old_val), str(new_val))


def _both_enum(old_val: Any, new_val: Any) -> bool:
    old_s = str(old_val).strip().casefold()
    new_s = str(new_val).strip().casefold()
    return old_s in _ENUM_VALUES and new_s in _ENUM_VALUES
