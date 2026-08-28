"""Tests for monitor/watcher.py + monitor/ingest_bridge.py — 目录监视采集闭环。

使用 tmp_path + 真实 watchdog Observer 的集成测试（非 mock 事件），覆盖：
  - PNG + mock OCR → MANUAL 风格入库（evidence + knowledge）→ ingested 事件；
  - TXT 文本入库；
  - .tmp / .part / ~ / 隐藏文件 → 完全忽略（无事件无入库）；
  - 总闸关 / 目录源关 → 不捕获；
  - 敏感内容（手机号）→ detector 判定 → sensitive_quarantined + sensitivity 落库；
  - 不支持后缀 → ignored 事件；
  - 配置热更新（store.put 后热生效）；
  - 单文件异常隔离：一个文件失败不中断后续捕获；
  - 写入过程防抖 + 稳定性检查（连续追加只捕获一次）。
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

import aiosqlite
import pytest
import pytest_asyncio

from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.security import SecurityService
from backend.engine.tests.fakes import StubTextEmbedder
from backend.foundation.monitor import DirectoryWatcher, IngestBridge, MonitorConfigStore
from backend.foundation.storage.repository import (
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
)
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


class FakeOcr:
    """测试用 OCR 桩：固定返回识别行（生产环境为 engine/kylin ocr adapter）。"""

    def __init__(self, lines: list[str] | None = None) -> None:
        self.lines = list(lines or [])
        self.calls: list[str] = []

    def recognize(self, image_path, nums: int = 4) -> list[str]:
        self.calls.append(str(image_path))
        return list(self.lines)


# ─── Fixtures ─────────────────────────────────────────────

@pytest_asyncio.fixture
async def env(tmp_path: Path):
    """真实 SQLite 库 + 真实 Service 栈（StubTextEmbedder）+ MonitorConfigStore。"""
    db_path = str(tmp_path / "pixiu.db")
    # 建表连接是一次性测试用：关掉 fsync（synchronous=OFF）避免每条 DDL 落盘，
    # 使 fixture 初始化 ~0.2s 而非 ~7s；不影响随后 aiosqlite 连接的正确性。
    sync_conn = sqlite3.connect(db_path)
    sync_conn.execute("PRAGMA synchronous=OFF")
    init_db_on_connection(sync_conn)
    sync_conn.close()

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")

    evidence_repo = SqliteEvidenceRepo(db)
    knw_repo = SqliteKnowledgeRepo(db)
    entity_repo = SqliteEntityRepo(db)
    env = SimpleNamespace(
        db=db,
        db_path=db_path,
        watched=str(tmp_path / "watched"),
        evidence_repo=evidence_repo,
        knw_repo=knw_repo,
        services={
            "ingestion": IngestionService(evidence_repo=evidence_repo),
            "knowledge": KnowledgeService(
                knw_repo=knw_repo,
                entity_repo=entity_repo,
                embedder=StubTextEmbedder(dim=32),
            ),
            "security": SecurityService(knw_repo=knw_repo, entity_repo=entity_repo),
        },
        store=MonitorConfigStore(db_path),
    )
    Path(env.watched).mkdir(parents=True, exist_ok=True)
    try:
        yield env
    finally:
        await db.close()


def _bridge(env, *, ocr: FakeOcr | None = None, security: bool = True) -> IngestBridge:
    return IngestBridge(
        env.services["ingestion"],
        env.services["knowledge"],
        security=env.services["security"] if security else None,
        ocr=ocr,
        scope="user:local",
    )


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


# ─── PNG + mock OCR ───────────────────────────────────────

@pytest.mark.asyncio
async def test_png_ocr_captured_and_ingested(env):
    await env.store.put(_config(env))
    ocr = FakeOcr(["电费 210 元", "水费 80 元"])
    events: list[dict] = []
    watcher = DirectoryWatcher(
        env.store, _bridge(env, ocr=ocr), debounce_ms=200, callbacks=[]
    )
    watcher.register_callback(lambda *a, **kw: events.append(kw))
    watcher.start()
    try:
        time.sleep(0.6)  # 等 observer 挂上监视点
        target = Path(env.watched) / "支出清单.png"
        target.write_bytes(b"\x89PNG fake image bytes")

        assert _wait_until(lambda: events), "on_capture 未触发"
        event = events[0]
        assert event["source"] == "directory"
        assert event["status"] == "ingested"
        assert event["summary"] == "记住文件 支出清单.png"
        assert event["evidence_id"].startswith("evd_")
        assert event["knowledge_id"].startswith("knw_")
        assert isinstance(event["ts"], int) and event["ts"] > 0

        # OCR 直调的是同一文件路径
        assert ocr.calls and ocr.calls[0] == str(target)

        # 证据与知识已入库
        evidence = await env.evidence_repo.get(event["evidence_id"])
        assert evidence is not None
        assert evidence.source_type.value == "MANUAL_CONFIG"
        assert evidence.scope == "user:local"
        assert "电费 210 元" in evidence.raw["body"]["text"]
        item = await env.knw_repo.get(event["knowledge_id"])
        assert item is not None
        assert item.title == "支出清单.png"
    finally:
        watcher.stop()


# ─── TXT 文本入库 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_txt_file_ingested(env):
    await env.store.put(_config(env))
    events: list[dict] = []
    watcher = DirectoryWatcher(
        env.store, _bridge(env), debounce_ms=200, callbacks=[]
    )
    watcher.register_callback(lambda *a, **kw: events.append(kw))
    watcher.start()
    try:
        time.sleep(0.6)
        (Path(env.watched) / "启动说明.txt").write_text(
            "项目启动步骤：1. 安装依赖 2. 初始化数据库", encoding="utf-8"
        )
        assert _wait_until(lambda: events), "on_capture 未触发"
        event = events[0]
        assert event["status"] == "ingested"
        assert event["summary"] == "记住文件 启动说明.txt"
        evidence = await env.evidence_repo.get(event["evidence_id"])
        assert evidence is not None
        assert "安装依赖" in evidence.raw["body"]["text"]
        assert evidence.raw["title"] == "启动说明.txt"
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
        evidence_rows = await env.db.execute_fetchall("SELECT id FROM evidence")
        assert evidence_rows == []
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
        rows = await env.db.execute_fetchall("SELECT id FROM evidence")
        assert rows == []
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
        rows = await env.db.execute_fetchall("SELECT id FROM evidence")
        assert rows == []
    finally:
        watcher.stop()


# ─── 敏感内容 → sensitive_quarantined ─────────────────────

@pytest.mark.asyncio
async def test_sensitive_text_quarantined(env):
    await env.store.put(_config(env))
    events: list[dict] = []
    watcher = DirectoryWatcher(
        env.store, _bridge(env), debounce_ms=200, callbacks=[]
    )
    watcher.register_callback(lambda *a, **kw: events.append(kw))
    watcher.start()
    try:
        time.sleep(0.6)
        (Path(env.watched) / "通讯录.txt").write_text(
            "联系人 张三 手机 13812345678", encoding="utf-8"
        )
        assert _wait_until(lambda: events), "on_capture 未触发"
        event = events[0]
        assert event["status"] == "sensitive_quarantined"
        # summary 不得含敏感原文全文（手机号）
        assert "13812345678" not in event["summary"]
        assert "通讯录.txt" in event["summary"]
        evidence = await env.evidence_repo.get(event["evidence_id"])
        assert evidence is not None
        assert evidence.sensitivity >= 2  # 手机号 敏感度 2
    finally:
        watcher.stop()


# ─── 不支持后缀 → ignored 事件（不入库） ──────────────────

@pytest.mark.asyncio
async def test_unsupported_extension_ignored_event(env):
    await env.store.put(_config(env))
    events: list[dict] = []
    watcher = DirectoryWatcher(
        env.store, _bridge(env), debounce_ms=200, callbacks=[]
    )
    watcher.register_callback(lambda *a, **kw: events.append(kw))
    watcher.start()
    try:
        time.sleep(0.6)
        (Path(env.watched) / "预算.xlsx").write_bytes(b"PK fake xlsx")
        assert _wait_until(lambda: events), "on_capture 未触发"
        event = events[0]
        assert event["status"] == "ignored"
        assert event["evidence_id"] is None
        assert event["knowledge_id"] is None
        rows = await env.db.execute_fetchall("SELECT id FROM evidence")
        assert rows == []
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

    class FlakyOcr(FakeOcr):
        def recognize(self, image_path, nums: int = 4) -> list[str]:
            self.calls.append(str(image_path))
            if "坏图" in str(image_path):
                raise OSError("broken image")
            return ["正常识别文本"]

    events: list[dict] = []
    ocr = FlakyOcr()
    watcher = DirectoryWatcher(
        env.store, _bridge(env, ocr=ocr), debounce_ms=200, callbacks=[]
    )
    watcher.register_callback(lambda *a, **kw: events.append(kw))
    watcher.start()
    try:
        time.sleep(0.6)
        (Path(env.watched) / "坏图.png").write_bytes(b"broken")
        # 等坏图进入处理（OCR 被调起，失败被吞掉、不产生事件）
        assert _wait_until(lambda: len(ocr.calls) >= 1), "坏图未进入处理"
        time.sleep(1.5)
        # 后续文件仍可正常捕获
        (Path(env.watched) / "好图.png").write_bytes(b"good")
        assert _wait_until(lambda: events), "坏图失败后 watcher 仍在工作"
        assert events[0]["status"] == "ingested"
        assert events[0]["summary"] == "记住文件 好图.png"
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
        captured = [e for e in events if e["summary"] == "记住文件 连载.txt"]
        assert len(captured) == 1, f"写入过程应合并为一次捕获: {events}"
        evidence = await env.evidence_repo.get(captured[0]["evidence_id"])
        assert evidence is not None
        assert "第三段" in evidence.raw["body"]["text"], "应捕获到写完后的完整内容"
        rows = await env.db.execute_fetchall(
            "SELECT id FROM evidence WHERE source_type='MANUAL_CONFIG'"
        )
        assert len(rows) == 1
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
        rows = await env.db.execute_fetchall("SELECT id FROM evidence")
        assert rows == []

        # 空 .txt：_read_text 返回空 → ignored 事件，不入库（不产生空证据）
        (Path(env.watched) / "空文件.txt").write_text("", encoding="utf-8")
        assert _wait_until(lambda: events), "空文件应产生 ignored 事件"
        event = events[0]
        assert event["status"] == "ignored"
        assert event["summary"] == "忽略无法读取的文件 空文件.txt"
        assert event["evidence_id"] is None
        assert event["knowledge_id"] is None
        rows = await env.db.execute_fetchall("SELECT id FROM evidence")
        assert rows == []
    finally:
        watcher.stop()