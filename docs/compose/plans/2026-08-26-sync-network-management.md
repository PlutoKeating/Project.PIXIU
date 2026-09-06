# 同步网络图形化管理 Implementation Plan

> 2026-09-06 代码复核：发现/请求/确认、同步开关和退出网络 UI 已实现；退出复用逐节点 revoke，无 /sync/leave 或 /sync/now 端点。三逻辑节点协议回归不等于三台物理 V11 场景全部通过。
> 下文实施步骤、旧接口草图和测试数字保留作阶段历史，不作为当前操作手册；当前契约见 docs/API.md，发布见 docs/DELIVERY_PLAN.md。

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 PIXIU 去中心化网状同步升级为默认开启、GUI 可管理的多人场景功能：mDNS 发现未配对设备、确认式配对入网、main 主干 + 快进检测 + 分叉人工仲裁、运行时开关（enabled/paused）、同步 Tab 全量管理控件。

**Architecture:** 后端扩展 sync 层（discovery 广播未配对能力、pair request/confirm 通道、mainline 快进判定置于 CRDT 之上、运行时设置存储）；前端升级记忆面板同步 Tab（总开关/暂停/发现列表/退出网络/状态刷新/冲突横幅），移除单设备解绑。契约写回 docs/API.md。原计划中的“立即同步”最终未保留：后端没有对应动作，自动 Gossip/反熵继续负责同步。

**Tech Stack:** Python 3.12 · FastAPI · zeroconf(mDNS) · SQLite | C++17 · Qt5 Widgets · QtTest(offscreen)

## Global Constraints

- **模块边界**：后端任务只改 `backend/foundation/`；前端任务只改 `frontend/`。契约变更须写回 `docs/API.md`。
- **验收口径**：局域网内两台实例可互相发现（GET /sync/discover 见未配对设备）；A 发起配对 → B 弹窗确认 → 入网；分叉记忆转人工仲裁（ConflictRecord，source="sync"）；`PIXIU_SYNC_NETWORK_ENABLED` 默认 true；前端同步 Tab 全控件可用；后端全量 pytest 绿 + `frontend/scripts/regression.sh` 双路径绿。
- **安全铁律**：mDNS 广播仅含设备名/IP/公钥/域，不含记忆内容；pair_request 的 PIN 6 位数字、TTL 60s；enabled=false 停止广播与监听。
- **mainline 语义**：快进（本地为远程祖先）自动吸收；并发矛盾（Concurrent）才触发仲裁——NEW_WINS/MERGE 自动、MANUAL 生成 ConflictRecord 经既有 `conflict_detected` WS 广播；不改变 Gossip/反熵/存储传输机制。
- **前端移除**：RevokeDialog 单设备解绑入口删除（整网退出替代）；新文案全部 tr() 中文源文本；颜色只用 palette/ui::UiTokens；offscreen 测试。
- 提交前缀 `feat(sync)/feat(frontend)/test(...)/docs(...)`；禁止 push；个人分支同步 `--ff-only`。
- 本计划依赖批次②已合入（main @ 8c25c29）与 spec `docs/compose/specs/2026-08-26-sync-network-management-design.md`（S1–S7）。

---

## Task 1: discovery 扩展（未配对设备广播与发现 + GET /sync/discover）

**Covers:** [S2.1]

**Files:**
- Modify: `backend/foundation/sync/discovery.py`（PeerAdvertisement 加 `pairable: bool`；build_service_info 加 `pairable` 参数与属性；parse_service_info 解析 `b"pairable"` 缺省 False）
- Modify: `backend/foundation/sync/__init__.py`（导出）
- Modify: `backend/foundation/api/http_app.py`（GET /sync/discover 端点）
- Modify: `backend/foundation/api/di.py`（get_sync_discovery 依赖）
- Test: `backend/foundation/tests/test_discovery_pairable.py`

**Interfaces:**
- Consumes: `MdnsDiscovery`（discovery.py:181）、`PeerAdvertisement`、`parse_service_info`、`TrustedPeerDirectory.accept`、`settings.sync_*`
- Produces: `PeerAdvertisement.pairable: bool`；`build_service_info(..., pairable: bool = False)`；`parse_service_info(info) -> PeerAdvertisement`（含 pairable）；`GET /sync/discover -> {"devices": [{"device_id","device_name","addresses","port","pairable","paired"}]}`
- 运行时依赖：`start_sync_runtime` 已启动时 discovery 可用；未启动时返回空列表（HTTP 200，`{"devices": []}`）。

- [ ] **Step 1: 写失败测试**

```python
# backend/foundation/tests/test_discovery_pairable.py
"""mDNS pairable 通告与 /sync/discover 契约。"""
import pytest

from backend.foundation.sync.discovery import (
    PeerAdvertisement,
    build_service_info,
    parse_service_info,
)


def _adv(**overrides):
    return PeerAdvertisement(
        device_id="dev_alpha_0001",
        name="Alpha",
        domain="shared:home",
        public_key=b"k" * 32,
        addresses=("192.168.1.10",),
        port=8766,
        server_name="alpha.local",
        pairable=overrides.get("pairable", False),
    )


def test_build_service_info_encodes_pairable():
    info = build_service_info(
        device_id="dev_alpha_0001", name="Alpha", domain="shared:home",
        public_key=b"k" * 32, addresses=("192.168.1.10",), port=8766,
        server_name="alpha.local", pairable=True,
    )
    parsed = parse_service_info(info)
    assert parsed.pairable is True


def test_parse_service_info_defaults_pairable_false():
    info = build_service_info(
        device_id="dev_alpha_0001", name="Alpha", domain="shared:home",
        public_key=b"k" * 32, addresses=("192.168.1.10",), port=8766,
        server_name="alpha.local",
    )
    parsed = parse_service_info(info)
    assert parsed.pairable is False
```

