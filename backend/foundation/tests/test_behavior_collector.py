"""行为采集器（BehaviorCollector）测试：焦点轮询、聚合、门控、敏感丢弃、无 X 降级。

对齐 docs/compose/specs/2026-08-29-batch3-behavior-preference-conflict-design.md [S2.1]：
  - 只采集窗口焦点（应用名+标题）与应用活跃时长（隐私边界：不记键击/截屏/聊天内容）；
  - 60s 聚合产出 {"app","title","focus_seconds","hour_bucket","day_type"} evidence；
  - enabled && sources["behavior"] 双门控（仿 watcher effective）；
  - 标题经既有 security detector 判定，sensitivity>0 不落库（比 ingest_bridge 更严格）；
    detector 异常时无法确认非敏感，fail-closed 直接丢弃（不落库）；
  - 无 X 环境（xprop 失败）降级记录日志不采集、不崩溃。

测试直调 _aggregate/_poll_focus/_flush 等内部方法，绕开 1s 轮询线程，保证确定性。
"""

from __future__ import annotations

import subprocess

import pytest

import backend.foundation.monitor.behavior as behavior_module
from backend.foundation.monitor.behavior import (
    BEHAVIOR_SCOPE,
    SOURCE_TYPE_BEHAVIOR,
    BehaviorCollector,
)


class _FakeConfig:
    def __init__(self, enabled: bool = True, behavior: bool = True) -> None:
        self._cfg = {"enabled": enabled, "sources": {"behavior": behavior}}

    def get(self) -> dict:
        return self._cfg


class _FakeIngestion:
    def __init__(self) -> None:
        self.evidence: list[tuple] = []

    async def ingest(self, source_type, raw, scope, *, sensitivity=0):
        self.evidence.append((source_type, raw, scope, sensitivity))
        return type(
            "E",
            (),
            {"id": f"evd_{len(self.evidence)}", "source_type": source_type, "raw": raw},
        )()


class _FakeKnowledge:
    def __init__(self) -> None:
        self.items: list = []

    async def structure(self, evidence):
        self.items.append(evidence)
        return type("K", (), {"id": f"knw_{len(self.items)}"})()


class _FakeSecurity:
    def __init__(self, sensitivity: int = 0) -> None:
        self._sensitivity = sensitivity
        self.calls: list[dict] = []

    async def detect_sensitivity(self, raw: dict) -> int:
        self.calls.append(raw)
        return self._sensitivity


def _make_collector(**kw):
    cfg = _FakeConfig(**kw)
    ing = _FakeIngestion()
    know = _FakeKnowledge()
    return BehaviorCollector(cfg, ing, know, security=None), cfg, ing, know


# ═══════════════════════════════════════════════════════
# 聚合 → behavior evidence 形状
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_aggregates_focus_into_behavior_evidence():
    collector, cfg, ing, know = _make_collector()
    await collector._aggregate("org.kylin.files", "支出清单", 42)
    assert ing.evidence
    source_type, raw, scope, sens = ing.evidence[-1]
    assert source_type == SOURCE_TYPE_BEHAVIOR
    assert raw["app"] == "org.kylin.files"
    assert raw["title"] == "支出清单"
    assert raw["focus_seconds"] == 42
    assert raw["hour_bucket"] in range(24)
    assert raw["day_type"] in ("workday", "weekend")
    assert scope == BEHAVIOR_SCOPE
    assert sens == 0
    # 聚合载荷内嵌 events 载体：USER_BEHAVIOR connector 只透传 title/events，
    # 保证 ingest→structure 后 evidence.raw 仍完整保留（供 B3-2 偏好规则）
    assert raw["events"][0]["app"] == "org.kylin.files"
    assert raw["events"][0]["focus_seconds"] == 42
    # structure 被调用（复用 /memory/write 同进程管线）
    assert know.items


# ═══════════════════════════════════════════════════════
# 门控（enabled && sources["behavior"]）
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_gated_off_does_not_emit():
    collector, cfg, ing, _ = _make_collector(enabled=True, behavior=False)
    await collector._aggregate("org.kylin.files", "t", 10)
    assert not ing.evidence


@pytest.mark.asyncio
async def test_disabled_does_not_emit():
    collector, cfg, ing, _ = _make_collector(enabled=False, behavior=True)
    await collector._aggregate("org.kylin.files", "t", 10)
    assert not ing.evidence


# ═══════════════════════════════════════════════════════
# 敏感标题：sensitivity>0 直接丢弃（不落库）
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_sensitive_title_dropped():
    collector, cfg, ing, _ = _make_collector()
    collector._security = _FakeSecurity(sensitivity=2)
    await collector._aggregate("org.kylin.files", "含手机号 13800138000 的标题", 5)
    assert not ing.evidence


