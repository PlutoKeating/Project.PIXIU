"""conflict/ —— 冲突仲裁。

对外暴露 ConflictService。公开构造参数保持向后兼容：
``ConflictService(knw_repo, conflict_repo, arbiter=None)``。

``entity_repo`` 为可选注入。foundation 契约没有按 knowledge id 反查实体的
接口，KnowledgeItem.entities 存的是名称；不注入时用名称/identity 字段匹配。

裁决策略：
- NEW_WINS：新知识取代旧知识。
- MERGE：  合并新旧知识，生成一条新知识取代旧知识。
- MANUAL：保留两条知识 ACTIVE，记录待人工裁决。
"""

from __future__ import annotations

import copy
import time
from collections.abc import Awaitable, Callable
from typing import Optional

from backend.foundation.core.models import ConflictRecord, ConflictResolution, KnowledgeItem
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
        knowledge_writer: Callable[
            [KnowledgeItem], Awaitable[KnowledgeItem]
        ] | None = None,
    ) -> None:
        self._knw_repo = knw_repo
        self._conflict_repo = conflict_repo
        self._entity_repo = entity_repo
        detector = text_detector or RuleBasedTextConflictDetector()
        self._arbiter = arbiter or Arbiter(text_detector=detector)
        self._entity_matcher = entity_matcher or EntityMatcher(entity_repo=entity_repo)
        self._knowledge_writer = knowledge_writer

    async def _save(self, item: KnowledgeItem) -> None:
        if self._knowledge_writer is None:
            await self._knw_repo.save(item)
        else:
            await self._knowledge_writer(item)

    async def arbitrate(
        self,
        new_item: KnowledgeItem,
        *,
        source: str = "write",
    ) -> Optional[ConflictRecord]:
        """Detect contradiction with ACTIVE knowledge; apply chosen resolution.

        source — 冲突来源标记：本地写入默认 "write"，同步分叉（SN-3 mainline
        try_fast_forward 触发）置 "sync"，随 ConflictRecord 持久化。
        """
        candidates = await self._knw_repo.list_active()
        for existing in candidates:
            if not await self._is_candidate(new_item, existing):
                continue
            winner = new_item
            loser = existing
            if source == "sync" and _sync_precedence(existing) > _sync_precedence(
                new_item
            ):
                winner = existing
                loser = new_item
            record = self._arbiter.detect(winner, loser)
            if record is None:
                continue
            if source != "write":
                record.source = source
                record.created_at = winner.updated_at
            resolved_at = (
                winner.updated_at if source == "sync" else int(time.time())
            )
            await self._apply_resolution(
                loser, winner, record, resolved_at=resolved_at
            )
            return record

        await self._save(new_item)
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

    async def _apply_resolution(
        self,
        existing: KnowledgeItem,
        new_item: KnowledgeItem,
        record: ConflictRecord,
        *,
        resolved_at: int,
    ) -> None:
        resolution = record.resolution
        if resolution == ConflictResolution.MERGE:
            await self._apply_merge(
                existing, new_item, record, resolved_at=resolved_at
            )
        elif resolution == ConflictResolution.MANUAL:
            await self._apply_manual(
                existing, new_item, record, resolved_at=resolved_at
            )
        else:
            await self._apply_new_wins(
                existing, new_item, record, resolved_at=resolved_at
            )

    async def _apply_new_wins(
        self,
        existing: KnowledgeItem,
        new_item: KnowledgeItem,
        record: ConflictRecord,
        *,
        resolved_at: int,
    ) -> None:
        existing.status = "SUPERSEDED"
        existing.updated_at = resolved_at
        await self._save(existing)

        new_item.version = max(existing.version + 1, new_item.version)
        new_item.updated_at = resolved_at
        await self._save(new_item)

        await self._conflict_repo.save(record)

    async def _apply_manual(
        self,
        existing: KnowledgeItem,
        new_item: KnowledgeItem,
        record: ConflictRecord,
        *,
        resolved_at: int,
    ) -> None:
        # 保留两条知识 ACTIVE，让人工后续裁决。
        await self._save(existing)
        new_item.version = max(existing.version + 1, new_item.version)
        new_item.updated_at = resolved_at
        await self._save(new_item)
        await self._conflict_repo.save(record)

    async def _apply_merge(
        self,
        existing: KnowledgeItem,
        new_item: KnowledgeItem,
        record: ConflictRecord,
        *,
        resolved_at: int,
    ) -> None:
        merged = copy.deepcopy(existing)
        merged.id = new_item.id  # 复用新知识的 id，避免额外 id 空间
        merged.body = _merge_bodies(existing.body, new_item.body)
        merged.version = max(existing.version + 1, new_item.version)
        merged.updated_at = resolved_at
        merged.evidence_ids = list(
            sorted(set(merged.evidence_ids or []) | set(new_item.evidence_ids or []))
        )

        existing.status = "SUPERSEDED"
        existing.updated_at = resolved_at
        await self._save(existing)
        await self._save(merged)
        await self._conflict_repo.save(record)


def _merge_bodies(old: object, new: object) -> object:
    """浅合并两条知识的 body。

    - dict 层级：新值覆盖旧值；如果旧值或新值是 dict/list 则递归合并。
    - list：把 new 中不存在的元素追加到 old 列表后（按 dict 元素的 vendor/category 去重）。
    - 标量：new 优先。
    """
    if isinstance(old, dict) and isinstance(new, dict):
        merged: dict[str, object] = {}
        keys = set(old) | set(new)
        for key in keys:
            if key in old and key in new:
                merged[key] = _merge_bodies(old[key], new[key])
            elif key in new:
                merged[key] = copy.deepcopy(new[key])
            else:
                merged[key] = copy.deepcopy(old[key])
        return merged
    if isinstance(old, list) and isinstance(new, list):
        merged_list: list[object] = []
        seen: set[str] = set()
        for element in old:
            merged_list.append(element)
            seen.add(_item_signature(element))
        for element in new:
            sig = _item_signature(element)
            if sig not in seen:
                merged_list.append(element)
                seen.add(sig)
        return merged_list
    # 标量冲突：新知识优先（与 NEW_WINS 一致，但 MERGE 场景下不应出现标量冲突）。
    return copy.deepcopy(new)


def _item_signature(element: object) -> str:
    if isinstance(element, dict):
        # 用 vendor/category/amount 三元组做去重签名；缺省时用整个 dict。
        vendor = str(element.get("vendor", "")).strip()
        category = str(element.get("category", "")).strip()
        amount = element.get("amount")
        if vendor or category or amount is not None:
            return f"vendor={vendor}|category={category}|amount={amount}"
    return str(element)


def _sync_precedence(item: KnowledgeItem) -> tuple[int, int, str]:
    """Total order used only for peer-to-peer semantic conflict resolution."""
    return item.updated_at, item.created_at, item.id
