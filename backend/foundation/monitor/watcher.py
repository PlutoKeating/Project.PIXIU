"""PIXIU Foundation — 目录监视采集器（DirectoryWatcher）

批次②「目录监视闭环」的采集端：watchdog Observer 监视配置目录
（recursive=False），对落盘文件做防抖 + 稳定性检查后经 IngestBridge
入库，并把结果以 ``on_capture`` 事件回调外发（BE-3 用它写 monitor_log +
WS 广播）。

线程模型（watch 线程）：
- watcher.start() 启动一个独立线程，线程内跑一个 asyncio 事件循环；
- watchdog Observer 独立线程把事件通过 call_soon_threadsafe 汇入该循环；
- config_store.get() 为同步短连接读（BE-1 特意为 watch 线程设计），
  配置热更新经 store.subscribe 回调 call_soon_threadsafe 汇入同循环，
  Observer 的 schedule/unschedule 只在 watch 线程执行；
- 每个文件独立 try/except，单个文件失败不影响后续捕获。

effective 开关：``config.enabled && config.sources["directory"]`` 才捕获
（在采集器层实现，store 不门控）。
"""

from __future__ import annotations

import asyncio
import inspect
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..core.logger import get_logger

log = get_logger(__name__)

#: 忽略规则：隐藏文件（. 开头）；临时后缀 .part/.tmp；~ 结尾备份文件。
IGNORED_NAME_PREFIXES = (".",)
IGNORED_NAME_SUFFIXES = (".part", ".tmp", "~")


def _is_ignored(path: str) -> bool:
    """隐藏文件 / 临时后缀 / 备份后缀判定（按文件名）。"""
    name = Path(path).name
    return name.startswith(IGNORED_NAME_PREFIXES) or name.endswith(
        IGNORED_NAME_SUFFIXES
    )


@dataclass
class _PathState:
    """单路径稳定性采样状态。"""

    prev_sample: tuple[int, int] | None = None
    checks: int = 0
    in_flight: bool = False