- [ ] **Step 2: 运行验证失败**

Run: `cd /home/pluto/Project.PIXIU && PYTHONPATH=. PIXIU_EMBEDDING=portable pytest backend/foundation/tests/test_discovery_pairable.py -q`
Expected: FAIL（`PeerAdvertisement` 无 `pairable` 字段 / `build_service_info` 不接受 `pairable` 参数）

- [ ] **Step 3: 实现**

discovery.py 修改：
```python
@dataclass(frozen=True)
class PeerAdvertisement:
    device_id: str
    name: str
    domain: str
    public_key: bytes
    addresses: tuple[str, ...]
    port: int
    server_name: str
    pairable: bool = False
```
```python
def build_service_info(
    *,
    device_id: str,
    name: str,
    domain: str,
    public_key: bytes,
    addresses: list[str] | tuple[str, ...],
    port: int,
    server_name: str,
    pairable: bool = False,
) -> ServiceInfo:
    # ...（既有校验不变）...
    return ServiceInfo(
        type_=SERVICE_TYPE,
        name=f"{device_id}.{SERVICE_TYPE}",
        addresses=[ipaddress.ip_address(value).packed for value in normalized],
        port=port,
        properties={
            b"version": _PROPERTY_VERSION,
            b"device_id": device_id.encode("ascii"),
            b"name": name.encode("utf-8"),
            b"domain": domain.encode("ascii"),
            b"public_key": base64.b64encode(public_key),
            b"server_name": host.encode("utf-8"),
            b"pairable": b"1" if pairable else b"0",
        },
        server=f"{host}.",
    )
```
parse_service_info 在 server_name 解析后追加：
```python
    raw_pairable = properties.get(b"pairable")
    pairable = raw_pairable == b"1" if raw_pairable is not None else False
    return PeerAdvertisement(
        device_id=device_id,
        name=name,
        domain=domain,
        public_key=public_key,
        addresses=addresses,
        port=info.port,
        server_name=server_name,
        pairable=pairable,
    )
```

http_app.py 新增端点（在 `# ─── 设备同步 ───` 区，/sync/peers 之后）：
```python
@app.get("/sync/discover", tags=["Sync"], summary="发现局域网设备")
async def sync_discover(
    sync=Depends(get_sync_service),
    discovery=Depends(get_sync_discovery),
):
    """列出局域网内已发现设备（含未配对），paired 标注本地信任关系。"""
    advertisements = await discovery.list_advertisements()
    known = {peer["id"] for peer in await sync.peers()}
    devices = [
        {
            "device_id": adv.device_id,
            "device_name": adv.name,
            "addresses": list(adv.addresses),
            "port": adv.port,
            "pairable": adv.pairable,
            "paired": adv.device_id in known,
        }
        for adv in advertisements
        if adv.device_id != (await sync.initialize()).id
    ]
    return {"devices": devices}
```

di.py 新增：
```python
async def get_sync_discovery() -> MdnsDiscovery:
    """返回共享的 mDNS 发现实例（随 sync runtime 启动注册）。"""
    from ..sync.discovery import MdnsDiscovery
    runtime = _sync_runtime
    if runtime is None:
        return MdnsDiscovery()  # 未启动：空实例，list 返回 []
    return runtime.discovery
```

`MdnsDiscovery` 增加浏览能力（discovery.py 内追加方法）：
```python
    async def list_advertisements(self) -> list[PeerAdvertisement]:
        """浏览局域网内所有 _pixiu 通告并解析（不含信任过滤）。"""
        aiozc = await self._instance()
        found: list[PeerAdvertisement] = []

        async def _browse() -> list[PeerAdvertisement]:
            queue: asyncio.Queue[PeerAdvertisement] = asyncio.Queue()

            def _on_change(
                zeroconf, service_type, name, state_change,
            ) -> None:
                if state_change is not ServiceStateChange.Added:
                    return
                info = zeroconf.get_service_info(service_type, name)
                if info is not None:
                    try:
                        queue.put_nowait(parse_service_info(info))
                    except DiscoveryError:
                        pass  # 非法通告忽略，不中断浏览

            browser = AsyncServiceBrowser(
                aiozc, SERVICE_TYPE, handlers=[_on_change],
            )
            # 短窗口收集（mDNS 响应通常在数百 ms 内到达）
            for _ in range(20):
                await asyncio.sleep(0.25)
                if not queue.empty():
                    break
            await browser.async_cancel()
            while not queue.empty():
                found.append(queue.get_nowait())
            return found

        try:
            return await asyncio.wait_for(_browse(), timeout=10)
        except asyncio.TimeoutError:
            return []
```
> 注：`MdnsDiscovery` 现持有注册的 `self._registered`；浏览是独立路径，`_instance()` 复用同一 zeroconf。`runtime.discovery` 暴露给 `get_sync_discovery`。

- [ ] **Step 4: 运行验证通过**

Run: `cd /home/pluto/Project.PIXIU && PYTHONPATH=. PIXIU_EMBEDDING=portable pytest backend/foundation/tests/test_discovery_pairable.py backend/foundation/tests/test_sync_network.py -q`
Expected: PASS（新测试 + 既有 sync 网络测试不回归）

- [ ] **Step 5: 契约文档更新**

docs/API.md「设备同步」表追加：
`| GET | /sync/discover | 发现局域网设备（含未配对） | ✅ 已实现（2026-08-XX） |`
并在 §3.16 追加端点说明（请求/响应示例如上）。

- [ ] **Step 6: 提交**

```bash
git add backend/foundation/sync/discovery.py backend/foundation/sync/__init__.py backend/foundation/api/http_app.py backend/foundation/api/di.py backend/foundation/tests/test_discovery_pairable.py docs/API.md
git commit -m "feat(sync): discover pairable devices over mDNS"
```

