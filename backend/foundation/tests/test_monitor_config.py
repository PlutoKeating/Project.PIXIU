"""Tests for monitor/config_store.py — MonitorConfigStore（持久化 + 校验 + 热生效订阅）。

覆盖：默认值 / roundtrip / 跨实例持久化 / source 白名单与假值拒收 /
enabled 类型 / directories 去空去白去重归一化拒相对路径 /
订阅回调（同步 + 异步 + 异常隔离）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.foundation.monitor import MonitorConfigStore
from backend.foundation.monitor.config_store import InvalidMonitorConfig

SOURCE_NAMES = ["directory", "clipboard", "behavior", "screenshot"]

DEFAULT_CONFIG = {
    "enabled": False,
    "sources": {name: False for name in SOURCE_NAMES},
    "directories": [],
}

VALID_CONFIG = {
    "enabled": True,
    "sources": {
        "directory": True,
        "clipboard": True,
        "behavior": False,
        "screenshot": False,
    },
    "directories": ["/tmp/monitor-a", "/tmp/monitor-b"],
}


# ─── Fixtures ─────────────────────────────────────────────

@pytest.fixture
def store(db_path: str) -> MonitorConfigStore:
    return MonitorConfigStore(db_path)


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "monitor.db")


# ─── 默认值与读取 ────────────────────────────────────────

def test_default_config_when_unset(store: MonitorConfigStore):
    """未写入过配置时应返回默认值（全 false + 空目录）。"""
    assert store.get() == DEFAULT_CONFIG


# ─── Roundtrip 与持久化 ──────────────────────────────────

@pytest.mark.asyncio
async def test_roundtrip_put_get(store: MonitorConfigStore):
    stored = await store.put(VALID_CONFIG)
    assert stored == VALID_CONFIG
    assert store.get() == VALID_CONFIG


@pytest.mark.asyncio
async def test_put_overwrites_previous(store: MonitorConfigStore):
    await store.put(VALID_CONFIG)
    replacement = dict(VALID_CONFIG, enabled=False, directories=["/only"])
    stored = await store.put(replacement)
    assert stored == replacement
    assert store.get() == replacement


@pytest.mark.asyncio
async def test_persists_across_instances(db_path: str):
    """同一 db 文件上的新 store 实例应读到已持久化的配置（跨实例恢复）。"""
    first = MonitorConfigStore(db_path)
    await first.put(VALID_CONFIG)

    second = MonitorConfigStore(db_path)
    assert second.get() == VALID_CONFIG


# ─── sources 白名单校验 ──────────────────────────────────

@pytest.mark.asyncio
async def test_unknown_source_key_rejected(store: MonitorConfigStore):
    with pytest.raises(InvalidMonitorConfig, match="camera"):
        await store.put({"sources": {"directory": True, "camera": True}})


@pytest.mark.asyncio
async def test_source_value_must_be_bool(store: MonitorConfigStore):
    with pytest.raises(InvalidMonitorConfig, match="directory"):
        await store.put({"sources": {"directory": "yes"}})


@pytest.mark.asyncio
async def test_sources_falsy_non_dict_rejected(store: MonitorConfigStore):
    """sources 为 [] / "" 等假值不得静默当缺省（I3 回归），必须按类型拒收。"""
    for bad in ([], "", 0):
        with pytest.raises(InvalidMonitorConfig, match="dict"):
            await store.put({"sources": bad})


# ─── enabled 校验 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_enabled_must_be_bool(store: MonitorConfigStore):
    for bad in (1, 0, "yes", "false"):
        with pytest.raises(InvalidMonitorConfig, match="enabled"):
            await store.put({"enabled": bad})


# ─── 缺省键回填默认值 ────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_keys_fill_defaults(store: MonitorConfigStore):
    stored = await store.put({"enabled": True})
    assert stored == {"enabled": True, "sources": DEFAULT_CONFIG["sources"], "directories": []}


@pytest.mark.asyncio
async def test_empty_dict_put_yields_defaults(store: MonitorConfigStore):
    stored = await store.put({})
    assert stored == DEFAULT_CONFIG


# ─── directories 清理：去空/去重/拒相对路径 ──────────────

@pytest.mark.asyncio
async def test_directories_drop_empty_and_whitespace(store: MonitorConfigStore):
    stored = await store.put({"directories": ["", "   ", "\t\n", "/a"]})
    assert stored["directories"] == ["/a"]


@pytest.mark.asyncio
async def test_directories_dedupe_preserve_order(store: MonitorConfigStore):
    stored = await store.put({"directories": ["/b", "/a", "/b", "/a"]})
    assert stored["directories"] == ["/b", "/a"]


@pytest.mark.asyncio
async def test_directories_reject_relative_path(store: MonitorConfigStore):
    with pytest.raises(InvalidMonitorConfig, match="absolute"):
        await store.put({"directories": ["/abs", "relative/path"]})


@pytest.mark.asyncio
async def test_directories_must_be_strings(store: MonitorConfigStore):
    with pytest.raises(InvalidMonitorConfig, match="string"):
        await store.put({"directories": ["/abs", 42]})


@pytest.mark.asyncio
async def test_directories_whitespace_stripped(store: MonitorConfigStore):
    """目录条目先 strip 归一化再存储（M2）：首尾空白不影响绝对路径判定。"""
    stored = await store.put({"directories": [" /tmp/a ", "\t/tmp/b\n"]})
    assert stored["directories"] == ["/tmp/a", "/tmp/b"]


@pytest.mark.asyncio
async def test_directories_dedupe_after_strip(store: MonitorConfigStore):
    """strip 后去重（M2 回归）：前后空白差异不得漏判重复，归一化后 size==1。"""
    stored = await store.put({"directories": [" /a ", "/a"]})
    assert stored["directories"] == ["/a"]


# ─── 订阅回调（热生效） ──────────────────────────────────

@pytest.mark.asyncio
async def test_subscribe_callback_receives_new_config(store: MonitorConfigStore):
    received: list[dict] = []
    store.subscribe(lambda cfg: received.append(cfg))
    returned = await store.put(VALID_CONFIG)
    assert received == [returned]
    assert received[0] == VALID_CONFIG


@pytest.mark.asyncio
async def test_subscribe_async_callback_awaited(store: MonitorConfigStore):
    received: list[dict] = []

    async def on_change(cfg: dict) -> None:
        received.append(cfg)

    store.subscribe(on_change)
    returned = await store.put(VALID_CONFIG)
    assert received == [returned]


@pytest.mark.asyncio
async def test_subscribe_multiple_callbacks_all_called(store: MonitorConfigStore):
    first: list[dict] = []
    second: list[dict] = []
    store.subscribe(lambda cfg: first.append(cfg))
    store.subscribe(lambda cfg: second.append(cfg))
    await store.put(VALID_CONFIG)
    assert first == [VALID_CONFIG]
    assert second == [VALID_CONFIG]


@pytest.mark.asyncio
async def test_callbacks_not_called_on_invalid_put(store: MonitorConfigStore):
    called: list[dict] = []
    store.subscribe(lambda cfg: called.append(cfg))
    with pytest.raises(InvalidMonitorConfig):
        await store.put({"sources": {"bogus": True}})
    assert called == []


@pytest.mark.asyncio
async def test_callback_exception_does_not_break_put(store: MonitorConfigStore):
    """单个回调抛异常不应中断其它回调，也不应让 put 失败。"""
    called: list[dict] = []

    def failing(_cfg: dict) -> None:
        raise RuntimeError("boom")

    store.subscribe(failing)
    store.subscribe(lambda cfg: called.append(cfg))
    returned = await store.put(VALID_CONFIG)
    assert returned == VALID_CONFIG
    assert called == [VALID_CONFIG]