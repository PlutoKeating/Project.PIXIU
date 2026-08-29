"""确认式配对请求/确认流程（Task SN-2：pair/request + pair/confirm）。"""

from __future__ import annotations

import json

import pytest

from backend.foundation.sync.pair_request import PairRequestError, PairRequestManager


def _device(tag: str) -> str:
    """构造合法的 dev_ 前缀设备 ID（26 位字母数字，见 core.models._ID_PATTERNS）。"""
    return f"dev_{(tag + '0' * 26)[:26]}"


class _FakeStore:
    def __init__(self):
        self.meta: dict[str, str] = {}

    async def get_meta(self, key):
        return self.meta.get(key)

    async def set_meta(self, key, value):
        self.meta[key] = value


class _FakeIdentity:
    id = _device("alpha")
    domain = "shared:home"


@pytest.mark.asyncio
async def test_create_request_stores_pin_and_ttl():
    store = _FakeStore()
    mgr = PairRequestManager(store, _FakeIdentity())
    result = await mgr.create(_device("beta"), now=1_000_000)
    assert result["target_device_id"] == _device("beta")
    assert len(result["pin"]) == 6
    assert result["pin"].isdigit()
    assert result["expires_at"] == 1_000_000 + 60
    # KV 落库：pair_request:{request_id} 键存 JSON payload
    raw = store.meta[f"pair_request:{result['request_id']}"]
    payload = json.loads(raw)
    assert payload["request_id"] == result["request_id"]
    assert payload["from_device_id"] == _FakeIdentity.id
    assert payload["target_device_id"] == result["target_device_id"]
    assert payload["pin"] == result["pin"]
    assert payload["expires_at"] == 1_000_000 + 60


@pytest.mark.asyncio
async def test_confirm_expired_request_rejected():
    store = _FakeStore()
    mgr = PairRequestManager(store, _FakeIdentity())
    result = await mgr.create(_device("beta"), now=1_000_000)
    status = await mgr.confirm(result["request_id"], accept=True, now=1_000_100)
    assert status == "expired"


@pytest.mark.asyncio
async def test_confirm_unknown_request_not_found():
    store = _FakeStore()
    mgr = PairRequestManager(store, _FakeIdentity())
    status = await mgr.confirm("req_missing_0001", accept=True, now=1_000_000)
    assert status == "not_found"


@pytest.mark.asyncio
async def test_confirm_accept():
    store = _FakeStore()
    mgr = PairRequestManager(store, _FakeIdentity())
    result = await mgr.create(_device("beta"), now=1_000_000)
    status = await mgr.confirm(result["request_id"], accept=True, now=1_000_010)
    assert status == "accepted"


@pytest.mark.asyncio
async def test_confirm_accept_is_single_use():
    """防重放：首次 confirm 记录 status，二次 confirm 返回已记录状态不再重新判定。"""
    store = _FakeStore()
    mgr = PairRequestManager(store, _FakeIdentity())
    result = await mgr.create(_device("beta"), now=1_000_000)
    assert (
        await mgr.confirm(result["request_id"], accept=True, now=1_000_010)
        == "accepted"
    )
    # 翻转 accept 或已过 TTL，均返回已记录状态
    assert (
        await mgr.confirm(result["request_id"], accept=False, now=1_000_010)
        == "accepted"
    )
    assert (
        await mgr.confirm(result["request_id"], accept=True, now=1_000_100)
        == "accepted"
    )
    payload = json.loads(store.meta[f"pair_request:{result['request_id']}"])
    assert payload["status"] == "accepted"


@pytest.mark.asyncio
async def test_confirm_reject_is_single_use():
    store = _FakeStore()
    mgr = PairRequestManager(store, _FakeIdentity())
    result = await mgr.create(_device("beta"), now=1_000_000)
    assert (
        await mgr.confirm(result["request_id"], accept=False, now=1_000_010)
        == "rejected"
    )
    assert (
        await mgr.confirm(result["request_id"], accept=True, now=1_000_010)
        == "rejected"
    )
    payload = json.loads(store.meta[f"pair_request:{result['request_id']}"])
    assert payload["status"] == "rejected"


@pytest.mark.asyncio
async def test_confirm_reject():
    store = _FakeStore()
    mgr = PairRequestManager(store, _FakeIdentity())
    result = await mgr.create(_device("beta"), now=1_000_000)
    status = await mgr.confirm(result["request_id"], accept=False, now=1_000_010)
    assert status == "rejected"


@pytest.mark.asyncio
async def test_create_rejects_self_pairing():
    store = _FakeStore()
    mgr = PairRequestManager(store, _FakeIdentity())
    with pytest.raises(PairRequestError):
        await mgr.create(_FakeIdentity.id, now=1_000_000)


@pytest.mark.asyncio
async def test_create_rejects_invalid_target_device_id():
    store = _FakeStore()
    mgr = PairRequestManager(store, _FakeIdentity())
    with pytest.raises(PairRequestError):
        await mgr.create("not-a-device-id", now=1_000_000)