---

## Task 2: 确认式配对通道（pair/request + pair/confirm + WS pair_request）

**Covers:** [S2.2]

**Files:**
- Create: `backend/foundation/sync/pair_request.py`（PairRequestManager）
- Modify: `backend/foundation/sync/__init__.py`（导出 + SyncService 方法）
- Modify: `backend/foundation/api/http_app.py`（POST /sync/pair/request、POST /sync/pair/confirm）
- Modify: `backend/foundation/api/ws_manager.py`（无——复用 broadcast）
- Test: `backend/foundation/tests/test_pair_request.py`

**Interfaces:**
- Consumes: `SqliteSyncStore.get_meta/set_meta`（store.py:300,308）、`PairingManager.pair`（pairing.py:100）、`ws_manager.broadcast`、`DeviceIdentity`
- Produces: `PairRequestManager(store, identity)` — `async def create(target_device_id: str) -> dict{request_id, pin, target_name, expires_at}`、`async def confirm(request_id: str, accept: bool) -> bool`（accept 时触发 `pair` 令牌交换入网）、`async def pending() -> list[dict]`；`SyncService.create_pair_request(target_device_id)` / `SyncService.confirm_pair_request(request_id, accept)`；`POST /sync/pair/request {target_device_id}` → `{"request_id","pin","target_device_id","expires_at"}`；`POST /sync/pair/confirm {request_id, accept}` → `{"status":"accepted"|"rejected"|"expired"|"not_found"}`
- 事件：`ws_manager.broadcast("pair_request", {"type":"INCOMING","request_id","from_device_id","from_name","pin","expires_at"})`（全局广播；前端按 target 过滤见 Task 6）。

- [ ] **Step 1: 写失败测试**

```python
# backend/foundation/tests/test_pair_request.py
"""确认式配对请求/确认流程。"""
import pytest

from backend.foundation.sync.pair_request import PairRequestError, PairRequestManager


class _FakeStore:
    def __init__(self):
        self.meta: dict[str, str] = {}

    async def get_meta(self, key):
        return self.meta.get(key)

    async def set_meta(self, key, value):
        self.meta[key] = value


class _FakeIdentity:
    id = "dev_alpha_0001"
    domain = "shared:home"


@pytest.mark.asyncio
async def test_create_request_stores_pin_and_ttl():
    store = _FakeStore()
    mgr = PairRequestManager(store, _FakeIdentity())
    result = await mgr.create("dev_beta_0002", now=1_000_000)
    assert result["target_device_id"] == "dev_beta_0002"
    assert len(result["pin"]) == 6
    assert result["pin"].isdigit()
    assert result["expires_at"] == 1_000_000 + 60


@pytest.mark.asyncio
async def test_confirm_expired_request_rejected():
    store = _FakeStore()
    mgr = PairRequestManager(store, _FakeIdentity())
    result = await mgr.create("dev_beta_0002", now=1_000_000)
    status = await mgr.confirm(result["request_id"], accept=True, now=1_000_100)
    assert status == "expired"


@pytest.mark.asyncio
async def test_confirm_unknown_request_not_found():
    store = _FakeStore()
    mgr = PairRequestManager(store, _FakeIdentity())
    status = await mgr.confirm("req_missing_0001", accept=True, now=1_000_000)
    assert status == "not_found"
```

- [ ] **Step 2: 运行验证失败**

Run: `cd /home/pluto/Project.PIXIU && PYTHONPATH=. PIXIU_EMBEDDING=portable pytest backend/foundation/tests/test_pair_request.py -q`
Expected: FAIL（`ModuleNotFoundError: backend.foundation.sync.pair_request`）

- [ ] **Step 3: 实现 pair_request.py**

```python
"""确认式设备配对请求通道（GUI 主路径，QR/PIN 令牌为备选）。"""

from __future__ import annotations

import json
import secrets
import time

from .models import validate_id


class PairRequestError(ValueError):
    pass


_REQUEST_TTL_SECONDS = 60


class PairRequestManager:
    """创建/确认配对请求；accept 后由调用方执行令牌入网。"""

    def __init__(self, store, identity) -> None:
        self._store = store
        self._identity = identity

    async def create(
        self,
        target_device_id: str,
        *,
        now: int | None = None,
        ttl_seconds: int = _REQUEST_TTL_SECONDS,
    ) -> dict:
        validate_id("device", target_device_id)
        if target_device_id == self._identity.id:
            raise PairRequestError("cannot pair a device with itself")
        timestamp = int(time.time()) if now is None else now
        request_id = "req_" + secrets.token_hex(8)
        pin = f"{secrets.randbelow(1_000_000):06d}"
        payload = {
            "request_id": request_id,
            "from_device_id": self._identity.id,
            "pin": pin,
            "expires_at": timestamp + ttl_seconds,
        }
        await self._store.set_meta(
            f"pair_request:{request_id}", json.dumps(payload)
        )
        return {
            "request_id": request_id,
            "pin": pin,
            "target_device_id": target_device_id,
            "expires_at": payload["expires_at"],
        }

    async def pending(self) -> list[dict]:
        # 简单实现：遍历本机发出的请求键（MVP 规模小，直接按前缀扫描）
        results: list[dict] = []
        # store 未暴露前缀扫描；此处返回空并由 confirm 按 request_id 直查。
        return results

    async def confirm(
        self,
        request_id: str,
        *,
        accept: bool,
        now: int | None = None,
    ) -> str:
        validate_id("request", request_id)
        raw = await self._store.get_meta(f"pair_request:{request_id}")
        if raw is None:
            return "not_found"
        payload = json.loads(raw)
        timestamp = int(time.time()) if now is None else now
        if payload["expires_at"] < timestamp:
            return "expired"
        if accept:
            # 由 SyncService 层完成令牌交换（见 Step 4）
            return "accepted"
        return "rejected"
```

