"""三层记忆流转：短/中期上下文、长期知识沉淀与可逆降级。"""

from __future__ import annotations

import time
from typing import Any

from backend.foundation.core.idgen import gen_context_id
from backend.foundation.core.models import KnowledgeStatus
from backend.foundation.core.repository import KnowledgeRepository

from .models import ContextStatus, MemoryContext, MemoryTier
from .promoter import (
    FlowContextNotFound,
    InvalidFlowTransition,
    Promoter,
    PromotionHandler,
)
from .store import FlowStore, SqliteFlowStore
from .ttl import TTLManager, ttl_for


class KnowledgeNotFound(LookupError):
    """长期知识不存在、不属于 scope，或已经失效。"""


class FlowService:
    """Module C 的三层记忆生命周期门面。"""

    def __init__(
        self,
        store: FlowStore,
        promotion_handler: PromotionHandler,
        knowledge_repo: KnowledgeRepository | None = None,
    ) -> None:
        self._store = store
        self._promoter = Promoter(store, promotion_handler)
        self._ttl = TTLManager(store)
        self._knowledge_repo = knowledge_repo

    async def remember(
        self,
        tier: MemoryTier,
        payload: dict[str, Any],
        scope: str,
        *,
        ttl_seconds: int | None = None,
        context_id: str | None = None,
        now: int | None = None,
    ) -> MemoryContext:
        timestamp = int(time.time()) if now is None else now
        effective_ttl = ttl_for(tier) if ttl_seconds is None else ttl_seconds
        if effective_ttl <= 0:
            raise ValueError("ttl_seconds must be positive")
        context = MemoryContext(
            id=context_id or gen_context_id(),
            tier=tier,
            payload=payload,
            scope=scope,
            created_at=timestamp,
            updated_at=timestamp,
            expires_at=timestamp + effective_ttl,
        )
        await self._store.save(context)
        return context

    async def promote(
        self,
        source: MemoryTier,
        context_ids: list[str],
        scope: str,
        *,
        now: int | None = None,
    ) -> list[str]:
        return await self._promoter.promote(
            source, context_ids, scope, now=now
        )

    async def demote(
        self,
        knowledge_id: str,
        target: MemoryTier,
        scope: str,
        *,
        ttl_seconds: int | None = None,
        now: int | None = None,
    ) -> MemoryContext:
        if self._knowledge_repo is None:
            raise RuntimeError("demote requires a knowledge repository")
        item = await self._knowledge_repo.get(knowledge_id)
        if (
            item is None
            or item.scope != scope
            or item.status != KnowledgeStatus.ACTIVE
        ):
            raise KnowledgeNotFound(knowledge_id)
        payload = {
            "source_type": "MANUAL_CONFIG",
            "raw": {
                "title": item.title,
                "body": item.body,
                "kind": item.kind.value,
                "source_knowledge": item.id,
                "evidence_ids": list(item.evidence_ids),
            },
        }
        return await self.remember(
            target,
            payload,
            scope,
            ttl_seconds=ttl_seconds,
            now=now,
        )

    async def sweep_expired(self, *, now: int | None = None) -> list[str]:
        return await self._ttl.sweep(now=now)


__all__ = [
    "ContextStatus",
    "FlowContextNotFound",
    "FlowService",
    "FlowStore",
    "InvalidFlowTransition",
    "KnowledgeNotFound",
    "MemoryContext",
    "MemoryTier",
    "SqliteFlowStore",
]