class _FileEventHandler(FileSystemEventHandler):
    """把 watcher 关心的文件事件转交 watcher（目录事件/忽略规则在此过滤）。"""

    def __init__(self, watcher: "DirectoryWatcher") -> None:
        self._watcher = watcher

    def _maybe_note(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = str(getattr(event, "dest_path", event.src_path))
        if _is_ignored(path):
            return
        self._watcher._note_event(path)

    def on_created(self, event: FileSystemEvent) -> None:
        self._maybe_note(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._maybe_note(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        # 移入受监视目录等同新增（dest_path 为目标路径）；目录整体忽略，
        # 与 _maybe_note 一致（否则名为 note.txt 的目录会走 read_text → 空入库）。
        if event.is_directory:
            return
        dest = str(getattr(event, "dest_path", ""))
        if dest and not _is_ignored(dest):
            self._watcher._note_event(dest)

    def on_closed(self, event: FileSystemEvent) -> None:
        self._maybe_note(event)


class DirectoryWatcher:
    """目录监视采集器：watchdog 事件 → 防抖/稳定 → IngestBridge → on_capture。

    用法：
        watcher = DirectoryWatcher(config_store, ingest_bridge, callbacks=[cb])
        watcher.start()
        ...
        watcher.stop()

    事件回调签名（关键字参数，BE-3 契约）：
        cb(source, status, summary, evidence_id, knowledge_id, ts)
    回调可为同步或异步函数；单个回调异常只记日志，不影响其它回调。
    """

    def __init__(
        self,
        config_store: Any,
        ingest_bridge: Any,
        *,
        debounce_ms: float = 500,
        max_stable_attempts: int = 30,
        check_interval_ms: float = 50,
        callbacks: list[Callable[..., Any]] | None = None,
    ) -> None:
        self._config_store = config_store
        self._bridge = ingest_bridge
        self._debounce = debounce_ms / 1000.0
        #: 稳定性检查的最大尝试次数上限：到期仍未稳定也强制入库（防无限跟踪）。
        self._max_stable_attempts = max_stable_attempts
        self._check_interval = check_interval_ms / 1000.0
        self._callbacks: list[Callable[..., Any]] = list(callbacks or [])

        self._observer: Observer | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._queue: asyncio.Queue | None = None
        self._states: dict[str, _PathState] = {}
        self._last_event: dict[str, float] = {}
        self._watched: dict[str, Any] = {}  # directory -> Observer watch
        self._effective: bool = False
        self._running: bool = False
        self._loop_ready = threading.Event()

    # ─── 生命周期 ─────────────────────────────────────────

    def start(self) -> None:
        """启动监视线程 + watchdog Observer，并应用当前配置。

        线程启动后的 setup 包进 try/except：任何失败（含 loop 启动超时）
        都走 _abort_start 镜像 stop() 尾部清理，保证失败后不留孤儿
        loop/线程/队列（否则 stop() 因 ``not self._running`` 空转泄漏）。
        """
        if self._running:
            return
        self._running = True
        self._loop = asyncio.new_event_loop()
        self._queue = asyncio.Queue()
        self._loop_ready.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="pixiu-dirwatcher", daemon=True
        )
        self._thread.start()
        try:
            if not self._loop_ready.wait(timeout=10):
                raise RuntimeError("directory watcher loop failed to start")
            self._observer = Observer()
            self._observer.daemon = True
            self._observer.start()
            # 每进程单生命周期假设：本实例只 start 一次、不做退订（MVP 无
            # unsubscribe）；进程重启由 di.stop_monitor_runtime 置空
            # _monitor_runtime 后新建实例驱动。
            self._config_store.subscribe(self._on_config_changed)
            self._submit(self._apply_config(self._config_store.get()))
        except Exception:
            log.exception("failed to start directory watcher")
            self._abort_start()
            return
        log.info("DirectoryWatcher started")

    def _abort_start(self) -> None:
        """start() 中途失败后的回收（镜像 stop() 尾部清理，含任务取消）。"""
        self._running = False
        loop = self._loop
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                log.exception("failed to stop watchdog observer")
            self._observer = None
        if loop is not None and loop.is_running():
            try:
                shutdown = asyncio.run_coroutine_threadsafe(self._shutdown(), loop)
                shutdown.result(timeout=10)
            except Exception:
                log.exception("failed to shut down watcher loop tasks")
        if loop is not None:
            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception:
                log.exception("failed to stop watcher loop")
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._loop = None
        self._thread = None
        self._queue = None
        self._states.clear()
        self._last_event.clear()
        self._watched.clear()

    def stop(self) -> None:
        """停止监视：先停 Observer，再取消看护循环任务并回收线程。"""
        if not self._running:
            return
        self._running = False
        loop = self._loop
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                log.exception("failed to stop watchdog observer")
            self._observer = None

        if loop is not None and loop.is_running():
            try:
                shutdown = asyncio.run_coroutine_threadsafe(self._shutdown(), loop)
                shutdown.result(timeout=10)
            except Exception:
                log.exception("failed to shut down watcher loop tasks")
            loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._loop = None
        self._thread = None
        self._queue = None
        self._states.clear()
        self._last_event.clear()
        self._watched.clear()
        log.info("DirectoryWatcher stopped")

    async def _shutdown(self) -> None:
        current = asyncio.current_task()
        pending = [t for t in asyncio.all_tasks() if t is not current]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.create_task(self._worker())
        self._loop.create_task(self._ticker())
        self._loop_ready.set()
        try:
            self._loop.run_forever()
        finally:
            try:
                self._loop.close()
            except Exception:
                log.exception("failed to close watcher loop")

    # ─── 配置热生效 ───────────────────────────────────────

    def _on_config_changed(self, config: dict) -> None:
        """config_store.subscribe 回调：汇入 watch 线程应用（非阻塞）。"""
        self._submit(self._apply_config(config))

    def _submit(self, coro) -> None:
        if self._loop is not None and self._loop.is_running() and self._running:
            try:
                self._loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(coro)
                )
            except RuntimeError:
                log.exception("failed to submit config to watcher loop")

    async def _apply_config(self, config: dict) -> None:
        """按配置调整监视点与 effective 开关（只在 watch 线程执行）。"""
        enabled = bool(config.get("enabled"))
        sources = config.get("sources") or {}
        effective = enabled and bool(sources.get("directory"))
        self._effective = effective
        directories = config.get("directories") or []

        for directory in list(self._watched):
            if directory not in directories:
                self._unwatch(directory)
        for directory in directories:
            if directory not in self._watched:
                self._watch(directory)

        if not effective:
            # 关闭期间不累积待处理事件
            self._last_event.clear()
            self._states.clear()

    def _watch(self, directory: str) -> None:
        if not os.path.isdir(directory):
            log.warning("monitor directory missing, skip: %s", directory)
            return
        try:
            watch = self._observer.schedule(
                _FileEventHandler(self), directory, recursive=False
            )
            self._watched[directory] = watch
            log.info("watching directory: %s", directory)
        except Exception:
            log.exception("failed to watch directory: %s", directory)

    def _unwatch(self, directory: str) -> None:
        watch = self._watched.pop(directory, None)
        if watch is not None:
            try:
                self._observer.unschedule(watch)
            except Exception:
                log.exception("failed to unschedule directory: %s", directory)

    # ─── 事件入口（watchdog observer 线程） ────────────────

    def _note_event(self, path: str) -> None:
        """来自 Observer 线程：把路径推进队列（关闭时不投递）。"""
        if not self._running or self._queue is None or self._loop is None:
            return
        if not self._effective:
            return
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, path)
        except RuntimeError:
            log.debug("watcher loop not running, drop event for %s", path)

    # ─── 看护循环（watch 线程） ────────────────────────────

    async def _worker(self) -> None:
        """消费事件队列：登记路径并刷新其静默期起点（防抖计时）。"""
        loop = asyncio.get_running_loop()
        while True:
            path = await self._queue.get()
            if not self._effective:
                continue
            self._last_event[path] = loop.time()
            self._states.setdefault(path, _PathState())

    async def _ticker(self) -> None:
        """周期扫描：静默期已过（防抖）的路径进入稳定性检查。"""
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(self._check_interval)
            now = loop.time()
            for path, state in list(self._states.items()):
                if state.in_flight:
                    continue
                if now - self._last_event.get(path, 0.0) < self._debounce:
                    continue
                state.in_flight = True
                asyncio.create_task(self._capture_path(path))

    async def _capture_path(self, path: str) -> None:
        state = self._states.get(path)
        try:
            if not self._effective:
                return
            sample = self._sample(path)
            if sample is None:
                # 文件已消失（写入中途删除/移走）
                self._states.pop(path, None)
                self._last_event.pop(path, None)
                return
            if state is not None and state.prev_sample == sample:
                # 连续两次采样 size+mtime 不变 → 稳定，入库
                self._states.pop(path, None)
                self._last_event.pop(path, None)
                await self._process(path)
                return
            if state is None:
                state = _PathState()
                self._states[path] = state
            state.prev_sample = sample
            state.checks += 1
            if state.checks >= self._max_stable_attempts:
                # 达到尝试次数上限的文件仍持续写入：到期强制入库（防止无限跟踪）
                log.warning(
                    "file kept changing for %d checks, capture anyway: %s",
                    state.checks,
                    path,
                )
                self._states.pop(path, None)
                self._last_event.pop(path, None)
                await self._process(path)
                return
            # 未稳定：等待下一个静默期再采样
            self._last_event[path] = asyncio.get_running_loop().time()
        finally:
            if state is not None and path in self._states:
                state.in_flight = False

    @staticmethod
    def _sample(path: str) -> tuple[int, int] | None:
        try:
            st = os.stat(path)
        except OSError:
            return None
        return (st.st_size, st.st_mtime_ns)

    async def _process(self, path: str) -> None:
        """稳定文件 → IngestBridge 入库 → 派发 on_capture 回调。

        单文件异常吞掉记日志，不中断监视循环。
        """
        if not self._effective:
            return
        try:
            result = await self._bridge.capture(path)
        except Exception:
            log.exception("capture failed for %s", path)
            return
        try:
            self._emit(
                source="directory",
                status=result.status,
                summary=result.summary,
                evidence_id=result.evidence_id,
                knowledge_id=result.knowledge_id,
                ts=result.ts,
            )
        except Exception:
            log.exception("on_capture callback dispatch failed for %s", path)

    def _emit(
        self,
        *,
        source: str,
        status: str,
        summary: str,
        evidence_id: str | None,
        knowledge_id: str | None,
        ts: int,
    ) -> None:
        for callback in list(self._callbacks):
            try:
                outcome = callback(
                    source=source,
                    status=status,
                    summary=summary,
                    evidence_id=evidence_id,
                    knowledge_id=knowledge_id,
                    ts=ts,
                )
                if inspect.isawaitable(outcome):
                    asyncio.ensure_future(outcome)
            except Exception:
                log.exception("on_capture callback error: %s", callback)

    # ─── 回调注册 ─────────────────────────────────────────

    def register_callback(self, callback: Callable[..., Any]) -> None:
        """注册 on_capture 回调（可多个）；同步/异步函数均可。"""
        self._callbacks.append(callback)

    # ─── 状态查询（测试/观测用） ──────────────────────────

    @property
    def effective(self) -> bool:
        return self._effective


__all__ = ["DirectoryWatcher"]