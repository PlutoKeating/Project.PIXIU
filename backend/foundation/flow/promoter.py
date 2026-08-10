"""短/中期上下文沉淀到长期知识的状态机。"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from .models import ContextStatus, MemoryContext, MemoryTier
from .store import FlowStore

PromotionHandler = Callable[[MemoryContext], Awaitable[str]]


class FlowContextNotFound(LookupError):
    """上下文不存在，或不属于请求 scope。"""


class InvalidFlowTransition(ValueError):
    """上下文当前状态不允许执行请求的流转。"""


class Promoter:
    """校验并执行上下文沉淀；业务结构化由注入的 handler 完成。"""

    def __init__(self, store: FlowStore, handler: PromotionHandler) -> None:
        self._store = store
        self._handler = handler

    async def promote(
        self,
        source: MemoryTier,
        context_ids: list[str],
        scope: str,
        *,
        now: int | None = None,
    ) -> list[str]:
        ordered_ids = list(dict.fromkeys(context_ids))
        if not ordered_ids:
            raise InvalidFlowTransition("context_ids must not be empty")

        contexts = await self._store.get_many(ordered_ids)
        by_id = {context.id: context for context in contexts}

        # 先整体校验，避免批量请求在中途失败时留下部分业务副作用。
        for context_id in ordered_ids:
            context = by_id.get(context_id)
            if context is None or context.scope != scope:
                raise FlowContextNotFound(context_id)
            if context.tier != source:
                raise InvalidFlowTransition(
                    f"context {context_id} belongs to {context.tier.value}, not {source.value}"
                )
            if context.status not in (ContextStatus.ACTIVE, ContextStatus.PROMOTED):
                raise InvalidFlowTransition(
                    f"context {context_id} cannot be promoted from {context.status.value}"
                )

        timestamp = int(time.time()) if now is None else now
        knowledge_ids: list[str] = []
        for context_id in ordered_ids:
            context = by_id[context_id]
            if context.status == ContextStatus.PROMOTED:
                # 模型已保证 PROMOTED 必有 knowledge_id。
                knowledge_ids.append(context.knowledge_id or "")
                continue
            knowledge_id = await self._handler(context)
            if not knowledge_id:
                raise InvalidFlowTransition(
                    f"promotion handler returned no knowledge id for {context_id}"
                )
            await self._store.mark_promoted(context_id, knowledge_id, timestamp)
            knowledge_ids.append(knowledge_id)
        return knowledge_ids
