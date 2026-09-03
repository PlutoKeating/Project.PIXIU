"""Phase 4 完成标准验证：多节点收敛、断网重连、丢包恢复、revoke 拒绝。

覆盖任务清单中此前缺失的验收点：
- 两/三节点模拟最终收敛
- 乱序、重复、丢包、断网重连
- revoke 后无法继续接收
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.sync import (
    InvalidSyncOperation,
    PairingMethod,
    SqliteSyncStore,
    SyncService,
)
from backend.foundation.sync.anti_entropy import AntiEntropy
from backend.foundation.sync.gc import TombstoneGC

NOW = 2_000_000_000
PASSPHRASE = "phase4-convergence-test-passphrase"
DOMAIN = "shared:home"


async def _node(root: Path, filename: str, name: str):
    db_path = str(root / filename)
    sync_db = sqlite3.connect(db_path)
    init_db_on_connection(sync_db)
    sync_db.close()
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    store = SqliteSyncStore(db)
    service = SyncService(
        store,
        device_name=name,
        domain=DOMAIN,
        key_passphrase=PASSPHRASE,
    )
    return service, store, db


async def _pair(a: SyncService, b: SyncService) -> None:
    """双向配对 a 与 b。"""
    token_b = await b.create_pairing_token(PairingMethod.QR, now=NOW)
    await a.pair(PairingMethod.QR, token_b, now=NOW)
    token_a = await a.create_pairing_token(PairingMethod.QR, now=NOW)
    await b.pair(PairingMethod.QR, token_a, now=NOW)


async def _record(service: SyncService, entity: str, value: dict) -> None:
    await service.record_local(entity, value, DOMAIN, now=NOW)


async def _state_of(service: SyncService, entity: str) -> dict:
    return await service._store.get_state(entity)


@pytest_asyncio.fixture
async def three_nodes(tmp_path: Path):
    a = await _node(tmp_path, "a.db", "书房工作站")
    b = await _node(tmp_path, "b.db", "客厅一体机")
    c = await _node(tmp_path, "c.db", "随身笔记本")
    yield a, b, c
    for _, _, db in (a, b, c):
        await db.close()


# ═══════════════════════════════════════════════════════
# 三节点收敛：A 产生 → A→B 传播 → B→C 两跳，最终三方一致
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_three_node_convergence_via_two_hops(three_nodes):
    a, b, c = [n[0] for n in three_nodes]
    await _pair(a, b)
    await _pair(b, c)
    await _pair(a, c)

    await _record(a, "knw:monthly-budget", {"amount": 434.5, "title": "4月预算"})
    ops_a = await a._store.list_ops()
    assert await b.receive_ops(ops_a) == 1  # A → B

    ops_b = await b._store.list_ops()
    assert await c.receive_ops(ops_b) == 1  # B → C（两跳）

    state_a = await _state_of(a, "knw:monthly-budget")
    state_b = await _state_of(b, "knw:monthly-budget")
    state_c = await _state_of(c, "knw:monthly-budget")
    assert state_a.payload == state_b.payload == state_c.payload == {
        "amount": 434.5,
        "title": "4月预算",
    }


@pytest.mark.asyncio
async def test_three_node_concurrent_updates_converge(three_nodes):
    """三节点各自并发写不同实体，全量交换后状态一致。"""
    a, b, c = [n[0] for n in three_nodes]
    await _pair(a, b)
    await _pair(b, c)
    await _pair(a, c)

    await _record(a, "knw:entity-x", {"from": "a"})
    await _record(b, "knw:entity-x", {"from": "b"})
    await _record(c, "knw:entity-x", {"from": "c"})

    all_ops = await a._store.list_ops()
    await b.receive_ops(all_ops)
    await c.receive_ops(all_ops)
    all_ops = await c._store.list_ops()
    await a.receive_ops(all_ops)
    await b.receive_ops(all_ops)

    pa = (await _state_of(a, "knw:entity-x")).payload
    pb = (await _state_of(b, "knw:entity-x")).payload
    pc = (await _state_of(c, "knw:entity-x")).payload
    assert pa == pb == pc  # 三方收敛到同一胜者


# ═══════════════════════════════════════════════════════
# 断网重连：离线积累 oplog → 重连后反熵补齐
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_offline_accumulation_recovered_by_anti_entropy(three_nodes):
    a, b, _ = [n[0] for n in three_nodes]
    await _pair(a, b)

    # A 离线期间积累 3 条本地修改（未发给 B）
    await _record(a, "knw:offline-1", {"v": 1})
    await _record(a, "knw:offline-2", {"v": 2})
    await _record(a, "knw:offline-3", {"v": 3})

    # 重连：B 出 summary，A 算 delta 补齐（apply_remote 在此场景不使用）
    b_summary = await AntiEntropy(b._store, None).summary()
    delta = await AntiEntropy(a._store, None).delta_for(set(b_summary["op_ids"]))
    assert len(delta) == 3
    assert await b.receive_ops(delta) == 3

    for entity in ("knw:offline-1", "knw:offline-2", "knw:offline-3"):
        state_b = await _state_of(b, entity)
        state_a = await _state_of(a, entity)
        assert state_a.payload == state_b.payload


# ═══════════════════════════════════════════════════════
# 丢包恢复：部分送达失败 → 重发补齐且幂等
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_dropped_ops_recovered_idempotently(three_nodes):
    a, b, _ = [n[0] for n in three_nodes]
    await _pair(a, b)

    await _record(a, "knw:drop-1", {"v": 1})
    await _record(a, "knw:drop-2", {"v": 2})
    await _record(a, "knw:drop-3", {"v": 3})

    all_ops = await a._store.list_ops()
    # 模拟丢包：只成功送达 1 条
    assert await b.receive_ops(all_ops[:1]) == 1
    # 重传全部：已接收的幂等跳过，只补 2 条
    assert await b.receive_ops(all_ops) == 2

    assert (await _state_of(b, "knw:drop-1")).payload == {"v": 1}
    assert (await _state_of(b, "knw:drop-2")).payload == {"v": 2}
    assert (await _state_of(b, "knw:drop-3")).payload == {"v": 3}
    # 重复应用不产生重复 op
    assert len(await b._store.list_ops()) == 3


# ═══════════════════════════════════════════════════════
# revoke 后无法继续接收：被撤销设备的 op 被拒绝
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_revoked_peer_ops_rejected(three_nodes):
    a, b, _ = [n[0] for n in three_nodes]
    await _pair(a, b)

    await _record(b, "knw:before-revoke", {"v": 1})
    before = await a._store.list_ops()
    await a.receive_ops(before)

    # A 撤销 B
    peer = await a.revoke((await b.initialize()).id)
    assert peer.status.value == "REVOKED"

    # B 仍在本地产生 op（本地仍可写），但 A 拒绝接收
    await _record(b, "knw:after-revoke", {"v": 2})
    malicious = await b._store.list_ops()
    with pytest.raises(InvalidSyncOperation):
        await a.receive_ops(malicious)

    assert (await _state_of(a, "knw:after-revoke")) is None


# ═══════════════════════════════════════════════════════
# 乱序应用幂等：A→C 直达 + A→B→C 绕行，最终一致
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_out_of_order_delivery_converges(three_nodes):
    a, b, c = [n[0] for n in three_nodes]
    await _pair(a, b)
    await _pair(b, c)
    await _pair(a, c)

    await _record(a, "knw:order", {"v": 1})
    await _record(a, "knw:order", {"v": 2})
    all_ops = await a._store.list_ops()

    # 乱序：C 先收 op2 再收 op1
    assert await c.receive_ops([all_ops[1]]) == 1
    assert await c.receive_ops([all_ops[0]]) == 1
    # 绕行：B 收全部，再转发给 C（重复幂等）
    assert await b.receive_ops(all_ops) == 2
    assert await c.receive_ops(await b._store.list_ops()) == 0

    assert (await _state_of(a, "knw:order")).payload == {"v": 2}
    assert (await _state_of(b, "knw:order")).payload == {"v": 2}
    assert (await _state_of(c, "knw:order")).payload == {"v": 2}


# ═══════════════════════════════════════════════════════
# 离线遗忘防复活：C 离线错过墓碑，重连补齐后旧写重放仍不可复活
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_three_node_offline_forget_reconciles_without_resurrection(three_nodes):
    (a, store_a, _), (b, _, _), (c, _, _) = three_nodes
    await _pair(a, b)
    await _pair(b, c)
    await _pair(a, c)

    created = await a.record_local(
        "knw:forgotten-offline", {"title": "旧共享事实"}, DOMAIN, now=NOW
    )
    assert await b.receive_ops([created]) == 1
    assert await c.receive_ops([created]) == 1

    # C 此时离线。B 已见过创建操作，因此删除的向量时钟因果上晚于旧值。
    tombstone = await b.record_local(
        "knw:forgotten-offline", {}, DOMAIN, deleted=True, now=NOW + 1
    )
    assert await a.receive_ops([tombstone]) == 1
    assert (await _state_of(a, "knw:forgotten-offline")).tombstone is True
    assert (await _state_of(c, "knw:forgotten-offline")).tombstone is False

    # C 重连后按 oplog 摘要只补缺失墓碑，三节点最终收敛到删除状态。
    c_summary = await AntiEntropy(c._store, None).summary()
    delta = await AntiEntropy(a._store, None).delta_for(set(c_summary["op_ids"]))
    assert [operation.op_id for operation in delta] == [tombstone.op_id]
    assert await c.receive_ops(delta) == 1
    converged = [
        await _state_of(service, "knw:forgotten-offline")
        for service in (a, b, c)
    ]
    assert all(state.tombstone is True for state in converged)

    # 旧创建操作发生重复/乱序重放时，不得覆盖已见墓碑。
    assert await a.receive_ops([created]) == 0
    assert await b.receive_ops([created]) == 0
    assert await c.receive_ops([created]) == 0
    after_replay = [
        await _state_of(service, "knw:forgotten-offline")
        for service in (a, b, c)
    ]
    assert all(state.tombstone is True for state in after_replay)

    # 只有所有未撤销节点确认墓碑后才允许回收；回收后重放相同旧 op 仍被 oplog 去重。
    identity_b = await b.initialize()
    identity_c = await c.initialize()
    gc = TombstoneGC(store_a, retention_seconds=0)
    await a.acknowledge(identity_b.id, [tombstone.op_id], now=NOW + 2)
    assert await gc.collect(now=NOW + 2) == []
    await a.acknowledge(identity_c.id, [tombstone.op_id], now=NOW + 2)
    assert await gc.collect(now=NOW + 2) == ["knw:forgotten-offline"]
    assert await _state_of(a, "knw:forgotten-offline") is None
    assert await a.receive_ops([created]) == 0
    assert await _state_of(a, "knw:forgotten-offline") is None