@pytest.mark.asyncio
async def test_insensitive_title_persisted():
    collector, cfg, ing, _ = _make_collector()
    collector._security = _FakeSecurity(sensitivity=0)
    await collector._aggregate("org.kylin.files", "支出清单", 5)
    assert ing.evidence
    assert ing.evidence[-1][3] == 0


@pytest.mark.asyncio
async def test_sensitivity_detect_failure_drops():
    class _BrokenSecurity:
        async def detect_sensitivity(self, raw):
            raise RuntimeError("detector boom")

    collector, cfg, ing, _ = _make_collector()
    collector._security = _BrokenSecurity()
    await collector._aggregate("org.kylin.files", "任何标题", 5)
    # detector 异常时无法确认标题非敏感：fail-closed 直接丢弃，不落库
    assert not ing.evidence


# ═══════════════════════════════════════════════════════
# 无效聚合值
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_zero_focus_seconds_skipped():
    collector, cfg, ing, _ = _make_collector()
    await collector._aggregate("org.kylin.files", "t", 0)
    assert not ing.evidence


# ═══════════════════════════════════════════════════════
# 焦点轮询与聚合（绕开线程，直接调内部方法）
# ═══════════════════════════════════════════════════════


def test_poll_focus_accumulates_seconds_on_switch(monkeypatch):
    collector, cfg, ing, _ = _make_collector()
    # 4 次轮询：t=1000/1001/1002 应用 A，t=1010 切到应用 B
    ticks = iter([1000.0, 1001.0, 1002.0, 1010.0])
    monkeypatch.setattr(behavior_module.time, "monotonic", lambda: next(ticks))
    reads = iter(
        [
            ("org.kylin.files", "支出清单"),
            ("org.kylin.files", "支出清单"),
            ("org.kylin.files", "支出清单"),
            ("org.kylin.office", "报告"),
        ]
    )
    monkeypatch.setattr(collector, "_read_focus", lambda: next(reads))
    for _ in range(4):
        collector._poll_focus()
    # 切换到 B 时结算 A 的完整活跃时长 1010-1000 = 10s（非每次轮询的 1s）
    assert collector._focus.get("org.kylin.files") == 10.0
    assert collector._current_app == "org.kylin.office"
    # 标题随聚合态保留（_flush 落库时读取）
    assert collector._titles.get("org.kylin.files") == "支出清单"
    assert collector._titles.get("org.kylin.office") == "报告"


def test_poll_focus_settles_duration_on_focus_loss(monkeypatch):
    collector, cfg, ing, _ = _make_collector()
    # A(1000) → 焦点丢失 None(1010) → B(1020)：切到 None 时结算 A 的时长，
    # 不能把整段活跃时长静默丢弃（C1：_focus 应保留 A 的 10s）。
    ticks = iter([1000.0, 1010.0, 1020.0])
    monkeypatch.setattr(behavior_module.time, "monotonic", lambda: next(ticks))
    reads = iter(
        [
            ("org.kylin.files", "支出清单"),
            (None, ""),
            ("org.kylin.office", "报告"),
        ]
    )
    monkeypatch.setattr(collector, "_read_focus", lambda: next(reads))
    for _ in range(3):
        collector._poll_focus()
    assert collector._focus.get("org.kylin.files") == 10.0
    assert collector._current_app == "org.kylin.office"
    assert collector._current_title == "报告"


def test_poll_to_flush_persists_title(monkeypatch):
    collector, cfg, ing, _ = _make_collector()
    # 注意：monotonic 桩可能被 asyncio.run 的内部循环调用（_flush 内联执行），
    # 耗尽后回退到固定值，避免 StopIteration 破坏 asyncio 循环。
    counter = iter([1000.0, 1100.0])

    def _monotonic():
        try:
            return next(counter)
        except StopIteration:
            return 2000.0

    monkeypatch.setattr(behavior_module.time, "monotonic", _monotonic)
    reads = iter([("org.kylin.files", "支出清单"), ("org.kylin.office", "报告")])
    monkeypatch.setattr(collector, "_read_focus", lambda: next(reads))
    collector._poll_focus()
    collector._poll_focus()
    assert collector._focus.get("org.kylin.files") == 100.0
    collector._flush()
    assert ing.evidence
    source_type, raw, scope, sens = ing.evidence[0]
    assert source_type == SOURCE_TYPE_BEHAVIOR
    assert raw["app"] == "org.kylin.files"
    assert raw["title"] == "支出清单"
    assert raw["focus_seconds"] == 100


def test_poll_focus_gated_off_does_not_accumulate(monkeypatch):
    collector, cfg, ing, _ = _make_collector(enabled=True, behavior=False)
    monkeypatch.setattr(collector, "_read_focus", lambda: ("org.kylin.files", "t"))
    collector._poll_focus()
    assert collector._current_app is None
    assert collector._focus == {}


