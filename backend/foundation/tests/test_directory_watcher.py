"""Real watchdog tests: file stability, configuration, service dispatch and lifecycle.

Document decoding and actual memory writes are tested through the document API
and dreaming harness; this suite exercises the watcher boundary.
"""
from __future__ import annotations
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from backend.foundation.monitor import DirectoryWatcher, MonitorConfigStore, CaptureResult
from backend.foundation.storage.schema import init_db_on_connection

WATCHED_DIR_ENABLED = {
    "enabled": True,
    "sources": {
        "directory": True,
        "clipboard": False,
        "behavior": False,
        "screenshot": False,
    },
    "directories": [],
}


class FakeDreaming:
    def __init__(self):
        self.calls = []
        self.contents = []

    async def capture(self, path):
        self.calls.append(path)
        content = Path(path).read_bytes()
        self.contents.append(content)
        return CaptureResult("ingested" if content else "ignored", Path(path).name, ts=int(time.time()))


@pytest.fixture
def env(tmp_path):
    db_path = str(tmp_path / "pixiu.db")
    with sqlite3.connect(db_path) as connection:
        init_db_on_connection(connection)
    watched = tmp_path / "watched"
    watched.mkdir()
    return SimpleNamespace(watched=str(watched), store=MonitorConfigStore(db_path), capture=FakeDreaming())


def _bridge(env):
    return env.capture


def _config(env, *, enabled: bool = True, directory: bool = True) -> dict:
    cfg = dict(WATCHED_DIR_ENABLED)
    cfg["enabled"] = enabled
    cfg["sources"] = dict(WATCHED_DIR_ENABLED["sources"])
    cfg["sources"]["directory"] = directory
    cfg["directories"] = [env.watched]
    return cfg


def _wait_until(predicate, timeout: float = 8.0, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["photo.png", "note.txt", "budget.xlsx", "slides.ppt"])
async def test_supported_files_are_dispatched_to_dreaming(env, name):
    await env.store.put(_config(env))
    events = []
    watcher = DirectoryWatcher(env.store, env.capture, debounce_ms=200)
    watcher.register_callback(lambda *a, **kw: events.append(kw))
    watcher.start()
    try:
        time.sleep(0.6)
        target = Path(env.watched) / name
        target.write_bytes(b"document contents")
        assert _wait_until(lambda: events)
        assert env.capture.calls == [str(target)]
        assert events[0]["source"] == "directory"
        assert events[0]["status"] == "ingested"
        assert events[0]["summary"] == name
    finally:
        watcher.stop()


# ─── 临时/隐藏文件忽略（不发事件、不入库） ───────────────

@pytest.mark.asyncio
async def test_temp_and_hidden_files_ignored_completely(env):
    await env.store.put(_config(env))
    events: list[dict] = []
    watcher = DirectoryWatcher(
        env.store, _bridge(env), debounce_ms=200, callbacks=[]
    )
    watcher.register_callback(lambda *a, **kw: events.append(kw))
    watcher.start()
    try:
        time.sleep(0.6)
        (Path(env.watched) / "notes.txt.tmp").write_text("temp content")
        (Path(env.watched) / "backup.part").write_text("partial")
        (Path(env.watched) / "emacs-note~").write_text("emacs temp")
        (Path(env.watched) / ".hidden.txt").write_text("hidden")
        time.sleep(2.0)  # 足够跨过防抖 + 稳定性窗口
        assert events == [], f"临时/隐藏文件不应触发捕获: {events}"
        assert env.capture.calls == []
    finally:
        watcher.stop()


# ─── 总闸/目录源关闭不捕获 ────────────────────────────────

@pytest.mark.asyncio
async def test_master_switch_off_no_capture(env):
    await env.store.put(_config(env, enabled=False))
    events: list[dict] = []
    watcher = DirectoryWatcher(
        env.store, _bridge(env), debounce_ms=200, callbacks=[]
    )
    watcher.register_callback(lambda *a, **kw: events.append(kw))
    watcher.start()
    try:
        time.sleep(0.6)
        (Path(env.watched) / "off.txt").write_text("should not be captured")
        time.sleep(2.0)
        assert events == []
        assert env.capture.calls == []
    finally:
        watcher.stop()


@pytest.mark.asyncio
async def test_directory_source_off_no_capture(env):
    await env.store.put(_config(env, enabled=True, directory=False))
    events: list[dict] = []
    watcher = DirectoryWatcher(
        env.store, _bridge(env), debounce_ms=200, callbacks=[]
    )
    watcher.register_callback(lambda *a, **kw: events.append(kw))
    watcher.start()
    try:
        time.sleep(0.6)
        (Path(env.watched) / "src-off.txt").write_text("should not be captured")
        time.sleep(2.0)
        assert events == []
        assert env.capture.calls == []
    finally:
        watcher.stop()


# ─── 配置热更新：put 后立即生效 ───────────────────────────

@pytest.mark.asyncio
async def test_hot_reload_enables_after_put(env):
    await env.store.put(_config(env, enabled=False))
    events: list[dict] = []
    watcher = DirectoryWatcher(
        env.store, _bridge(env), debounce_ms=200, callbacks=[]
    )
    watcher.register_callback(lambda *a, **kw: events.append(kw))
    watcher.start()
    try:
        time.sleep(0.6)
        await env.store.put(_config(env, enabled=True))
        time.sleep(0.5)
        (Path(env.watched) / "hot.txt").write_text("captured after hot reload")
        assert _wait_until(lambda: events), "热更新后应能捕获"
        assert events[0]["status"] == "ingested"
    finally:
        watcher.stop()


# ─── 单文件异常隔离：失败不中断监视 ───────────────────────

