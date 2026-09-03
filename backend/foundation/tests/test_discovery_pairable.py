"""mDNS pairable 通告、浏览与 /sync/discover 端点契约（Task SN-1）。"""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient
from zeroconf import ServiceInfo, ServiceStateChange

import backend.foundation.api.di as di_module
from backend.foundation.api import app
from backend.foundation.sync.discovery import (
    MdnsDiscovery,
    PeerAdvertisement,
    build_service_info,
    parse_service_info,
)

SERVICE_TYPE = "_pixiu._tcp.local."
DEV_A = "dev_" + "A" * 26
DEV_B = "dev_" + "B" * 26
DEV_C = "dev_" + "C" * 26


def _info(device_id: str = DEV_A, *, pairable: bool = False, name: str = "Alpha"):
    return build_service_info(
        device_id=device_id,
        name=name,
        domain="shared:home",
        public_key=b"k" * 32,
        addresses=("192.168.1.10",),
        port=8766,
        server_name="alpha.local",
        pairable=pairable,
    )


def _adv(device_id: str = DEV_A, *, pairable: bool = False, name: str = "Alpha"):
    return PeerAdvertisement(
        device_id=device_id,
        name=name,
        domain="shared:home",
        public_key=b"k" * 32,
        addresses=("192.168.1.10",),
        port=8766,
        server_name="alpha.local",
        pairable=pairable,
    )


# ─── pairable 通告编码/解析 ───────────────────────────────


def test_build_service_info_encodes_pairable_flag():
    info = _info(pairable=True)
    assert info.properties[b"pairable"] == b"1"
    parsed = parse_service_info(info)
    assert parsed.pairable is True
    assert parsed.device_id == DEV_A


def test_build_service_info_defaults_pairable_false():
    info = _info()
    assert info.properties[b"pairable"] == b"0"
    assert parse_service_info(info).pairable is False


def test_parse_service_info_treats_missing_pairable_as_false():
    """旧版通告没有 pairable 属性时按不可配对处理（向后兼容）。"""
    legacy = ServiceInfo(
        type_=SERVICE_TYPE,
        name=f"{DEV_A}.{SERVICE_TYPE}",
        addresses=["192.168.1.10"],
        port=8766,
        properties={
            b"version": b"1",
            b"device_id": DEV_A.encode("ascii"),
            b"name": b"Legacy",
            b"domain": b"shared:home",
            b"public_key": base64.b64encode(b"k" * 32),
            b"server_name": b"legacy.local",
        },
        server="legacy.local.",
    )
    assert parse_service_info(legacy).pairable is False


# ─── MdnsDiscovery.list_advertisements ────────────────────


@pytest.mark.asyncio
async def test_list_advertisements_returns_empty_without_socket():
    """未启动的实例不打开 mDNS socket，直接返回空列表。"""
    discovery = MdnsDiscovery()
    assert await discovery.list_advertisements() == []


@pytest.mark.asyncio
async def test_list_advertisements_browses_and_parses(monkeypatch):
    import backend.foundation.sync.discovery as discovery_module

    valid = _info(DEV_A, pairable=True, name="Alpha")
    invalid = ServiceInfo(
        type_=SERVICE_TYPE,
        name=f"{DEV_B}.{SERVICE_TYPE}",
        addresses=["192.168.1.20"],
        port=8766,
        properties={b"version": b"99"},  # 非法版本 → DiscoveryError
        server="bad.local.",
    )

    class FakeAsyncZeroconf:
        def __init__(self):
            self.zeroconf = object()
            self.services = {valid.name: valid, invalid.name: invalid}

        async def async_get_service_info(self, service_type, name, timeout=3000):
            return self.services.get(name)

    class FakeBrowser:
        def __init__(self, zc, type_, handlers=None, **kwargs):
            for handler in handlers or []:
                handler(zc, type_, valid.name, ServiceStateChange.Added)
                handler(zc, type_, invalid.name, ServiceStateChange.Added)
            self.cancelled = False

        async def async_cancel(self):
            self.cancelled = True

    monkeypatch.setattr(discovery_module, "AsyncServiceBrowser", FakeBrowser)
    discovery = MdnsDiscovery(zeroconf=FakeAsyncZeroconf())
    result = await discovery.list_advertisements(timeout_seconds=5)

    assert [item.device_id for item in result] == [DEV_A]
    assert result[0].pairable is True
    assert result[0].name == "Alpha"
    assert result[0].addresses == ("192.168.1.10",)


# ─── GET /sync/discover 端点 ──────────────────────────────


class _FakeSettings:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.embedding = "portable"
        self.vector_store = "portable"
        self.ocr = "portable"
        self.sync_device_name = "书房工作站"
        self.sync_domain = "shared:home"
        self.sync_key_passphrase = "phase3-api-test-passphrase"
        self.sync_network_enabled = False
        self.monitor_enabled = False


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(
        di_module, "settings", _FakeSettings(str(tmp_path / "pixiu.db"))
    )
    di_module._db = None
    di_module._sync_runtime = None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    di_module._db = None


class _FakeDiscovery:
    def __init__(self, advertisements):
        self._advertisements = advertisements

    async def list_advertisements(self):
        return self._advertisements


class _FakeIdentity:
    def __init__(self, id_: str) -> None:
        self.id = id_


class _FakeSync:
    """只实现 handler 用到的 peers()/initialize()。"""

    def __init__(self, self_id: str, peer_ids: list[str]) -> None:
        self._self_id = self_id
        self._peer_ids = peer_ids

    async def initialize(self):
        return _FakeIdentity(self._self_id)

    async def peers(self):
        return [{"id": self._self_id}] + [{"id": pid} for pid in self._peer_ids]


def test_sync_discover_empty_when_runtime_not_started(client):
    resp = client.get("/sync/discover")
    assert resp.status_code == 200
    assert resp.json() == {"devices": []}


def test_sync_discover_marks_paired_and_filters_self(client):
    app.dependency_overrides[di_module.get_sync_service] = lambda: _FakeSync(
        DEV_A, [DEV_B]
    )
    app.dependency_overrides[di_module.get_sync_discovery] = lambda: _FakeDiscovery(
        [
            _adv(DEV_A, name="Self"),
            _adv(DEV_B, pairable=True, name="PairedPeer"),
            _adv(DEV_C, pairable=True, name="NearbyPeer"),
        ]
    )
    try:
        resp = client.get("/sync/discover")
    finally:
        app.dependency_overrides.pop(di_module.get_sync_service, None)
        app.dependency_overrides.pop(di_module.get_sync_discovery, None)

    assert resp.status_code == 200
    devices = resp.json()["devices"]
    by_id = {device["device_id"]: device for device in devices}
    assert set(by_id) == {DEV_B, DEV_C}  # 本机自身被过滤
    assert by_id[DEV_B]["paired"] is True
    assert by_id[DEV_B]["pairable"] is True
    assert by_id[DEV_B]["device_name"] == "PairedPeer"
    assert by_id[DEV_B]["addresses"] == ["192.168.1.10"]
    assert by_id[DEV_B]["port"] == 8766
    assert by_id[DEV_C]["paired"] is False
    assert by_id[DEV_C]["pairable"] is True