- [ ] **Step 4: SyncService 方法与端点**

sync/__init__.py 追加：
```python
    async def create_pair_request(
        self, target_device_id: str, *, now: int | None = None
    ) -> dict:
        identity = await self.initialize()
        return await PairRequestManager(
            self._store, identity
        ).create(target_device_id, now=now)

    async def confirm_pair_request(
        self,
        request_id: str,
        *,
        accept: bool,
        now: int | None = None,
    ) -> str:
        identity = await self.initialize()
        mgr = PairRequestManager(self._store, identity)
        status = await mgr.confirm(request_id, accept=accept, now=now)
        if status == "accepted":
            # accept 后：目标机用已存令牌完成入网。
            # 令牌在 create 时由发起方生成；此处为契约完整性返回 accepted，
            # 实际入网走既有 /sync/pair（前端 confirm 后自动以 QR/PIN 令牌配对）。
            pass
        return status
```
> 注：本设计将"确认"与"令牌交换"解耦——B 确认后，A/B 仍通过既有 `/sync/pair` 完成签名入网（前端 Task 6 在 confirm 成功后自动执行既有配对流程，或复用 PairDialog 的 token）。此解耦保持 PairingManager 签名安全逻辑零改动。

http_app.py 追加：
```python
class SyncPairRequestRequest(BaseModel):
    target_device_id: str


class SyncPairConfirmRequest(BaseModel):
    request_id: str
    accept: bool


@app.post("/sync/pair/request", tags=["Sync"], summary="发起配对请求")
async def sync_pair_request(
    body: SyncPairRequestRequest, sync=Depends(get_sync_service)
):
    try:
        result = await sync.create_pair_request(body.target_device_id)
    except PairRequestError as exc:
        raise HTTPException(status_code=400, detail="INVALID_REQUEST") from exc
    await ws_manager.broadcast(
        "pair_request",
        {
            "type": "INCOMING",
            "request_id": result["request_id"],
            "from_device_id": result["target_device_id"],
            "from_name": "",
            "pin": result["pin"],
            "expires_at": result["expires_at"],
        },
    )
    return result


@app.post("/sync/pair/confirm", tags=["Sync"], summary="确认/拒绝配对请求")
async def sync_pair_confirm(
    body: SyncPairConfirmRequest, sync=Depends(get_sync_service)
):
    status = await sync.confirm_pair_request(
        body.request_id, accept=body.accept
    )
    if status == "not_found":
        raise HTTPException(status_code=404, detail="REQUEST_NOT_FOUND")
    return {"status": status}
```
> 注：`from_device_id`/`from_name` 广播字段为演示语义——request_id 由本机生成即"本机发给目标机"，目标机凭 request_id 确认。MVP 简化：confirm 端点按 request_id 查本机请求并接受；广播的 from_name 可在 Task 6 前端配对时以设备名展示。

- [ ] **Step 5: 运行验证通过 + 契约文档**

Run: `cd /home/pluto/Project.PIXIU && PYTHONPATH=. PIXIU_EMBEDDING=portable pytest backend/foundation/tests/test_pair_request.py backend/foundation/tests/test_api.py -q`
Expected: PASS（新测试 + API 回归）

docs/API.md 设备同步表追加两行：
`| POST | /sync/pair/request | 发起确认式配对请求 | ✅ 已实现（2026-08-XX） |`
`| POST | /sync/pair/confirm | 确认/拒绝配对请求 | ✅ 已实现（2026-08-XX） |`
并补充 §3.17/3.18 请求响应示例（如上）。

- [ ] **Step 6: 提交**

```bash
git add backend/foundation/sync/pair_request.py backend/foundation/sync/__init__.py backend/foundation/api/http_app.py backend/foundation/tests/test_pair_request.py docs/API.md
git commit -m "feat(sync): confirmable pairing request channel"
```

---

## Task 3: mainline 主干（快进检测 + 分叉转人工仲裁）

**Covers:** [S2.3]

**Files:**
- Create: `backend/foundation/sync/mainline.py`
- Modify: `backend/foundation/sync/__init__.py`（SyncService 构造注入 mainline；receive_ops 内接入）
- Modify: `backend/foundation/sync/models.py`（ConflictSource 或复用——见下）
- Modify: `backend/engine/conflict/__init__.py`（ConflictService 构造接受 source 标注，或 record 增加 source 字段——实现时选最小侵入：ConflictRecord 模型加 `source: str = "write"`）
- Test: `backend/foundation/tests/test_mainline.py`

**Interfaces:**
- Consumes: `SyncOplog`/`store.get_state`、`compare_clocks/merge_clocks/increment_clock`（crdt.py:19,32,42）、`LWWElementSet.resolve`（crdt.py:64）、`ConflictService.arbitrate`（conflict/__init__.py:53）、`ConflictRecord`（core/models）
- Produces: `Mainline(store, conflict_service)` — `async def try_fast_forward(ops: list[SyncOp]) -> list[SyncOp]`（返回可安全吸收的 ops；分叉且 MANUAL 的 op 被拦截并生成 ConflictRecord）；`SyncService.receive_ops` 改造：调用 `mainline.try_fast_forward` 后再走 CRDT resolve/materializer
- 行为：快进（本地 main vclock 与 op.vclock 非 Concurrent）→ 正常吸收；Concurrent 且 Arbiter 判 MANUAL → 生成 ConflictRecord（source="sync"）并跳过该 op 落库（保持本地 main 不变，等待人工）；NEW_WINS/MERGE → 正常吸收（Arbiter 内部已处理）。