@pytest.mark.asyncio
async def test_failing_file_does_not_stop_monitoring(env):
    await env.store.put(_config(env))

    class FlakyDreaming(FakeDreaming):
        async def capture(self, image_path):
            self.calls.append(str(image_path))
            if "坏图" in str(image_path):
                raise OSError("broken image")
            return CaptureResult("ingested", Path(image_path).name, ts=int(time.time()))

    events: list[dict] = []
    capture = FlakyDreaming()
    watcher = DirectoryWatcher(
        env.store, capture, debounce_ms=200, callbacks=[]
    )
    watcher.register_callback(lambda *a, **kw: events.append(kw))
    watcher.start()
    try:
        time.sleep(0.6)
        (Path(env.watched) / "坏图.png").write_bytes(b"broken")
        # 等坏图进入处理（dreaming 被调起，失败被吞掉、不产生事件）
        assert _wait_until(lambda: len(capture.calls) >= 1), "坏图未进入处理"
        time.sleep(1.5)
        # 后续文件仍可正常捕获
        (Path(env.watched) / "好图.png").write_bytes(b"good")
        assert _wait_until(lambda: events), "坏图失败后 watcher 仍在工作"
        assert events[0]["status"] == "ingested"
        assert events[0]["summary"] == "好图.png"
    finally:
        watcher.stop()


# ─── 防抖 + 稳定性：连续追加只捕获一次 ────────────────────

@pytest.mark.asyncio
async def test_debounce_merges_concurrent_writes_into_single_capture(env):
    await env.store.put(_config(env))
    events: list[dict] = []
    watcher = DirectoryWatcher(
        env.store, _bridge(env), debounce_ms=200, callbacks=[]
    )
    watcher.register_callback(lambda *a, **kw: events.append(kw))
    watcher.start()
    try:
        time.sleep(0.6)
        target = Path(env.watched) / "连载.txt"
        with target.open("w", encoding="utf-8") as handle:
            for chunk in ("第一段\n", "第二段\n", "第三段\n"):
                handle.write(chunk)
                handle.flush()
                time.sleep(0.15)  # 写入过程持续产生 modify 事件
        assert _wait_until(lambda: events), "on_capture 未触发"
        time.sleep(1.0)
        captured = [e for e in events if e["summary"] == "连载.txt"]
        assert len(captured) == 1, f"写入过程应合并为一次捕获: {events}"
        assert len(env.capture.calls) == 1
        assert "第三段" in env.capture.contents[0].decode()
    finally:
        watcher.stop()


# ─── I1 回归：start() 失败路径不泄漏 loop/线程，可重启 ─────

@pytest.mark.asyncio
async def test_start_failure_cleans_up_and_allows_restart(env):
    class FailingStore:
        """subscribe 抛错的 config store：触发 start() 失败清理路径。"""

        def subscribe(self, _cb):
            raise RuntimeError("subscribe boom")

    watcher = DirectoryWatcher(FailingStore(), _bridge(env), debounce_ms=200)
    watcher.start()  # 失败在内部 try/except 清理，不抛给调用方
    assert watcher._running is False
    assert watcher._loop is None, "失败后不应残留事件循环引用"
    assert watcher._thread is None, "失败后不应残留 watch 线程引用"
    assert watcher._queue is None
    assert watcher._observer is None
    watcher.stop()  # 已清理：stop 为 no-op，不抛错

    # 生命周期契约保持：清理后可再次 start 并正常捕获
    await env.store.put(_config(env))
    events: list[dict] = []
    watcher2 = DirectoryWatcher(
        env.store, _bridge(env), debounce_ms=200, callbacks=[]
    )
    watcher2.register_callback(lambda *a, **kw: events.append(kw))
    watcher2.start()
    assert watcher2._running is True
    try:
        time.sleep(0.6)
        (Path(env.watched) / "restart.txt").write_text(
            "captured after restart", encoding="utf-8"
        )
        assert _wait_until(lambda: events), "失败清理后重新 start 应可正常捕获"
        assert events[0]["status"] == "ingested"
    finally:
        watcher2.stop()


# ─── I2 回归：移入目录 / 空文件 → ignored，不入库空证据 ───

@pytest.mark.asyncio
async def test_directory_move_and_empty_file_not_ingested(env):
    await env.store.put(_config(env))
    events: list[dict] = []
    watcher = DirectoryWatcher(
        env.store, _bridge(env), debounce_ms=200, callbacks=[]
    )
    watcher.register_callback(lambda *a, **kw: events.append(kw))
    watcher.start()
    try:
        time.sleep(0.6)
        # 目录（名为 .txt）移入监视目录：on_moved 必须过滤 is_directory，
        # 不产生捕获事件、不入库（否则 read_text 抛 IsADirectoryError → 空证据）
        outside = Path(env.watched).parent / "outside_dir"
        outside.mkdir(exist_ok=True)
        (outside / "inner.txt").write_text("inner", encoding="utf-8")
        outside.rename(Path(env.watched) / "伪文本.txt")
        time.sleep(2.0)  # 跨过防抖 + 稳定性窗口
        assert events == [], f"移入目录不应触发捕获: {events}"
        assert env.capture.calls == []

        # 空文件由服务返回 ignored，监视器保留该状态。
        (Path(env.watched) / "空文件.txt").write_text("", encoding="utf-8")
        assert _wait_until(lambda: events), "空文件应产生 ignored 事件"
        event = events[0]
        assert event["status"] == "ignored"
        assert event["summary"] == "空文件.txt"
        assert event["evidence_id"] is None
        assert event["knowledge_id"] is None
        assert env.capture.calls == [str(Path(env.watched) / "空文件.txt")]
    finally:
        watcher.stop()