def test_flush_persists_aggregates():
    collector, cfg, ing, know = _make_collector()
    collector._focus = {"org.kylin.files": 60.0, "org.kylin.office": 30.0}
    collector._titles = {"org.kylin.files": "支出清单", "org.kylin.office": "报告"}
    # 无主循环句柄、当前线程无运行中循环：_schedule 走 asyncio.run 内联执行
    collector._flush()
    assert collector._focus == {}
    assert len(ing.evidence) == 2
    apps = {raw["app"] for _, raw, _, _ in ing.evidence}
    assert apps == {"org.kylin.files", "org.kylin.office"}
    assert know.items


def test_flush_gated_off_clears_without_persist():
    collector, cfg, ing, _ = _make_collector(enabled=True, behavior=False)
    collector._focus = {"org.kylin.files": 60.0}
    collector._flush()
    assert collector._focus == {}
    assert not ing.evidence


# ═══════════════════════════════════════════════════════
# 无 X 环境降级（xprop 失败 → 不采集、不崩溃）
# ═══════════════════════════════════════════════════════


def test_xprop_failure_degrades_without_crash(monkeypatch):
    collector, cfg, ing, _ = _make_collector()

    def _boom(*args, **kwargs):
        raise OSError("no X display")

    monkeypatch.setattr(subprocess, "run", _boom)
    app, title = collector._read_focus()
    assert app is None
    assert title == ""
    collector._poll_focus()  # 不应抛异常
    assert collector._current_app is None
    assert not ing.evidence


def test_xprop_timeout_degrades(monkeypatch):
    collector, cfg, ing, _ = _make_collector()

    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["xprop"], timeout=2)

    monkeypatch.setattr(subprocess, "run", _timeout)
    app, title = collector._read_focus()
    assert app is None
    assert title == ""


def test_xprop_no_active_window_returns_none(monkeypatch):
    collector, cfg, ing, _ = _make_collector()

    def _fake_run(*args, **kwargs):
        return type("R", (), {"stdout": "  \n"})

    monkeypatch.setattr(subprocess, "run", _fake_run)
    app, title = collector._read_focus()
    assert app is None
    assert title == ""


# ═══════════════════════════════════════════════════════
# xprop 输出解析（WM_CLASS / WM_NAME 健壮性）
# ═══════════════════════════════════════════════════════


def test_parse_wm_class_and_name():
    text = (
        'WM_CLASS(STRING) = "org.kylin.files", "org.kylin.files"\n'
        'WM_NAME(STRING) = "支出清单"\n'
    )
    assert behavior_module._parse_wm_class(text) == "org.kylin.files"
    assert behavior_module._parse_wm_name(text) == "支出清单"


def test_parse_wm_class_missing():
    assert behavior_module._parse_wm_class("WM_NAME(STRING) = \"x\"\n") is None
    assert behavior_module._parse_wm_name("WM_CLASS(STRING) = \"x\"\n") == ""


def test_parse_wm_class_not_found_is_missing():
    # xprop 缺失属性时打印 "not found."：解析为无应用名/无标题，
    # 不能变成幻影 app 键或幻影标题。
    text = "WM_CLASS(STRING) = not found.\nWM_NAME(STRING) = not found.\n"
    assert behavior_module._parse_wm_class(text) is None
    assert behavior_module._parse_wm_name(text) == ""


@pytest.mark.asyncio
async def test_no_title_window_skipped():
    collector, cfg, ing, _ = _make_collector()
    # S2.1：忽略无标题窗口——无标题不聚合落库
    await collector._aggregate("org.kylin.files", "", 5)
    assert not ing.evidence


def test_parse_active_window_id():
    text = "_NET_ACTIVE_WINDOW(WINDOW): window id # 0x3a00007\n"
    assert behavior_module._parse_active_window(text) == "0x3a00007"
    assert behavior_module._parse_active_window("no window\n") is None


# ═══════════════════════════════════════════════════════
# di 接线：get_behavior_collector 惰性装配真实服务
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_di_wiring_creates_collector_with_real_services(tmp_path, monkeypatch):
    import backend.foundation.api.di as di_module
    from backend.foundation.api.di import get_behavior_collector

    class _FakeSettings:
        def __init__(self, db_path: str) -> None:
            self.db_path = db_path
            self.embedding = "portable"
            self.vector_store = "portable"
            self.sync_device_name = "test-device"
            self.sync_domain = "shared:test"
            self.sync_key_passphrase = "phase3-di-test-passphrase"
            self.sync_network_enabled = False
            self.monitor_enabled = True

    monkeypatch.setattr(di_module, "settings", _FakeSettings(str(tmp_path / "pixiu.db")))
    di_module._db = None
    di_module._monitor_config_store = None
    di_module._behavior_collector = None
    try:
        collector = await get_behavior_collector()
        assert isinstance(collector, BehaviorCollector)
        # security 可选注入：di 装配真实 SecurityService
        assert collector._security is not None
        assert await get_behavior_collector() is collector  # 单例
    finally:
        di_module._db = None
        di_module._monitor_config_store = None
        di_module._behavior_collector = None