- [ ] **Step 1: 写失败测试**

```python
# backend/foundation/tests/test_mainline.py
"""mainline 快进/分叉判定。"""
import pytest

from backend.foundation.sync.crdt import increment_clock, merge_clocks
from backend.foundation.sync.mainline import Mainline
from backend.foundation.sync.models import SyncOp


class _FakeStore:
    def __init__(self):
        self.states: dict[str, object] = {}

    async def get_state(self, entity):
        return self.states.get(entity)

    async def save_state(self, entity, state):
        self.states[entity] = state


class _FakeConflict:
    async def arbitrate(self, new_item, existing=None):
        return None  # 默认无冲突


def _op(op_id, entity, vclock):
    return SyncOp(
        op_id=op_id, entity=entity,
        payload={"scope": "shared:home", "value": {}, "deleted": False, "origin": "dev_x"},
        vclock=vclock, ts=1,
    )


@pytest.mark.asyncio
async def test_sequential_ops_fast_forward():
    store = _FakeStore()
    mainline = Mainline(store, _FakeConflict())
    a = increment_clock({}, "dev_a")
    b = increment_clock(a, "dev_b")
    ops = [_op("op1", "knowledge:k1", a), _op("op2", "knowledge:k1", b)]
    absorbed = await mainline.try_fast_forward(ops)
    assert len(absorbed) == 2  # 顺序（非并发）全吸收


@pytest.mark.asyncio
async def test_concurrent_conflict_deferred():
    store = _FakeStore()

    class _ManualConflict:
        async def arbitrate(self, new_item, existing=None):
            record = type("R", (), {"resolution": "MANUAL", "source": "sync"})()
            return record

    mainline = Mainline(store, _ManualConflict())
    a = increment_clock({}, "dev_a")
    b = increment_clock({}, "dev_b")  # 两分支并发
    ops = [_op("op1", "knowledge:k1", a), _op("op2", "knowledge:k1", b)]
    absorbed = await mainline.try_fast_forward(ops)
    assert len(absorbed) == 0  # 分叉且 MANUAL：拦截等待人工
```

- [ ] **Step 2: 运行验证失败**

Run: `cd /home/pluto/Project.PIXIU && PYTHONPATH=. PIXIU_EMBEDDING=portable pytest backend/foundation/tests/test_mainline.py -q`
Expected: FAIL（`ModuleNotFoundError: backend.foundation.sync.mainline`）

- [ ] **Step 3: 实现 mainline.py**

```python
"""main 主干语义：快进检测 + 分叉转人工仲裁。

置于 CRDT 之上：op 级合并仍由 LWWElementSet 完成；本模块判定
「远程 op 集相对本地 main 是快进还是分叉」。
"""

from __future__ import annotations

from .crdt import ClockRelation, compare_clocks, merge_clocks
from .models import SyncOp


class Mainline:
    """维护本地 main 版本向量，判定远端 op 可吸收性。"""

    def __init__(self, store, conflict_service) -> None:
        self._store = store
        self._conflict = conflict_service

    async def _local_main_clock(self, entity: str) -> dict[str, int]:
        state = await self._store.get_state(entity)
        if state is None or getattr(state, "vclock", None) is None:
            return {}
        return dict(state.vclock)

    async def try_fast_forward(self, ops: list[SyncOp]) -> list[SyncOp]:
        """返回可安全吸收（快进或自动裁决通过）的 op 列表。

        分叉且 Arbiter 判 MANUAL 的 op 被拦截：生成 ConflictRecord 并
        从返回列表剔除，本地 main 保持不变，等待人工裁决。
        """
        absorbed: list[SyncOp] = []
        # 按 entity 分组，逐实体判定
        by_entity: dict[str, list[SyncOp]] = {}
        for op in ops:
            by_entity.setdefault(op.entity, []).append(op)
        for entity, group in by_entity.items():
            local_clock = await self._local_main_clock(entity)
            for op in group:
                relation = compare_clocks(local_clock, op.vclock)
                if relation in (ClockRelation.Before, ClockRelation.Equal):
                    absorbed.append(op)
                    local_clock = merge_clocks(local_clock, op.vclock)
                    continue
                if relation == ClockRelation.After:
                    # 远程落后于本地（已在本地或过期 op）——吸收（去重由 caller 处理）
                    absorbed.append(op)
                    continue
                # Concurrent → 语义仲裁
                if self._conflict is not None:
                    record = await self._conflict.arbitrate(op)
                    if record is not None and getattr(record, "resolution", "") == "MANUAL":
                        # 拦截：等待人工
                        continue
                absorbed.append(op)
                local_clock = merge_clocks(local_clock, op.vclock)
        return absorbed
```
> 注：`conflict.arbitrate` 的签名是 `(new_item: KnowledgeItem, existing=None)`；mainline 传入的是 SyncOp——Task 3 实现时在 `receive_ops` 层先把 op.payload 转 KnowledgeItem 再调（实现细节：Mainline 构造再加 `materializer` 或由 SyncService 在拦截前物化 knowledge 模型；测试用 FakeConflict 验证判定逻辑，真实接入在 receive_ops 内做转换并注明）。

- [ ] **Step 4: receive_ops 接入**

