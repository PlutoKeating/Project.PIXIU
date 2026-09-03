"""SN-4 运行时同步开关契约：默认开启 + KV 持久化 + enabled/paused 语义。"""

from __future__ import annotations

import os
import socket
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.core.config import Settings
from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.sync import SqliteSyncStore, SyncService
from backend.foundation.sync.models import SyncStatus
from backend.foundation.sync.runtime import (
    SyncRuntime,
    _auto_lan_addresses,
    _resolve_advertise_addresses,
)

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


# ─── _auto_lan_addresses：优先默认路由、排除回环（SN-4 I-2）──────

def _mock_getaddrinfo(entries: list[str]):
    def _fake(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))
            for address in entries
        ]

    return _fake


def test_auto_lan_addresses_excludes_loopback_and_keeps_lan_order(monkeypatch):
    """getaddrinfo 返回 (LAN + 回环) → 只取 LAN，且保持解析顺序。"""
    import backend.foundation.sync.runtime as runtime_module

    monkeypatch.setattr(runtime_module, "_default_route_ipv4", lambda: None)
    monkeypatch.setattr(
        runtime_module.socket,
        "getaddrinfo",
        _mock_getaddrinfo(
            ["192.168.1.20", "127.0.1.1", "127.0.0.1", "192.168.1.30"]
        ),
    )
    assert _auto_lan_addresses() == ("192.168.1.20", "192.168.1.30")


def test_auto_lan_addresses_prefers_default_route_ip(monkeypatch):
    """默认路由 IP 优先于主机名解析结果。"""
    import backend.foundation.sync.runtime as runtime_module

    monkeypatch.setattr(runtime_module, "_default_route_ipv4", lambda: "192.168.1.50")
    monkeypatch.setattr(
        runtime_module.socket,
        "getaddrinfo",
        _mock_getaddrinfo(["192.168.1.20", "192.168.1.50"]),
    )
    assert _auto_lan_addresses() == ("192.168.1.50", "192.168.1.20")


def test_auto_lan_addresses_loopback_only_falls_back_with_warning(
    monkeypatch, caplog
):
    """仅回环（Debian 127.0.1.1 惯例）→ 自动分支返回空，resolve 回退
    127.0.0.1 并告警「不可跨机配对」。"""
    import logging

    import backend.foundation.sync.runtime as runtime_module

    monkeypatch.setattr(runtime_module, "_default_route_ipv4", lambda: None)
    monkeypatch.setattr(
        runtime_module.socket,
        "getaddrinfo",
        _mock_getaddrinfo(["127.0.1.1", "127.0.0.1"]),
    )
    assert _auto_lan_addresses() == ()

    with caplog.at_level(logging.WARNING):
        resolved = _resolve_advertise_addresses(_AdvertiseSettings())
    assert resolved == ("127.0.0.1",)
    assert "cross-machine pairing unavailable" in caplog.text
    assert "PIXIU_SYNC_ADVERTISE_ADDRESSES" in caplog.text


# ─── di 接线：缺证书降级不阻塞 + 热生效转发 ─────────────────

class _DegradedSettings:
    db_path = None
    embedding = "portable"
    vector_store = "portable"
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
    await di_module.stop_vector_store()
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


# ─── SN-4 I-1/I-3：env 守卫移除 + paused 重启恢复 ──────────

class _RecordingRuntime:
    """记录 start/set_paused 调用的假 runtime，用于 di 接线测试。"""

    def __init__(self, paused: bool = False):
        self.paused = paused
        self.started = False

    def set_paused(self, value: bool) -> None:
        self.paused = value

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        pass


def _write_self_signed_cert(root: Path) -> dict[str, str]:
    """生成可加载的自签名证书（构造 create_sync_runtime 所需，不握手）。"""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    now = datetime.now(timezone.utc)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PIXIU settings test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path = root / "cert.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path = root / "key.pem"
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return {"cert": str(cert_path), "key": str(key_path)}


class _EnvDisabledTlsSettings(_DegradedSettings):
    """env 关闭但 TLS 配置齐全的替身：验证 create_sync_runtime 不再被 env 阻断。"""

    sync_network_enabled = False


@pytest.mark.asyncio
async def test_create_sync_runtime_builds_when_env_disabled(tmp_path):
    """I-1：env=false 不再阻断构造——启动与否由 di 的 KV 门控决定。"""
    from backend.foundation.sync.runtime import create_sync_runtime

    files = _write_self_signed_cert(tmp_path)
    fake = _EnvDisabledTlsSettings()
    fake.db_path = str(tmp_path / "env-disabled.db")
    fake.sync_certfile = files["cert"]
    fake.sync_keyfile = files["key"]
    fake.sync_cafile = files["cert"]

    db, store = await _node(tmp_path, "env-disabled.db")
    service = _service(store, enabled_default=False)
    try:
        runtime = await create_sync_runtime(service, store, fake)
        assert isinstance(runtime, SyncRuntime)
        assert runtime.paused is False  # 未传 paused 时默认不暂停
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_start_sync_runtime_kv_enabled_starts_despite_env_false(
    tmp_path, monkeypatch
):
    """I-1：env=false + KV enabled=1 → start_sync_runtime 实际启动（非 None）。"""
    import backend.foundation.api.di as di_module

    fake = _DegradedSettings()
    fake.sync_network_enabled = False
    fake.db_path = str(tmp_path / "kv-enabled.db")
    monkeypatch.setattr(di_module, "settings", fake)
    di_module._sync_runtime = None
    di_module._db = None

    captured: dict = {}

    async def _fake_create(service, store, settings, *, paused=False):
        captured["paused"] = paused
        return _RecordingRuntime(paused=paused)

    monkeypatch.setattr(di_module, "create_sync_runtime", _fake_create)
    try:
        db = await di_module.get_db()
        service = await di_module.get_sync_service(db)
        await service.set_settings(enabled=True)  # KV enabled=1 覆盖 env=false
        runtime = await di_module.start_sync_runtime()
        assert runtime is not None
        assert runtime.started is True
        assert di_module._sync_runtime is runtime
    finally:
        await _close_di_db(di_module)


@pytest.mark.asyncio
async def test_start_sync_runtime_restores_paused_from_kv(tmp_path, monkeypatch):
    """I-3：KV paused=1 + 重启路径（start_sync_runtime 直调）→ runtime.paused=True。"""
    import backend.foundation.api.di as di_module

    fake = _DegradedSettings()
    fake.db_path = str(tmp_path / "paused-restart.db")
    monkeypatch.setattr(di_module, "settings", fake)
    di_module._sync_runtime = None
    di_module._db = None

    captured: dict = {}

    async def _fake_create(service, store, settings, *, paused=False):
        captured["paused"] = paused
        return _RecordingRuntime(paused=paused)

    monkeypatch.setattr(di_module, "create_sync_runtime", _fake_create)
    try:
        db = await di_module.get_db()
        service = await di_module.get_sync_service(db)
        await service.set_settings(enabled=True, paused=True)
        runtime = await di_module.start_sync_runtime()
        assert runtime is not None
        assert captured["paused"] is True  # create_sync_runtime 收到 KV paused
        assert runtime.paused is True  # runtime 构造即暂停（非 set_paused 热生效）
        assert runtime.started is True
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
