"""main 主干语义：快进检测 + 分叉转人工仲裁。

置于 CRDT 之上：op 级合并仍由 LWWElementSet 完成；本模块判定
「远程 op 集相对本地 main 是快进还是分叉」——快进自动吸收，
并发矛盾经 ConflictService 仲裁，MANUAL 拦截等待人工裁决。

知识模型转换钩子：arbitrate 的签名是 ``(new_item: KnowledgeItem)``，
而 mainline 收到的是 SyncOp，因此构造时通过 ``knowledge_factory``
把 op.payload 物化为 KnowledgeItem（默认实现见 ``default_knowledge_from_op``）；
仅 knowledge 实体参与仲裁，evidence/preference 由 LWW 确定性收敛。

MANUAL 拦截的粘性（SN-3 质量审查 I-3）：拦截时在 sync_meta 持久化
``sync_blocked:{entity}`` 标记（value = 触发拦截的 op_id），此后该实体
的并发 op 直接拦截、不重新 arbitrate——避免重试重仲裁产生重复
ConflictRecord。标记在人工裁决落地（ConflictRecord 裁决端点）前永存，
重试保持拦截是安全方向。
"""

from __future__ import annotations

from typing import NamedTuple

from pydantic import ValidationError

from backend.foundation.core.models import (
    ConflictResolution,
    KnowledgeItem,
    SyncOp,
)

from .crdt import ClockRelation, compare_clocks, merge_clocks

#: MANUAL 拦截的粘性标记 key 前缀（sync_meta）。value = 触发拦截的 op_id。
#: 人工裁决落地时清除；落地前该实体并发 op 一律粘性拦截。
BLOCKED_KEY_PREFIX = "sync_blocked:"


def blocked_key(entity: str) -> str:
    """构造 MANUAL 拦截标记的 sync_meta key。"""
    return f"{BLOCKED_KEY_PREFIX}{entity}"


def default_knowledge_from_op(op: SyncOp) -> KnowledgeItem | None:
    """把知识类同步 op 的 payload 值转换为 KnowledgeItem。

    仅 ``knowledge:<id>`` 实体参与冲突仲裁；evidence/preference 实体由
    LWW 确定性收敛，返回 None 表示无需仲裁。空 entity id（``knowledge:``）
    同样返回 None——materializer 对空 id 直接 return，仲裁侧保持一致语义。
    """
    kind, separator, entity_id = op.entity.partition(":")
    if not separator or kind != "knowledge" or not entity_id:
        return None
    value = op.payload.get("value")
    if not isinstance(value, dict):
        return None
    try:
        return KnowledgeItem.model_validate(value)
    except ValidationError as exc:
        # 与 receive_ops 其余校验统一抛 InvalidSyncOperation（I-2），
        # 避免裸 pydantic ValidationError 穿出破坏「整批零吸收」的契约。
        # 惰性导入规避 sync/__init__.py ↔ mainline.py 的循环依赖。
        from . import InvalidSyncOperation

        raise InvalidSyncOperation(f"malformed knowledge payload: {exc}") from exc


class FastForwardResult(NamedTuple):
    """try_fast_forward 的返回值。

    absorbed — 可安全吸收（快进或自动裁决通过）的 op 列表；
    arbitrated_op_ids — 已经 ConflictService.arbitrate 落库（NEW_WINS/MERGE）
    的 op id 集合。仲裁产物（merge 合并体 / 抬升后的 version）已是 knowledge
    repo 的最终事实，receive_ops 对这些 op 跳过 materializer 重复落库（I-1），
    避免合并体被原始 CRDT payload 覆盖、版本抬升被抹平。
    """

    absorbed: list[SyncOp]
    arbitrated_op_ids: frozenset[str]


class Mainline:
    """维护本地 main 版本向量，判定远端 op 可吸收性。

    - 快进（BEFORE/EQUAL/AFTER）：相对本地 main 是祖先或后继 → 吸收，
      并把本地 main 时钟 merge 推进（吸收所有已见分支）。
    - 并发矛盾：交 ``conflict_service.arbitrate(item, source="sync")``；
      MANUAL → 拦截（不返回、本地 main 不变、等待人工裁决）并持久化
      ``sync_blocked:{entity}`` 标记（此后并发 op 粘性拦截，不重新仲裁）；
      NEW_WINS/MERGE → 自动吸收（Arbiter 内部已处理知识层，返回的 op_id
      记入 arbitrated_op_ids，caller 跳过 materializer 重复落库）。
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

    async def try_fast_forward(self, operations: list[SyncOp]) -> FastForwardResult:
        """返回可安全吸收的 op 列表 + 已仲裁 op id 集合。

        分叉且 Arbiter 判 MANUAL 的 op 被拦截：生成 ConflictRecord（source="sync"）、
        持久化 blocked 标记并从返回列表剔除，本地 main 保持不变，等待人工裁决。
        已 blocked 实体的并发 op 直接拦截（不重新 arbitrate，不新增 ConflictRecord）。
        """
        if not operations:
            return FastForwardResult([], frozenset())
        absorbed: list[SyncOp] = []
        arbitrated: set[str] = set()
        # 按 entity 分组：main 时钟以实体为粒度推进，组内保持 op 顺序
        by_entity: dict[str, list[SyncOp]] = {}
        for op in operations:
            by_entity.setdefault(op.entity, []).append(op)

        for entity, group in by_entity.items():
            local_clock = await self._local_main_clock(entity)
            blocked_op_id = await self._store.get_meta(blocked_key(entity))
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
                if blocked_op_id is not None:
                    # 该实体已有 MANUAL 分叉待人工裁决：并发 op 直接拦截，
                    # 不重新 arbitrate（避免重试/新并发 op 产生重复 ConflictRecord）。
                    continue
                item = self._knowledge_factory(op)
                if item is not None:
                    record = await self._conflict_service.arbitrate(
                        item, source="sync"
                    )
                    if (
                        record is not None
                        and record.resolution == ConflictResolution.MANUAL
                    ):
                        # 拦截：分叉转人工，本地 main 不变，等待人工裁决。
                        # 持久化 blocked 标记使后续（含跨轮重试）并发 op 粘性拦截。
                        blocked_op_id = op.op_id
                        await self._store.set_meta(blocked_key(entity), op.op_id)
                        continue
                    if record is not None:
                        arbitrated.add(op.op_id)
                absorbed.append(op)
                local_clock = merge_clocks(local_clock, op.vclock)
        return FastForwardResult(absorbed, frozenset(arbitrated))


__all__ = ["Mainline", "FastForwardResult", "default_knowledge_from_op"]
