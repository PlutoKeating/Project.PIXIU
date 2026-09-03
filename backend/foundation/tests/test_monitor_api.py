"""Tests for monitor API endpoints + capture_event broadcast (BE-3).

对齐 frontend/docs/MONITOR_API_REQUIREMENTS.md §1–§3 契约：
  - GET / PUT /monitor/config roundtrip、非法配置 400 INVALID_REQUEST；
  - GET /monitor/log 分页（limit≤500 默认 100、offset）+ 空日志 {"events": []}；
  - PUT 写一条 state_changed 日志并广播 capture_event（TestClient WS 收到）；
  - MonitorLogStore 直连单测（写 + 时间倒序分页 + limit 钳制）；
  - on_capture 回调（watch 线程语义）：短同步写日志 + 调度广播回主循环；
  - _lifespan 在 PIXIU_MONITOR_ENABLED 下启动/停止 monitor runtime。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import backend.foundation.api.di as di_module
from backend.foundation.api import app
from backend.foundation.api.monitor_log import (
    MAX_PAGE_SIZE,
    MonitorLogStore,
    broadcast_capture_event,
)

VALID_CONFIG = {
    "enabled": True,
    "sources": {
        "directory": True,
        "clipboard": False,
        "behavior": False,
        "screenshot": False,
    },
    "directories": ["/home/u/Downloads"],
}

DEFAULT_CONFIG = {
    "enabled": False,
    "sources": {
        "directory": False,
        "clipboard": False,
        "behavior": False,
        "screenshot": False,
    },
    "directories": [],
}


class _FakeSettings:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.embedding = "portable"
        self.vector_store = "portable"
        self.ocr = "portable"
        self.sync_device_name = "书房工作站"
        self.sync_domain = "shared:home"
        self.sync_key_passphrase = "phase3-monitor-test-passphrase"
        self.sync_network_enabled = False
        self.monitor_enabled = False


def _reset_di_singletons() -> None:
    di_module._db = None
    di_module._monitor_config_store = None
    di_module._monitor_log_store = None
    di_module._monitor_runtime = None
    di_module._behavior_collector = None
    di_module._main_loop = None


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(di_module, "settings", _FakeSettings(str(tmp_path / "pixiu.db")))
    _reset_di_singletons()
    with TestClient(app) as c:
        yield c
    _reset_di_singletons()


# ═══════════════════════════════════════════════════════
# §1 配置读写：GET/PUT /monitor/config
# ═══════════════════════════════════════════════════════

def test_get_monitor_config_returns_defaults(client):
    resp = client.get("/monitor/config")
    assert resp.status_code == 200
    assert resp.json() == DEFAULT_CONFIG


def test_put_get_roundtrip(client):
    resp = client.put("/monitor/config", json=VALID_CONFIG)
    assert resp.status_code == 200
    assert resp.json() == VALID_CONFIG
    assert client.get("/monitor/config").json() == VALID_CONFIG


def test_put_normalizes_missing_keys(client):
    resp = client.put("/monitor/config", json={"enabled": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["sources"] == {
        "directory": False,
        "clipboard": False,
        "behavior": False,
        "screenshot": False,
    }
    assert data["directories"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {"sources": {"bogus": True}},      # 未知 source 名
        {"enabled": "yes"},                # 字段类型错误
        {"directories": ["relative/path"]},  # 相对目录
        {"sources": {"directory": 1}},     # source 值非 bool
        {"sources": [], "directories": []},  # sources 非 dict
        {"directories": "not-a-list"},     # directories 非 list
    ],
)
def test_put_invalid_returns_400(client, payload):
    resp = client.put("/monitor/config", json=payload)
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "INVALID_REQUEST"
    assert body["request_id"]


def test_put_persists_across_requests(client):
    client.put("/monitor/config", json=VALID_CONFIG)
    # 新请求/新连接仍读到持久化配置（同一 db，daemon 存续视角）
    assert client.get("/monitor/config").json() == VALID_CONFIG


# ═══════════════════════════════════════════════════════
# §2 活动日志：GET /monitor/log
# ═══════════════════════════════════════════════════════

def test_monitor_log_empty(client):
    assert client.get("/monitor/log").json() == {"events": []}


def test_put_writes_state_changed_log(client):
    client.put("/monitor/config", json=VALID_CONFIG)
    events = client.get("/monitor/log").json()["events"]
    assert len(events) == 1
    entry = events[0]
    assert entry["source"] == "system"
    assert entry["status"] == "state_changed"
    assert isinstance(entry["summary"], str) and entry["summary"]
    assert isinstance(entry["ts"], int)
    assert entry["evidence_id"] is None
    assert entry["knowledge_id"] is None


def test_put_survives_log_write_error(client, monkeypatch):
    """PUT 半提交隔离：state_changed 日志写入失败不吞掉已生效的配置变更。"""

    def _boom(self, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(MonitorLogStore, "write_event", _boom)
    resp = client.put("/monitor/config", json=VALID_CONFIG)
    assert resp.status_code == 200
    assert resp.json() == VALID_CONFIG
    # store.put（持久化 + 热生效）先于日志旁路执行，配置必须已生效
    assert client.get("/monitor/config").json() == VALID_CONFIG


def test_monitor_log_pagination(client):
    store = MonitorLogStore(str(Path(di_module.settings.db_path)))
    for i in range(5):
        store.write_event(
            source="directory",
            status="ingested",
            summary=f"记住文件 {i}.txt",
            ts=1756080000 + i,
            evidence_id=f"evd_{i}",
            knowledge_id=f"knw_{i}",
        )
    # 默认 limit=100，时间倒序（最新在前）
    events = client.get("/monitor/log").json()["events"]
    assert [e["summary"] for e in events] == [
        f"记住文件 {i}.txt" for i in reversed(range(5))
    ]
    assert events[0]["evidence_id"] == "evd_4"
    assert events[0]["knowledge_id"] == "knw_4"
    # limit + offset 分页
    page = client.get("/monitor/log", params={"limit": 2, "offset": 1}).json()["events"]
    assert [e["summary"] for e in page] == ["记住文件 3.txt", "记住文件 2.txt"]
    # offset 超出 → 空页而非 404
    empty = client.get("/monitor/log", params={"offset": 100}).json()["events"]
    assert empty == []


def test_monitor_log_limit_and_offset_validation(client):
    assert (
        client.get("/monitor/log", params={"limit": MAX_PAGE_SIZE + 1}).status_code
        == 400
    )
    assert client.get("/monitor/log", params={"limit": 0}).status_code == 400
    assert client.get("/monitor/log", params={"offset": -1}).status_code == 400


# ═══════════════════════════════════════════════════════
# §3 WS 实时事件：capture_event
# ═══════════════════════════════════════════════════════

def test_put_broadcasts_capture_event_state_changed(client):
    with client.websocket_connect("/events") as websocket:
        assert websocket.receive_json() == {"event": "connected", "data": {}}
        resp = client.put("/monitor/config", json=VALID_CONFIG)
        assert resp.status_code == 200
        frame = websocket.receive_json()
        assert frame["event"] == "capture_event"
        data = frame["data"]
        assert data["source"] == "system"
        assert data["status"] == "state_changed"
        assert isinstance(data["summary"], str) and data["summary"]
        assert isinstance(data["ts"], int)
        assert data["evidence_id"] is None


@pytest.mark.asyncio
async def test_broadcast_capture_event_payload(tmp_path, monkeypatch):
    from backend.foundation.api import ws_manager

    frames = []

    async def fake_broadcast(event, data):
        frames.append({"event": event, "data": data})

    monkeypatch.setattr(ws_manager, "broadcast", fake_broadcast)
    await broadcast_capture_event(
        source="directory",
        status="ingested",
        summary="记住文件 支出清单.xlsx",
        evidence_id="evd_x",
        knowledge_id="knw_y",
        ts=1756080000,
    )
    assert frames == [
        {
            "event": "capture_event",
            "data": {
                "source": "directory",
                "status": "ingested",
                "summary": "记住文件 支出清单.xlsx",
                "ts": 1756080000,
                "evidence_id": "evd_x",
                "knowledge_id": "knw_y",
            },
        }
    ]


# ═══════════════════════════════════════════════════════
# monitor_log 存储直连（写 + 分页 + limit 钳制）
# ═══════════════════════════════════════════════════════

def test_monitor_log_store_roundtrip_and_clamp(tmp_path):
    store = MonitorLogStore(str(tmp_path / "m.db"))
    store.write_event(
        source="directory", status="ignored", summary="忽略超大文件 x", ts=1
    )
    store.write_event(
        source="system", status="state_changed", summary="监控已开启", ts=2
    )
    events = store.list_events()
    assert len(events) == 2
    assert events[0]["status"] == "state_changed"
    assert events[1]["source"] == "directory"
    assert events[1]["evidence_id"] is None
    assert events[1]["knowledge_id"] is None
    # 直连调用：limit 钳制到 MAX_PAGE_SIZE、offset 负值钳制到 0
    assert len(store.list_events(limit=MAX_PAGE_SIZE * 10)) == 2
    assert len(store.list_events(offset=-5)) == 2


def test_monitor_log_store_default_ts(tmp_path):
    store = MonitorLogStore(str(tmp_path / "m.db"))
    before = int(__import__("time").time())
    store.write_event(source="system", status="state_changed", summary="监控已暂停")
    ts = store.list_events()[0]["ts"]
    assert before <= ts <= int(__import__("time").time())


# ═══════════════════════════════════════════════════════
# on_capture 回调（watch 线程语义）：写日志 + 调度广播回主循环
# ═══════════════════════════════════════════════════════

class _FakeLoop:
    """记录被调度 callable 的主事件循环桩（模拟 _lifespan 注册的主循环）。"""

    def __init__(self) -> None:
        self.scheduled: list = []

    def is_running(self) -> bool:
        return True

    def call_soon_threadsafe(self, fn) -> None:
        self.scheduled.append(fn)


def test_capture_callback_writes_log_and_schedules_broadcast(tmp_path, monkeypatch):
    store = MonitorLogStore(str(tmp_path / "m.db"))
    fake_loop = _FakeLoop()
    monkeypatch.setattr(di_module, "_main_loop", fake_loop)

    callback = di_module._make_capture_callback(store)
    callback(
        source="directory",
        status="ingested",
        summary="记住文件 支出清单.xlsx",
        evidence_id="evd_x",
        knowledge_id="knw_y",
        ts=1756080000,
    )
    # 日志已写（短同步写，watch 线程语义）
    events = store.list_events()
    assert len(events) == 1
    assert events[0]["summary"] == "记住文件 支出清单.xlsx"
    assert events[0]["evidence_id"] == "evd_x"
    # 广播被调度回主循环（回调本身不阻塞）
    assert len(fake_loop.scheduled) == 1


def test_capture_callback_still_logs_without_main_loop(tmp_path, monkeypatch):
    store = MonitorLogStore(str(tmp_path / "m.db"))
    monkeypatch.setattr(di_module, "_main_loop", None)

    callback = di_module._make_capture_callback(store)
    callback(source="directory", status="ignored", summary="忽略不支持的文件 x", ts=1)
    assert len(store.list_events()) == 1


def test_capture_callback_survives_log_write_error(tmp_path, monkeypatch):
    class _BrokenStore:
        def write_event(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(di_module, "_main_loop", _FakeLoop())
    callback = di_module._make_capture_callback(_BrokenStore())
    callback(source="directory", status="ingested", summary="x", ts=1)  # 不应抛出


# ═══════════════════════════════════════════════════════
# _lifespan 接线：PIXIU_MONITOR_ENABLED 时启动/停止 monitor runtime
# ═══════════════════════════════════════════════════════

def test_monitor_runtime_starts_and_stops_with_lifespan(tmp_path, monkeypatch):
    fake = _FakeSettings(str(tmp_path / "pixiu.db"))
    fake.monitor_enabled = True
    monkeypatch.setattr(di_module, "settings", fake)
    _reset_di_singletons()
    try:
        with TestClient(app) as c:
            assert di_module._monitor_runtime is not None
            assert di_module._monitor_runtime._running is True
            # runtime 启动不阻塞既有端点
            assert c.get("/monitor/config").status_code == 200
        # 退出 lifespan 后 runtime 已停止并释放
        assert di_module._monitor_runtime is None
    finally:
        _reset_di_singletons()