sync/__init__.py：
```python
    def __init__(
        self,
        store,
        *,
        identity_manager=None,
        crdt=None,
        materializer=None,
        mainline=None,
    ):
        # ...（既有字段）...
        self._mainline = mainline

    async def receive_ops(self, operations: list[SyncOp]) -> int:
        identity = await self.initialize()
        for op in operations:
            await self._verify_operation(op, identity)

        if self._mainline is not None:
            operations = await self._mainline.try_fast_forward(operations)

        accepted = 0
        for op in operations:
            if await self._store.get_op(op.op_id) is not None:
                continue
            current = await self._store.get_state(op.entity)
            resolved = self._crdt.resolve(current, op)
            if (
                self._materializer is not None
                and (current is None or resolved.op_id != current.op_id)
            ):
                await self._materializer(resolved)
            if not await self._store.append_op(op):
                continue
            await self._store.save_state(resolved)
            accepted += 1
        return accepted
```
di.py `get_sync_service` 处组装 mainline（注入 `get_conflict_service(db)`；为不引入循环依赖，mainline 构造仅存 conflict service 引用，arbitrate 调用按 Step 3 注处理）：
```python
    from ..sync.mainline import Mainline
    conflict = await get_conflict_service(db)
    mainline = Mainline(SqliteSyncStore(db), conflict)
    return SyncService(
        SqliteSyncStore(db),
        device_name=settings.sync_device_name,
        domain=settings.sync_domain,
        key_passphrase=settings.sync_key_passphrase,
        materializer=FoundationMaterializer(
            evidence_repo=await get_evidence_repo(db),
            knowledge_repo=await get_knowledge_repo(db),
            preference_repo=await get_preference_repo(db),
        ),
        mainline=mainline,
    )
```
> 注：`get_sync_service` 现有签名（di.py:175-182）不含 materializer 组装——Task 3 实现时按现有 di 结构对齐（读 di.py 全文后决定是在 get_sync_service 内组装还是新增 get_mainline；以不破坏既有测试为准）。

- [ ] **Step 5: 运行验证 + 冲突来源标注**

Run: `cd /home/pluto/Project.PIXIU && PYTHONPATH=. PIXIU_EMBEDDING=portable pytest backend/foundation/tests/test_mainline.py backend/foundation/tests/test_sync_core.py -q`
Expected: PASS（新测试 + 既有 sync 核心测试不回归）

ConflictRecord 增加 `source` 字段（core/models.py ConflictRecord 模型 + repository 表/序列化兼容默认 "write"；同步分叉记录置 "sync"）：
```python
# core/models.py ConflictRecord 追加字段（默认值保持向后兼容）
    source: str = "write"  # write | sync
```
> 注：repository 持久化若按列存储需 migration；若 JSON 存储则免迁移——实现时读 conflict repository 现状二选一，倾向 JSON 兼容（不迁移）。

- [ ] **Step 6: 提交**

```bash
git add backend/foundation/sync/mainline.py backend/foundation/sync/__init__.py backend/foundation/sync/models.py backend/foundation/core/models.py backend/foundation/api/di.py backend/engine/conflict/__init__.py backend/foundation/tests/test_mainline.py
git commit -m "feat(sync): mainline fast-forward with manual arbitration handoff"
```

---

## Task 4: 默认开启 + 运行时开关（PUT /sync/settings）

**Covers:** [S2.4]

**Files:**
- Modify: `backend/foundation/core/config.py`（`PIXIU_SYNC_NETWORK_ENABLED` 默认 true）
- Modify: `backend/.env.example`、`build/release/debian/pixiu.env`（默认 true）
- Modify: `backend/foundation/sync/__init__.py`（SyncService.status 扩展 enabled/paused；新增 set_settings）
- Modify: `backend/foundation/sync/store.py`（set_meta/get_meta 复用——无需新表）
- Modify: `backend/foundation/api/http_app.py`（PUT /sync/settings）
- Modify: `backend/foundation/api/di.py`（start_sync_runtime 读 KV 覆盖 env；settings 变更热生效）
- Test: `backend/foundation/tests/test_sync_settings.py`

**Interfaces:**
- Consumes: `settings.sync_network_enabled`、`SqliteSyncStore.get_meta/set_meta`、`SyncRuntime.start/stop`、`_sync_runtime`
- Produces: `GET /sync/status` 扩展 `{"enabled": bool, "paused": bool, ...}`（既有字段保留）；`PUT /sync/settings {"enabled": bool, "paused": bool}` → `{"enabled","paused"}`；KV 键 `sync_runtime:enabled`/`sync_runtime:paused`；默认 enabled=true（env）+ KV 覆盖。

- [ ] **Step 1: 写失败测试**

```python
# backend/foundation/tests/test_sync_settings.py
"""运行时同步开关契约。"""
import pytest


class _FakeStore:
    def __init__(self):
        self.meta: dict[str, str] = {}

    async def get_meta(self, key):
        return self.meta.get(key)

    async def set_meta(self, key, value):
        self.meta[key] = value


@pytest.mark.asyncio
async def test_settings_default_enabled():
    from backend.foundation.core.config import settings
    assert settings.sync_network_enabled is True
```

- [ ] **Step 2: 运行验证失败**

Run: `cd /home/pluto/Project.PIXIU && PYTHONPATH=. PIXIU_EMBEDDING=portable pytest backend/foundation/tests/test_sync_settings.py -q`
Expected: FAIL（当前 `_env_bool("PIXIU_SYNC_NETWORK_ENABLED")` 无默认 → 默认 False）

- [ ] **Step 3: 实现**

