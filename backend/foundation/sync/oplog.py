"""同步操作日志（oplog）门面。

oplog 的持久化实现位于 ``SqliteSyncStore``（表 ``sync_oplog`` + ``sync_peer_acks``）；
本模块按任务清单要求提供独立的高层接口，并补充反熵对账所需的缺失集视图。
"""

from __future__ import annotations

from backend.foundation.core.models import SyncOp


class SyncOplog:
    """本地修改自动写入、按 peer 追踪送达、反熵缺失集计算。"""

    def __init__(self, store) -> None:
        self._store = store

    async def append(self, op: SyncOp) -> bool:
        """追加一条 op 到日志（幂等：已存在返回 False）。"""
        return await self._store.append_op(op)

    async def get(self, op_id: str) -> SyncOp | None:
        """按 op_id 查询单条 op。"""
        return await self._store.get_op(op_id)

    async def ids(self) -> set[str]:
        """全部 op_id（反熵 digest 输入）。"""
        return await self._store.op_ids()

    async def list(self) -> list[SyncOp]:
        """按 (ts, op_id) 升序列出全部 op。"""
        return await self._store.list_ops()

    async def pending_for_peer(self, peer_id: str) -> int:
        """指定 peer 尚未确认送达的 op 数量。"""
        return await self._store.pending_for_peer(peer_id)

    async def pending_ops_for_peer(self, peer_id: str) -> list[SyncOp]:
        """指定 peer 尚未确认送达的 op 列表。"""
        return await self._store.pending_ops_for_peer(peer_id)

    async def acknowledge(self, peer_id: str, op_ids: list[str], now: int) -> int:
        """记录 peer 已确认的 op，返回本次新增确认数。"""
        return await self._store.acknowledge(peer_id, op_ids, now)

    async def delta_for(self, remote_op_ids: set[str]) -> list[SyncOp]:
        """计算对端缺失的 op 集（digest 反熵对账用）。"""
        return [
            op for op in await self._store.list_ops() if op.op_id not in remote_op_ids
        ]
