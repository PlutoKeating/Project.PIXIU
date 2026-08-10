"""版本向量与确定性 LWW-Element-Set。"""

from __future__ import annotations

from enum import Enum

from backend.foundation.core.models import SyncOp

from .models import SyncRecord


class ClockRelation(str, Enum):
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    EQUAL = "EQUAL"
    CONCURRENT = "CONCURRENT"


def compare_clocks(left: dict[str, int], right: dict[str, int]) -> ClockRelation:
    keys = set(left) | set(right)
    left_greater = any(left.get(key, 0) > right.get(key, 0) for key in keys)
    right_greater = any(left.get(key, 0) < right.get(key, 0) for key in keys)
    if left_greater and right_greater:
        return ClockRelation.CONCURRENT
    if left_greater:
        return ClockRelation.AFTER
    if right_greater:
        return ClockRelation.BEFORE
    return ClockRelation.EQUAL


def merge_clocks(*clocks: dict[str, int]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for clock in clocks:
        for device_id, counter in clock.items():
            if counter < 0:
                raise ValueError("vector clock counters must be non-negative")
            merged[device_id] = max(merged.get(device_id, 0), counter)
    return merged


def increment_clock(clock: dict[str, int], device_id: str) -> dict[str, int]:
    if not device_id:
        raise ValueError("device_id must not be empty")
    result = merge_clocks(clock)
    result[device_id] = result.get(device_id, 0) + 1
    return result


def record_from_op(op: SyncOp) -> SyncRecord:
    value = op.payload.get("value") or {}
    if not isinstance(value, dict):
        raise ValueError("sync operation value must be an object")
    return SyncRecord(
        entity=op.entity,
        payload=dict(value),
        vclock=dict(op.vclock),
        ts=op.ts,
        op_id=op.op_id,
        tombstone=bool(op.payload.get("deleted", False)),
    )


class LWWElementSet:
    """因果关系优先；并发或相同时按 (ts, op_id) 确定性决胜。"""

    @staticmethod
    def resolve(current: SyncRecord | None, incoming: SyncOp) -> SyncRecord:
        candidate = record_from_op(incoming)
        if current is None:
            return candidate
        relation = compare_clocks(candidate.vclock, current.vclock)
        if relation == ClockRelation.AFTER:
            winner = candidate
        elif relation == ClockRelation.BEFORE:
            winner = current
        elif (candidate.ts, candidate.op_id) > (current.ts, current.op_id):
            winner = candidate
        else:
            winner = current
        # 内容采用 LWW 胜者，但因果上下文必须吸收所有已见分支。
        return winner.model_copy(
            update={"vclock": merge_clocks(current.vclock, candidate.vclock)}
        )