config.py:
```python
        self._sync_network_enabled = _env_bool("PIXIU_SYNC_NETWORK_ENABLED", True)
```
> 注：`_env_bool(key, default)` 已支持默认参数（config.py:65）。`.env.example` 与 `pixiu.env` 的 `PIXIU_SYNC_NETWORK_ENABLED=false` 改 `true`。但 config 的 `if self._sync_network_enabled:` 校验块（config.py:114-119）要求 advertise_addresses 非空——默认开启后无配置的机器会启动失败：**Task 4 需将该校验改为「enabled 且配置了 advertise 时才要求非空」**，否则默认开启会导致既有部署崩溃。实现：
```python
        if self._sync_network_enabled:
            if not self._sync_advertise_addresses:
                # 默认开启但未显式配置广播地址：允许运行，mDNS 自动取本机 LAN IP
                self._sync_advertise_addresses = ()
```
> 注：`build_service_info` 要求 addresses 非空（discovery.py:55）——运行时若 advertise 为空需由 MdnsDiscovery 自动探测本机 LAN IP（Task 4 实现：在 start_sync_runtime 组装 service_info 前，若 advertise 为空则用 `socket.getaddrinfo(hostname)` 或 zeroconf 自动地址，否则回退 127.0.0.1 并告警）。实现时以「不崩溃 + 可配对」为底线，真机验证时再补多网卡策略。

SyncService 追加：
```python
    async def set_settings(self, *, enabled: bool | None = None,
                           paused: bool | None = None) -> dict:
        if enabled is not None:
            await self._store.set_meta(
                "sync_runtime:enabled", "1" if enabled else "0"
            )
        if paused is not None:
            await self._store.set_meta(
                "sync_runtime:paused", "1" if paused else "0"
            )
        return await self._runtime_settings()

    async def _runtime_settings(self) -> dict:
        raw_enabled = await self._store.get_meta("sync_runtime:enabled")
        raw_paused = await self._store.get_meta("sync_runtime:paused")
        return {
            "enabled": raw_enabled != "0" if raw_enabled is not None
                else settings.sync_network_enabled,
            "paused": raw_paused == "1",
        }
```
status() 扩展（models.py SyncStatus 加字段，或 status() 返回 dict 合并——实现时以不破坏既有 status 契约为准，倾向 models 加 `enabled: bool`/`paused: bool` 默认 False 并在 SyncService.status 内填充 `_runtime_settings()`）。

http_app.py：
```python
class SyncSettingsRequest(BaseModel):
    enabled: bool | None = None
    paused: bool | None = None


@app.put("/sync/settings", tags=["Sync"], summary="更新同步开关")
async def sync_settings_put(
    body: SyncSettingsRequest, sync=Depends(get_sync_service)
):
    result = await sync.set_settings(
        enabled=body.enabled, paused=body.paused
    )
    return result
```
di.py `start_sync_runtime`：读 KV 覆盖 env 默认：
```python
async def start_sync_runtime() -> SyncRuntime | None:
    global _sync_runtime
    db = await get_db()
    service = await get_sync_service(db)
    runtime_settings = await service._runtime_settings()
    if not runtime_settings["enabled"]:
        return None
    if _sync_runtime is None:
        # ...（既有组装，paused 语义在 SyncRuntime 内生效：paused 时 gossip 停止推送）
    return _sync_runtime
```
> 注：paused 的传输暂停语义需 SyncRuntime 支持（gossip 推送开关）——Task 4 在 runtime.py 加 `paused` 属性并由 gossip 周期检查；若实现成本高，paused 最小语义 = 暂停 record_local 的广播（不入队）但保留发现与配对。以计划意图「保留配对与发现、停止数据流」为准，实现时选最小可行并在报告注明。

- [ ] **Step 4: 运行验证 + 文档**

Run: `cd /home/pluto/Project.PIXIU && PYTHONPATH=. PIXIU_EMBEDDING=portable pytest backend/foundation/tests/test_sync_settings.py backend/foundation/tests/test_config.py -q`
Expected: PASS（新测试 + config 回归；注意 test_config 若有断言默认 false 需同步更新）

docs/API.md 追加：
`| PUT | /sync/settings | 更新同步开关（enabled/paused） | ✅ 已实现（2026-08-XX） |`
GET /sync/status 响应示例补充 `"enabled": true, "paused": false`。

- [ ] **Step 5: 提交**

```bash
git add backend/foundation/core/config.py backend/.env.example build/release/debian/pixiu.env backend/foundation/sync/__init__.py backend/foundation/sync/models.py backend/foundation/sync/runtime.py backend/foundation/api/http_app.py backend/foundation/api/di.py backend/foundation/tests/test_sync_settings.py docs/API.md
git commit -m "feat(sync): default-on runtime sync settings"
```

---

## Task 5: 前端 Transport/SyncController 扩展

**Covers:** [S3.1, S4]

**Files:**
- Modify: `frontend/src/services/BackendTransport.h/.cpp`（虚函数 discoverDevices/requestPairing/confirmPairing/updateSyncSettings/syncNow；信号 devicesLoaded/pairRequestResult/pairConfirmResult/settingsResult）
- Modify: `frontend/src/services/HttpBackendTransport.h/.cpp`（GET /sync/discover、POST /sync/pair/request、POST /sync/pair/confirm、PUT /sync/settings、POST /sync/now）
- Modify: `frontend/src/app/SyncController.h/.cpp`（discover/request/confirm/updateSettings 状态机 + 信号）
- Modify: `frontend/src/services/EventRouter.h/.cpp`、`WebSocketClient.cpp`（pair_request 帧路由 → 信号 pairingRequested）
- Test: `frontend/tests/t_sync_controller.cpp`（新）或扩展 t_contract_fixtures.cpp

**Interfaces:**
- Consumes: 既有 HttpBackendTransport.postJson/getJson/putJson（存在 putJson？实现时查——若无则补）、EventRouter 既有 isKnownBusinessEvent
- Produces: `SyncController::discover() -> 信号 discoveredDevices(QJsonArray)`；`requestPairing(QString targetId)`；`confirmPairing(QString requestId, bool accept)`；`updateSettings(bool enabled, bool paused)`；`EventRouter::pairingRequested(QJsonObject)` 信号
- 契约形状与 docs/API.md Task 1/2/4 一致。

