"""main 主干语义：快进检测 + 分叉转人工仲裁。

置于 CRDT 之上：op 级合并仍由 LWWElementSet 完成；本模块判定
「远程 op 集相对本地 main 是快进还是分叉」——快进自动吸收，
并发矛盾经 ConflictService 仲裁，MANUAL 拦截等待人工裁决。

知识模型转换钩子：arbitrate 的签名是 ``(new_item: KnowledgeItem)``，
而 mainline 收到的是 SyncOp，因此构造时通过 ``knowledge_factory``
把 op.payload 物化为 KnowledgeItem（默认实现见 ``default_knowledge_from_op``）；
仅 knowledge 实体参与仲裁，evidence/preference 由 LWW 确定性收敛。
"""

from __future__ import annotations

from backend.foundation.core.models import (
    ConflictResolution,
    KnowledgeItem,
    SyncOp,
)

from .crdt import ClockRelation, compare_clocks, merge_clocks


def default_knowledge_from_op(op: SyncOp) -> KnowledgeItem | None:
    """把知识类同步 op 的 payload 值转换为 KnowledgeItem。

    仅 ``knowledge:<id>`` 实体参与冲突仲裁；evidence/preference 实体由
    LWW 确定性收敛，返回 None 表示无需仲裁。
    """
    kind, separator, _ = op.entity.partition(":")
    if not separator or kind != "knowledge":
        return None
    value = op.payload.get("value")
    if not isinstance(value, dict):
        return None
    return KnowledgeItem.model_validate(value)


class Mainline:
    """维护本地 main 版本向量，判定远端 op 可吸收性。

    - 快进（BEFORE/EQUAL/AFTER）：相对本地 main 是祖先或后继 → 吸收，
      并把本地 main 时钟 merge 推进（吸收所有已见分支）。
    - 并发矛盾：交 ``conflict_service.arbitrate(item, source="sync")``；
      MANUAL → 拦截（不返回、本地 main 不变、等待人工裁决），
      NEW_WINS/MERGE → 自动吸收（Arbiter 内部已处理知识层）。
    """

    def __init__(self, store, conflict_service, *, knowledge_factory=None) -> None:
        self._store = store
        self._conflict_service = conflict_service
        self._knowledge_factory = knowledge_factory or default_knowledge_from_op

    async def _local_main_clock(self, entity: str) -> dict[str, int]:
        state = await self._store.get_state(entity)
        if state is None or getattr(state, "vclock", None) is None:
            return {}
        return dict(state.vclock)

    async def try_fast_forward(self, operations: list[SyncOp]) -> list[SyncOp]:
        """返回可安全吸收（快进或自动裁决通过）的 op 列表。

        分叉且 Arbiter 判 MANUAL 的 op 被拦截：生成 ConflictRecord（source="sync"）
        并从返回列表剔除，本地 main 保持不变，等待人工裁决。
        """
        if not operations:
            return []
        absorbed: list[SyncOp] = []
        # 按 entity 分组：main 时钟以实体为粒度推进，组内保持 op 顺序
        by_entity: dict[str, list[SyncOp]] = {}
        for op in operations:
            by_entity.setdefault(op.entity, []).append(op)

        for entity, group in by_entity.items():
            local_clock = await self._local_main_clock(entity)
            for op in group:
                relation = compare_clocks(local_clock, op.vclock)
                if relation in (ClockRelation.BEFORE, ClockRelation.EQUAL):
                    absorbed.append(op)
                    local_clock = merge_clocks(local_clock, op.vclock)
                    continue
                if relation == ClockRelation.AFTER:
                    # 远程落后于本地（已在本地或过期 op）——吸收（去重由 caller 负责）
                    absorbed.append(op)
                    continue
                # CONCURRENT → 语义仲裁
                item = self._knowledge_factory(op)
                if item is not None:
                    record = await self._conflict_service.arbitrate(
                        item, source="sync"
                    )
                    if (
                        record is not None
                        and record.resolution == ConflictResolution.MANUAL
                    ):
                        # 拦截：分叉转人工，本地 main 不变，等待人工裁决
                        continue
                absorbed.append(op)
                local_clock = merge_clocks(local_clock, op.vclock)
        return absorbed


__all__ = ["Mainline", "default_knowledge_from_op"]
