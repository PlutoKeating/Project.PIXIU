"""SN-3 mainline：快进吸收 + 分叉转人工仲裁。

判定层语义（S2.3）：
- 远程 op 相对本地 main 是快进（BEFORE/EQUAL/AFTER）→ 自动吸收；
- 并发分叉 → 交 ConflictService.arbitrate：MANUAL 拦截（不返回、本地 main
  不变、等待人工），NEW_WINS/MERGE 自动吸收；
- 非 knowledge 实体（evidence/preference）由 LWW 确定性收敛，不经过仲裁。

测试用 FakeStore（dict states）+ FakeConflict（记录调用、队列返回 resolution）
验证判定逻辑；receive_ops 接入用真实 SqliteSyncStore 两节点验证。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.core.models import (
    ConflictRecord,
    ConflictResolution,
    KnowledgeItem,
    SyncOp,
)
from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.sync import (
    Mainline,
    PairingMethod,
    SqliteSyncStore,
    SyncService,
)
from backend.foundation.sync.crdt import increment_clock, merge_clocks

NOW = 2_000_000_000
DOMAIN = "shared:home"
PASSPHRASE = "sn3-mainline-test-passphrase"
ENTITY = "knowledge:k1"


def _dev(tag: str) -> str:
    return f"dev_{(tag + '0' * 26)[:26]}"


def _op_id(tag: str) -> str:
    return f"sync_{(tag + '0' * 26)[:26]}"


def _knw(tag: str) -> str:
    return f"knw_{(tag + '0' * 26)[:26]}"


def _op(
    tag: str,
    entity: str,
    vclock: dict[str, int],
    *,
    value: dict | None = None,
    ts: int = NOW,
) -> SyncOp:
    return SyncOp(
        op_id=_op_id(tag),
        entity=entity,
        payload={
            "scope": DOMAIN,
            "value": value if value is not None else {"title": tag},
            "deleted": False,
            "origin": next(iter(vclock), "unknown"),
        },
        vclock=vclock,
        ts=ts,
    )


class _FakeState:
    def __init__(self, vclock: dict[str, int]) -> None:
        self.vclock = vclock


class _FakeStore:
    def __init__(self, states: dict | None = None) -> None:
        self.states: dict[str, _FakeState] = dict(states or {})
        self.get_calls: list[str] = []

    async def get_state(self, entity: str) -> _FakeState | None:
        self.get_calls.append(entity)
        return self.states.get(entity)


class _FakeConflict:
    """记录 arbitrate 调用；按队列依次返回给定 resolution（None 表示无冲突）。"""

    def __init__(self, *resolutions: ConflictResolution | None) -> None:
        self._resolutions = list(resolutions)
        self.calls: list[tuple[object, str]] = []

    async def arbitrate(self, new_item, *, source: str = "write"):
        self.calls.append((new_item, source))
        resolution = self._resolutions.pop(0) if self._resolutions else None
        if resolution is None:
            return None
        return ConflictRecord(
            id=f"cfl_{'a' * 26}",
            target_knowledge="knw_AAAAAAAAAAAAAAAAAAAAAAAAAA",
            field="x",
            old_value=1,
            new_value=2,
            resolution=resolution,
            created_at=NOW,
            source=source,
        )


def _knowledge_value(tag: str, title: str) -> dict:
    return {
        "id": _knw(tag),
        "kind": "FACT",
        "title": title,
        "body": {"amount": 434.5},
        "scope": DOMAIN,
        "created_at": NOW,
        "updated_at": NOW,
    }


def _trivial_factory(op: SyncOp) -> KnowledgeItem:
    """判定逻辑测试用：跳过 payload 校验，直接给一个最小 KnowledgeItem。"""
    return KnowledgeItem(
        id=_knw("demo"),
        kind="FACT",
        title="t",
        scope=DOMAIN,
        created_at=NOW,
        updated_at=NOW,
    )


# ═══════════════════════════════════════════════════════
# 快进（BEFORE / EQUAL / AFTER）全吸收
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_sequential_ops_fast_forward_all_absorbed():
    store = _FakeStore()
    mainline = Mainline(store, _FakeConflict())
    a = increment_clock({}, _dev("a"))
    b = increment_clock(a, _dev("b"))  # 因果后继（AFTER）
    ops = [_op("op1", ENTITY, a), _op("op2", ENTITY, b)]
    absorbed = await mainline.try_fast_forward(ops)
    assert absorbed == ops  # 顺序（非并发）全吸收
    assert _FakeConflict().calls == []  # 快进不触发仲裁


@pytest.mark.asyncio
async def test_offline_before_op_absorbed():
    # 本地 main 已推进，远端回补旧 op（BEFORE）→ 吸收，去重由 caller 负责
    store = _FakeStore({ENTITY: _FakeState({_dev("a"): 2})})
    conflict = _FakeConflict()
    mainline = Mainline(store, conflict)
    stale = _op("stale", ENTITY, {_dev("a"): 1})
    assert await mainline.try_fast_forward([stale]) == [stale]
    assert conflict.calls == []


@pytest.mark.asyncio
async def test_equal_op_absorbed():
    store = _FakeStore({ENTITY: _FakeState({_dev("a"): 1})})
    conflict = _FakeConflict()
    mainline = Mainline(store, conflict)
    same = _op("same", ENTITY, {_dev("a"): 1})
    assert await mainline.try_fast_forward([same]) == [same]
    assert conflict.calls == []


# ═══════════════════════════════════════════════════════
# 并发分叉：MANUAL 拦截 / NEW_WINS / MERGE 自动吸收
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_concurrent_manual_intercepted_and_main_unchanged():
    store = _FakeStore({ENTITY: _FakeState({_dev("a"): 1})})
    conflict = _FakeConflict(ConflictResolution.MANUAL)
    mainline = Mainline(store, conflict, knowledge_factory=_trivial_factory)
    fork = _op("fork", ENTITY, {_dev("b"): 1})

    absorbed = await mainline.try_fast_forward([fork])

    assert absorbed == []  # 拦截：不返回
    assert len(conflict.calls) == 1
    assert conflict.calls[0][1] == "sync"  # 同步分叉记录置 source="sync"
    # 本地 main 不变（store 未被写入，get_state 只读一次）
    assert store.states[ENTITY].vclock == {_dev("a"): 1}
    assert store.get_calls == [ENTITY]


@pytest.mark.asyncio
async def test_concurrent_new_wins_absorbed():
    store = _FakeStore({ENTITY: _FakeState({_dev("a"): 1})})
    conflict = _FakeConflict(ConflictResolution.NEW_WINS)
    mainline = Mainline(store, conflict, knowledge_factory=_trivial_factory)
    fork = _op("fork", ENTITY, {_dev("b"): 1})
    assert await mainline.try_fast_forward([fork]) == [fork]
    assert len(conflict.calls) == 1


@pytest.mark.asyncio
async def test_concurrent_merge_absorbed():
    store = _FakeStore({ENTITY: _FakeState({_dev("a"): 1})})
    conflict = _FakeConflict(ConflictResolution.MERGE)
    mainline = Mainline(store, conflict, knowledge_factory=_trivial_factory)
    fork = _op("fork", ENTITY, {_dev("b"): 1})
    assert await mainline.try_fast_forward([fork]) == [fork]
    assert len(conflict.calls) == 1


@pytest.mark.asyncio
async def test_mixed_batch_partial_interception():
    store = _FakeStore({ENTITY: _FakeState({_dev("a"): 1})})
    conflict = _FakeConflict(ConflictResolution.MANUAL, ConflictResolution.NEW_WINS)
    mainline = Mainline(store, conflict, knowledge_factory=_trivial_factory)
    blocked = _op("blocked", ENTITY, {_dev("b"): 1})
    absorbed = _op("absorbed", ENTITY, {_dev("c"): 1})

    result = await mainline.try_fast_forward([blocked, absorbed])

    assert result == [absorbed]  # MANUAL 拦截，后续 NEW_WINS 吸收
    assert [call[1] for call in conflict.calls] == ["sync", "sync"]


@pytest.mark.asyncio
async def test_empty_batch_returns_empty():
    mainline = Mainline(_FakeStore(), _FakeConflict())
    assert await mainline.try_fast_forward([]) == []


# ═══════════════════════════════════════════════════════
# SyncOp payload → KnowledgeItem 转换钩子
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_default_factory_builds_knowledge_item_from_payload():
    value = _knowledge_value("demo", "四月预算")
    entity = f"knowledge:{value['id']}"
    store = _FakeStore({entity: _FakeState({_dev("a"): 1})})
    conflict = _FakeConflict(ConflictResolution.MANUAL)
    mainline = Mainline(store, conflict)
    fork = _op("fork", entity, {_dev("b"): 1}, value=value)

    await mainline.try_fast_forward([fork])

    item = conflict.calls[0][0]
    assert isinstance(item, KnowledgeItem)
    assert item.id == value["id"]
    assert item.title == "四月预算"
    assert item.scope == DOMAIN


@pytest.mark.asyncio
async def test_custom_factory_injected():
    store = _FakeStore({ENTITY: _FakeState({_dev("a"): 1})})
    conflict = _FakeConflict(ConflictResolution.MANUAL)
    mainline = Mainline(store, conflict, knowledge_factory=lambda op: None)

    fork = _op("fork", ENTITY, {_dev("b"): 1})
    # factory 返回 None → 不仲裁、直接吸收（调用方显式选择跳过）
    assert await mainline.try_fast_forward([fork]) == [fork]
    assert conflict.calls == []


@pytest.mark.asyncio
async def test_non_knowledge_concurrent_op_absorbed_without_arbitration():
    evidence_entity = "evidence:evd_x"
    store = _FakeStore({evidence_entity: _FakeState({_dev("a"): 1})})
    conflict = _FakeConflict()
    mainline = Mainline(store, conflict)
    fork = _op("fork", evidence_entity, {_dev("b"): 1})

    # 非知识实体并发：LWW 确定性收敛，不进仲裁
    assert await mainline.try_fast_forward([fork]) == [fork]
    assert conflict.calls == []


# ═══════════════════════════════════════════════════════
# receive_ops 接入（真实 SqliteSyncStore 两节点）
# ═══════════════════════════════════════════════════════

async def _connect(root: Path, filename: str) -> aiosqlite.Connection:
    db_path = str(root / filename)
    sync_db = sqlite3.connect(db_path)
    init_db_on_connection(sync_db)
    sync_db.close()
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def _pair(a: SyncService, b: SyncService) -> None:
    token_b = await b.create_pairing_token(PairingMethod.QR, now=NOW)
    await a.pair(PairingMethod.QR, token_b, now=NOW)
    token_a = await a.create_pairing_token(PairingMethod.QR, now=NOW)
    await b.pair(PairingMethod.QR, token_a, now=NOW)


@pytest.mark.asyncio
async def test_receive_ops_intercepts_manual_fork_and_absorbs_new_wins(tmp_path: Path):
    db_a = await _connect(tmp_path, "a.db")
    db_b = await _connect(tmp_path, "b.db")
    store_a = SqliteSyncStore(db_a)
    store_b = SqliteSyncStore(db_b)
    conflict = _FakeConflict(ConflictResolution.MANUAL, ConflictResolution.NEW_WINS)
    svc_a = SyncService(
        store_a, device_name="书房工作站", domain=DOMAIN, key_passphrase=PASSPHRASE
    )
    svc_b = SyncService(
        store_b,
        device_name="客厅一体机",
        domain=DOMAIN,
        key_passphrase=PASSPHRASE,
        mainline=Mainline(store_b, conflict),
    )
    try:
        await _pair(svc_a, svc_b)
        device_b = (await svc_b.initialize()).id

        # ── 分叉 #1：A/B 并发写同一知识实体，B 收 A 的 op → MANUAL 拦截
        entity_fork = f"knowledge:{_knw('fork')}"
        await svc_a.record_local(
            entity_fork, _knowledge_value("fork", "A 版本"), DOMAIN, now=NOW
        )
        await svc_b.record_local(
            entity_fork, _knowledge_value("fork", "B 版本"), DOMAIN, now=NOW
        )
        ops_a = [op for op in await store_a.list_ops() if op.entity == entity_fork]

        assert await svc_b.receive_ops(ops_a) == 0  # 零吸收
        assert ops_a[0].op_id not in await store_b.op_ids()  # 不落库
        state_b = await store_b.get_state(entity_fork)
        assert state_b is not None and state_b.vclock == {device_b: 1}  # 本地 main 不变
        assert conflict.calls[0][1] == "sync"  # 同步分叉记录 source="sync"

        # ── 分叉 #2：同一服务，下一并发 op → NEW_WINS 自动吸收落库
        entity_wins = f"knowledge:{_knw('wins')}"
        await svc_a.record_local(
            entity_wins, _knowledge_value("wins", "A2"), DOMAIN, now=NOW
        )
        await svc_b.record_local(
            entity_wins, _knowledge_value("wins", "B2"), DOMAIN, now=NOW
        )
        ops_b = [op for op in await store_a.list_ops() if op.entity == entity_wins]

        assert await svc_b.receive_ops(ops_b) == 1  # 自动吸收
        assert ops_b[0].op_id in await store_b.op_ids()
    finally:
        await db_a.close()
        await db_b.close()
