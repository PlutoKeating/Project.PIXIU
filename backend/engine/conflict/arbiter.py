"""Arbiter —— 冲突检测 + 裁决策略选择。

当前支持三种裁决：
- NEW_WINS：同一实例字段发生明确矛盾，以新知识为准。
- MERGE：  新旧知识共享同一实体且无矛盾，新知识扩展旧知识。
- MANUAL：存在明确矛盾但标有“需人工确认”，或矛盾双方均具权威性无法自动取舍。
"""

from __future__ import annotations

import time
from typing import Any, Optional

from backend.foundation.core.idgen import gen_conflict_id
from backend.foundation.core.models import (
    ConflictRecord,
    ConflictResolution,
    KnowledgeItem,
    conflict_severity_for,
)

from .entity_matcher import EntityMatcher
from .field_matcher import FieldConflict, FieldMatcher
from .text_detector import RuleBasedTextConflictDetector, TextConflictDetector

# 触发人工裁决的文本标记（出现在 title/body 任意字符串值中）。
_MANUAL_MARKERS = (
    "人工确认",
    "待确认",
    "需人工",
    "手动仲裁",
    "manual review",
    "needs manual",
)


class Arbiter:
    """冲突检测与裁决策略选择器。"""

    def __init__(
        self,
        entity_matcher: Optional[EntityMatcher] = None,
        field_matcher: Optional[FieldMatcher] = None,
        text_detector: Optional[TextConflictDetector] = None,
    ) -> None:
        self._entity_matcher = entity_matcher or EntityMatcher()
        self._field = field_matcher or FieldMatcher(
            text_detector=text_detector or RuleBasedTextConflictDetector()
        )

    async def is_candidate(self, new_item: KnowledgeItem, existing: KnowledgeItem) -> bool:
        return await self._entity_matcher.matches(new_item, existing)

    def detect(
        self,
        new_item: KnowledgeItem,
        existing: KnowledgeItem,
    ) -> Optional[ConflictRecord]:
        """检测冲突并选择裁决策略；无冲突返回 None。"""
        field_conflict = self._field.find_conflict(existing, new_item)

        if field_conflict is not None:
            if self._has_manual_marker(existing, new_item):
                return self._record(existing, new_item, field_conflict, ConflictResolution.MANUAL)
            return self._record(existing, new_item, field_conflict, ConflictResolution.NEW_WINS)

        # 无字段冲突时，检查是否是互补扩展（MERGE）。
        if self._is_merge_extension(existing, new_item):
            return self._record(
                existing,
                new_item,
                FieldConflict(field="merge", old_value=None, new_value=None),
                ConflictResolution.MERGE,
            )

        return None

    def _has_manual_marker(self, *items: KnowledgeItem) -> bool:
        for item in items:
            text = f"{item.title} {_flatten_text(item.body)}"
            lowered = text.casefold()
            for marker in _MANUAL_MARKERS:
                if marker.casefold() in lowered:
                    return True
        return False

    def _is_merge_extension(self, existing: KnowledgeItem, new_item: KnowledgeItem) -> bool:
        """新旧知识无字段冲突，且在同一实体上共享部分事实、新知识又带来新事实 -> 可合并。"""
        old_facts = self._field.extract_facts(existing)
        new_facts = self._field.extract_facts(new_item)
        if not old_facts or not new_facts:
            return False
        shared_keys = set(old_facts) & set(new_facts)
        if not shared_keys:
            return False
        # 共享事实的值必须相同（无冲突已由调用方保证，再确认一次）。
        for key in shared_keys:
            if self._field.values_conflict(old_facts[key], new_facts[key]):
                return False
        return bool(set(new_facts) ^ set(old_facts))

    def _record(
        self,
        existing: KnowledgeItem,
        new_item: KnowledgeItem,
        conflict: FieldConflict,
        resolution: ConflictResolution,
    ) -> ConflictRecord:
        return ConflictRecord(
            id=gen_conflict_id(),
            target_knowledge=existing.id,
            field=conflict.field,
            old_value=conflict.old_value,
            new_value=conflict.new_value,
            resolution=resolution,
            severity=conflict_severity_for(resolution),
            created_at=int(time.time()),
        )


def _flatten_text(obj: Any) -> str:
    """把 body 里的所有字符串值拼接，用于标记检测。"""
    parts: list[str] = []
    if isinstance(obj, str):
        parts.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            parts.append(_flatten_text(value))
    elif isinstance(obj, list):
        for value in obj:
            parts.append(_flatten_text(value))
    return " ".join(parts)
