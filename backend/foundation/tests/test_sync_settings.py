"""SN-4 运行时同步开关契约：默认开启 + KV 持久化 + enabled/paused 语义。"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from unittest import mock

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.core.config import Settings
from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.sync import SqliteSyncStore, SyncService
from backend.foundation.sync.models import SyncStatus
from backend.foundation.sync.runtime import SyncRuntime, _resolve_advertise_addresses

PASSPHRASE = "phase3-settings-test-passphrase"


# ─── config 默认值（SN-4：默认开启 + 无配置不崩溃）────────────

def test_config_defaults_to_enabled():
    with mock.patch.dict(os.environ, {}, clear=True):
        configured = Settings()
    assert configured.sync_network_enabled is True
    assert configured.sync_advertise_addresses == ()


def test_config_allows_enabled_without_advertise_or_tls():
    base = {
        "PIXIU_SYNC_NETWORK_ENABLED": "true",
        "PIXIU_SYNC_KEY_PASSPHRASE": "phase3-config-test-passphrase",
    }
    with mock.patch.dict(os.environ, base, clear=True):
        configured = Settings()
    assert configured.sync_network_enabled is True
    assert configured.sync_advertise_addresses == ()
    # TLS 文件路径仍由属性级校验要求（runtime 装配期触发，di 层降级处理）
    with pytest.raises(ValueError, match="PIXIU_SYNC_CERTFILE"):
        configured.sync_certfile


# ─── SyncService：KV 持久化 + 跨实例 ───────────────────────

async def _node(root: Path, filename: str):
    db_path = str(root / filename)
    sync_db = sqlite3.connect(db_path)
    init_db_on_connection(sync_db)
    sync_db.close()
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    store = SqliteSyncStore(db)
    return db, store


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    db, store = await _node(tmp_path, "settings.db")
    yield store
    await db.close()


def _service(store, *, enabled_default: bool = True) -> SyncService:
    return SyncService(
        store,
        device_name="settings-host",
        domain="shared:home",
        key_passphrase=PASSPHRASE,
        runtime_enabled_default=enabled_default,
    )


@pytest.mark.asyncio
async def test_runtime_settings_default_from_env(store):
    service = _service(store, enabled_default=True)
    assert await service._runtime_settings() == {"enabled": True, "paused": False}


@pytest.mark.asyncio
async def test_kv_enabled_overrides_env_default(store):
    service = _service(store, enabled_default=True)
    await service.set_settings(enabled=False)
    # KV "0" 覆盖 env 默认 true
    assert await service._runtime_settings() == {"enabled": False, "paused": False}


@pytest.mark.asyncio
async def test_set_settings_persists_and_reads_across_instances(store):
    first = _service(store, enabled_default=True)
    result = await first.set_settings(enabled=False, paused=True)
    assert result == {"enabled": False, "paused": True}

    # 跨实例：新 service 同一 store 读到同一 KV
    second = _service(store, enabled_default=True)
    assert await second._runtime_settings() == {"enabled": False, "paused": True}

    # 部分更新只动指定键
    assert await first.set_settings(paused=False) == {
        "enabled": False,
        "paused": False,
    }
    assert await second._runtime_settings() == {"enabled": False, "paused": False}


@pytest.mark.asyncio
async def test_status_includes_enabled_and_paused(store):
    service = _service(store, enabled_default=True)
    status = await service.status()
    assert isinstance(status, SyncStatus)
    assert status.enabled is True
    assert status.paused is False

    await service.set_settings(enabled=False, paused=True)
    status = await service.status()
    assert status.enabled is False
    assert status.paused is True


# ─── SyncRuntime paused 语义：停数据流、保留发现与配对 ──────

class _FakeAdvertisement:
    def __init__(self, device_id: str):
        self.device_id = device_id


class _MemoryDiscovery:
    def __init__(self, advertisements=()):
        self.advertisements = list(advertisements)
        self.discover_calls = 0

    async def discover(self, timeout_seconds: float = 1.0):
        self.discover_calls += 1
        return list(self.advertisements)


class _MemoryGossip:
    def __init__(self):
        self.calls = 0

    async def run_once(self):
        self.calls += 1
        return {
            "peers_attempted": 1,
            "operations_delivered": 1,
            "peers_failed": 0,
        }


class _FakeStore:
    def __init__(self):
        self.statuses: list[tuple] = []

    async def set_peer_status(self, device_id, status, ts):
        self.statuses.append((device_id, status, ts))


class _FakeDirectory:
    async def accept(self, advertisement):
        return True


class _FakeIdentity:
    id = "dev_" + "A" * 26


def _make_runtime(*, paused: bool = False, advertisements=()):
    discovery = _MemoryDiscovery(advertisements)
    gossip = _MemoryGossip()
    runtime = SyncRuntime(
        identity=_FakeIdentity(),
        store=_FakeStore(),
        discovery=discovery,
        directory=_FakeDirectory(),
        gossip=gossip,
        service_info=object(),
        server_starter=object,
        interval_seconds=60,
        discovery_timeout_seconds=0.01,
        paused=paused,
    )
    return runtime, discovery, gossip


@pytest.mark.asyncio
async def test_runtime_paused_skips_gossip_but_keeps_discovery():
    advertisement = _FakeAdvertisement("dev_" + "B" * 26)
    runtime, discovery, gossip = _make_runtime(
        paused=True, advertisements=(advertisement,)
    )
    result = await runtime.run_once()
    assert gossip.calls == 0  # 数据流暂停
    assert discovery.discover_calls == 1  # 发现保留
    assert result["peers_attempted"] == 0
    assert result["operations_delivered"] == 0
    assert result["trusted_peers_discovered"] == 1  # 在线标记保留


@pytest.mark.asyncio
async def test_runtime_resumed_runs_gossip_and_paused_toggle():
    runtime, discovery, gossip = _make_runtime()
    assert runtime.paused is False
    result = await runtime.run_once()
    assert gossip.calls == 1
    assert result["peers_attempted"] == 1

    runtime.set_paused(True)
    assert runtime.paused is True
    await runtime.run_once()
    assert gossip.calls == 1  # paused 后不再推送

    runtime.set_paused(False)
    await runtime.run_once()
    assert gossip.calls == 2  # 恢复推送


# ─── advertise 地址自动解析（默认开启、无配置机器可运行）─────

class _AdvertiseSettings:
    def __init__(self, advertise=()):
        self.sync_advertise_addresses = advertise


def test_resolve_advertise_addresses_uses_explicit():
    resolved = _resolve_advertise_addresses(
        _AdvertiseSettings(("192.168.1.20", "127.0.0.1"))
    )
    assert resolved == ("192.168.1.20", "127.0.0.1")


def test_resolve_advertise_addresses_falls_back_to_valid_lan_or_loopback():
    from backend.foundation.sync.discovery import _lan_address

    resolved = _resolve_advertise_addresses(_AdvertiseSettings())
    assert isinstance(resolved, tuple)
    assert len(resolved) >= 1
    for address in resolved:
        _lan_address(address)  # 必须为 LAN/回环可通告地址


# ─── di 接线：缺证书降级不阻塞 + 热生效转发 ─────────────────

class _DegradedSettings:
    db_path = None
    sync_device_name = "degraded-host"
    sync_domain = "shared:test"
    sync_key_passphrase = PASSPHRASE
    sync_network_enabled = True
    sync_bind_host = "127.0.0.1"
    sync_port = 8766
    sync_server_name = "degraded-host"
    sync_advertise_addresses = ()
    sync_certfile = None
    sync_keyfile = None
    sync_cafile = None
    sync_tls_key_password = None


async def _close_di_db(di_module) -> None:
    """关闭 di 单例 db 连接（防 aiosqlite worker 线程在事件循环关闭后告警）。"""
    if di_module._db is not None:
        await di_module._db.close()
    di_module._db = None
    di_module._sync_runtime = None


@pytest.mark.asyncio
async def test_start_sync_runtime_degrades_without_tls(tmp_path, monkeypatch):
    import backend.foundation.api.di as di_module

    fake = _DegradedSettings()
    fake.db_path = str(tmp_path / "degraded.db")
    monkeypatch.setattr(di_module, "settings", fake)
    di_module._sync_runtime = None
    di_module._db = None
    try:
        runtime = await di_module.start_sync_runtime()
        assert runtime is None
        assert di_module._sync_runtime is None
    finally:
        await _close_di_db(di_module)


@pytest.mark.asyncio
async def test_start_sync_runtime_kv_disabled_returns_none(tmp_path, monkeypatch):
    import backend.foundation.api.di as di_module

    fake = _DegradedSettings()
    fake.db_path = str(tmp_path / "disabled.db")
    monkeypatch.setattr(di_module, "settings", fake)
    di_module._sync_runtime = None
    di_module._db = None
    try:
        db = await di_module.get_db()
        service = await di_module.get_sync_service(db)
        await service.set_settings(enabled=False)
        runtime = await di_module.start_sync_runtime()
        assert runtime is None
    finally:
        await _close_di_db(di_module)


@pytest.mark.asyncio
async def test_apply_sync_runtime_settings_forward_paused(monkeypatch):
    import backend.foundation.api.di as di_module

    class _FakeRuntime:
        def __init__(self):
            self.paused_value: bool | None = None

        def set_paused(self, value):
            self.paused_value = value

    fake_runtime = _FakeRuntime()
    monkeypatch.setattr(di_module, "_sync_runtime", fake_runtime)

    async def _noop_start():
        return fake_runtime

    async def _noop_stop():
        monkeypatch.setattr(di_module, "_sync_runtime", None)

    monkeypatch.setattr(di_module, "start_sync_runtime", _noop_start)
    monkeypatch.setattr(di_module, "stop_sync_runtime", _noop_stop)

    await di_module.apply_sync_runtime_settings(enabled=True, paused=True)
    assert fake_runtime.paused_value is True

    await di_module.apply_sync_runtime_settings(enabled=False, paused=True)
    assert di_module._sync_runtime is None