- [ ] **Step 1: 写失败测试**（t_sync_controller.cpp，offscreen，仿 t_app_navigation 隔离配方）

```cpp
// 用例 1：discover 成功 → discoveredDevices 含目标设备
// 用例 2：requestPairing 成功 → pairRequestResult 信号
// 用例 3：updateSettings(false, false) → settingsResult enabled=false
// 用例 4：confirmPairing 成功 → pairConfirmResult status accepted
```
（具体代码按 t_app_navigation.cpp 的 QTemporaryDir + PixiuTests org 配方编写；TCP 桩或 mock transport——仓库惯例见 t_contract_fixtures.cpp。）

- [ ] **Step 2: 运行验证失败**

Run: `cd /home/pluto/Project.PIXIU && cmake -S frontend -B build/frontend -DPIXIU_HAVE_KYSDK=OFF -G Ninja && cmake --build build/frontend -j && QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend -R sync_controller --output-on-failure`
Expected: FAIL（目标不存在 / 方法未定义）

- [ ] **Step 3: 实现**（transport + controller + router，按上述接口）

- [ ] **Step 4: 运行验证通过 + CMake 注册**

Run: `QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend -R "sync_controller|contract_fixtures|app_navigation" --output-on-failure`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/services/ frontend/src/app/SyncController.h frontend/src/app/SyncController.cpp frontend/tests/t_sync_controller.cpp frontend/CMakeLists.txt
git commit -m "feat(frontend): sync network transport and controller"
```

---

## Task 6: 同步 Tab 升级（开关/发现/退出/状态刷新/冲突横幅 + 移除单设备解绑）

**Covers:** [S3.1, S3.2, S6]

**Files:**
- Modify: `frontend/src/widgets/MemoryPanel.h/.cpp`（同步 Tab 控件集 + 冲突横幅 + showConflictTab）
- Modify: `frontend/src/widgets/MemoryPanel.cpp` createSyncTab（总开关/暂停/发现列表/退出网络/状态刷新/冲突横幅）
- Modify: `frontend/src/app/PixiuApp.h/.cpp`（pair_request WS 接线 → 配对确认对话框；冲突横幅计数联动）
- Modify: `frontend/src/app/SyncController.h/.cpp`（leaveNetwork 批处理）
- Modify: `frontend/src/widgets/PairDialog.cpp`（可选：适配确认式配对）
- Delete: `frontend/src/widgets/RevokeDialog.h/.cpp`（单设备解绑移除；CMake 同步）
- Test: `frontend/tests/t_app_navigation.cpp`、`frontend/tests/t_memory_panel.cpp`（若存在）扩展

**Interfaces:**
- Consumes: Task 5 的 SyncController 信号、GET /sync/status（含 enabled/paused）、`/sync/peers`、`/sync/discover`、conflicts 列表
- Produces: 同步 Tab 控件 objectName：`syncMasterSwitch`/`syncPauseSwitch`/`discoveredDeviceList`/`leaveNetworkButton`/`syncConflictBanner`；配对确认对话框（`pairRequestDialog`）
- 行为：总开关默认开（初始值 GET status.enabled）；off 时下级控件禁用；暂停仅停传输；发现列表「配对」→ requestPairing → 对方 confirm；「退出网络」确认框 → 逐台 revoke（复用既有 /sync/peers/{id}/revoke）；状态刷新读取 peers/status；横幅 N>0 可见、点击 showConflictTab()。

- [ ] **Step 1: 写失败测试**（t_app_navigation 扩展两用例：syncMasterSwitchDefaultOnAndGates、leaveNetworkButtonShowsConfirmAndRevokesAll；t_memory_panel 若存在加 discoverListRenders + conflictBannerCounts）

- [ ] **Step 2: 运行验证失败**

Run: `QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend -R "app_navigation|memory_panel" --output-on-failure`
Expected: FAIL（新控件/行为未实现）

- [ ] **Step 3: 实现**（控件集 + 信号接线 + 移除 RevokeDialog 入口与文件 + CMake）

- [ ] **Step 4: 运行验证通过**

Run: `QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend --output-on-failure`
Expected: 全绿（注意：移除 RevokeDialog 后既有引用它的测试需同步更新）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/widgets/ frontend/src/app/ frontend/tests/ frontend/CMakeLists.txt
git commit -m "feat(frontend): sync network management panel"
```

---

## Task 7: i18n 再生成 + 双路径回归 + 文档收尾

**Covers:** [S4, S7]

**Files:**
- Modify: `frontend/resources/i18n/pixiu_en_US.ts/.qm`（lupdate/lrelease）
- Modify: `README.md`（核心亮点第一条更新实现状态：默认开启 + GUI 管理 + main 主干人工仲裁）
- Test: 无新测试（回归）

- [ ] **Step 1: lupdate 收编新文案**（cd frontend/resources/i18n && lupdate ../../src ../../tests -ts pixiu_en_US.ts，补全英文译文至 0 unfinished，lrelease 生成 .qm）
- [ ] **Step 2: README 更新**
- [ ] **Step 3: 全量双路径回归**：`cd /home/pluto/Project.PIXIU && bash frontend/scripts/regression.sh`（OFF/ON 双路径 + deb 校验）+ 后端全量 pytest（后台轮询）
- [ ] **Step 4: 提交**（i18n 与 README 分开两个提交：`chore(frontend): regenerate i18n for sync panel`、`docs: update sync feature status`）

---

## 执行顺序与协调点

Task 1→2→3→4 后端顺序（3 依赖 1 的 discover 语义无强依赖但共享 sync 模块，按序避免冲突）；Task 5→6 前端依赖后端契约（可先按 docs/API.md 桩开发）；Task 7 收尾。每任务独立提交供两阶段审查；跨模块契约以 docs/API.md 为唯一事实源。
