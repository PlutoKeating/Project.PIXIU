"""PIXIU Foundation — 行为采集器（BehaviorCollector）

批次③「行为采集+自动偏好+冲突分级」的采集端：轮询窗口焦点（应用名+标题），
按应用聚合活跃时长，每 60s 把行为 evidence 经既有同进程管线
（``ingestion.ingest`` → ``knowledge.structure``，同 /memory/write 先例）落库。

隐私边界（用户确认，S2.1）：只采集窗口焦点变化（应用名+标题）与应用活跃时长；
**不记键击、不截屏、不读聊天内容**。标题经既有 security detector 判定，
sensitivity>0 直接丢弃（不写 evidence、不落库）——比 ingest_bridge 的
「带标记入库」更严格，按 S2.1 规格执行。

线程模型（轮询线程）：
- ``start()`` 启动 1s 轮询 daemon 线程；每 60s 聚合一次 ``_flush``；
- 聚合持久化是 async 调用，而轮询线程没有事件循环：``start()`` 在 _lifespan
  （主循环）上执行时捕获 ``asyncio.get_running_loop()`` 存为 ``_main_loop``，
  ``_flush`` 经 ``asyncio.run_coroutine_threadsafe`` 把 ``_aggregate`` 协程
  调度回主循环执行（对齐 di.py ``_schedule_capture_broadcast`` 的跨线程模式）；
- 主循环句柄缺失（测试直调/降级）时：当前线程无运行中循环则 ``asyncio.run``
  内联执行，否则记录日志放弃（不阻塞轮询）。

门控：``config.enabled && config.sources["behavior"]`` 才采集（仿 watcher
effective 语义，在采集器层实现，store 不门控）。

无 X 环境（xprop 失败/无活动窗口）：降级记录一次日志、不采集，不崩溃、
不影响其它监视。

入库形状说明：引擎 connector 注册表（engine/ingest/connectors）无
``behavior`` 类型，行为 evidence 使用语义对位的 ``USER_BEHAVIOR``；
该 connector 只透传 title/events/summary/entities/relations，因此聚合字段
（app/focus_seconds/hour_bucket/day_type）除顶层外同时放入 ``events[0]``，
保证 ingest→structure 后 ``evidence.raw["body"]["events"][0]`` 完整保留
（供 B3-2 偏好规则读取）。顶层扁平字段对齐 S2.1 规格的 evidence 形状。
"""

from __future__ import annotations

import asyncio
import subprocess
import threading
import time
from typing import Any, Coroutine

from ..core.logger import get_logger

log = get_logger(__name__)

#: 焦点轮询间隔（秒）。
_POLL_INTERVAL_S = 1.0

#: 活跃统计聚合间隔（秒）：每 60s 落一次行为 evidence。
_AGGREGATE_INTERVAL_S = 60.0

#: 行为 evidence 入库 source_type（引擎注册表实际类型；S2.1 规格中的
#: "behavior" 在引擎无对应 connector，见模块 docstring 与 B3-1 报告）。
SOURCE_TYPE_BEHAVIOR = "USER_BEHAVIOR"

#: 行为 evidence 落库 scope：本机 user:*，不参与 shared 同步流转。
BEHAVIOR_SCOPE = "user:local"


class BehaviorCollector:
    """窗口焦点 + 应用活跃时长采集器。

    用法：
        collector = BehaviorCollector(config_store, ingestion, knowledge, security)
        collector.start()
        ...
        collector.stop()

    构造参数与批次② IngestBridge 同构：config_store 提供同步 get()；
    ingestion/knowledge 复用 api 层同进程管线服务；security 可选注入
    （提供时标题经既有 detector 判定，sensitivity>0 不落库）。
    """

    def __init__(
        self,
        config_store: Any,
        ingestion: Any,
        knowledge: Any,
        security: Any | None = None,
    ) -> None:
        self._config = config_store
        self._ingestion = ingestion
        self._knowledge = knowledge
        self._security = security

        self._running = False
        self._thread: threading.Thread | None = None
        #: start() 在 _lifespan（主循环）上执行时捕获的主事件循环句柄；
        #: 轮询线程的 async 持久化经它调度回主循环。
        self._main_loop: asyncio.AbstractEventLoop | None = None

        #: 聚合态：app -> 累计活跃秒；app -> 最近一次窗口标题。
        self._focus: dict[str, float] = {}
        self._titles: dict[str, str] = {}
        self._current_app: str | None = None
        self._current_title: str = ""
        self._last_flip = 0.0
        #: xprop 降级只记录一次日志，避免 1s 轮询刷屏。
        self._degraded_logged = False

    # ─── 生命周期 ─────────────────────────────────────────

    def start(self) -> None:
        """启动轮询线程（幂等）。"""
        if self._running:
            return
        self._running = True
        try:
            # _lifespan 调用点在主循环上：捕获句柄供轮询线程调度持久化。
            self._main_loop = asyncio.get_running_loop()
        except RuntimeError:
            # 非事件循环上下文启动（异常路径）：持久化退化为内联执行。
            self._main_loop = None
        self._thread = threading.Thread(
            target=self._run, name="pixiu-behavior", daemon=True
        )
        self._thread.start()
        log.info("behavior collector started")

    def stop(self) -> None:
        """停止轮询线程（幂等；最多等待 5s）。"""
        self._running = False
        # 停止前 best-effort 最终 flush：落库最后不足 60s 的聚合数据
        # （无主循环句柄/测试直调时 _schedule 走内联 fallback；异常不阻断停止）。
        try:
            self._flush()
        except Exception:
            log.exception("final behavior flush failed during stop")
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._main_loop = None
        log.info("behavior collector stopped")

    # ─── 轮询主循环（轮询线程） ───────────────────────────

    def _run(self) -> None:
        last_agg = time.monotonic()
        while self._running:
            try:
                self._poll_focus()
            except Exception:
                log.exception("focus poll failed")
            now = time.monotonic()
            if now - last_agg >= _AGGREGATE_INTERVAL_S:
                try:
                    self._flush()
                except Exception:
                    log.exception("behavior flush failed")
                last_agg = now
            time.sleep(_POLL_INTERVAL_S)

    def _poll_focus(self) -> None:
        """读一次焦点并更新聚合态（同一应用持续聚焦不重复结算）。"""
        cfg = self._config.get()
        if not (cfg.get("enabled") and cfg.get("sources", {}).get("behavior")):
            # 门控关闭：不累计；重置当前焦点，避免恢复后把关闭期间的
            # 时长错误记给旧应用。
            self._current_app = None
            self._current_title = ""
            return

        app, title = self._read_focus()
        now = time.monotonic()

        if app == self._current_app:
            if app is not None:
                # 同应用持续聚焦（或窗口标题变化）：活跃时长在切换时统一结算，
                # 这里只刷新标题，不动 last_flip。
                self._current_title = title
                self._titles[app] = title
            return

        if self._current_app is not None:
            # 焦点离开当前应用（切到 B，或焦点丢失/窗口关闭/锁屏/无活动窗口）
            # 都结算 A 的活跃时长 [last_flip, now)——焦点消失时整段时长
            # 不能静默丢弃。None 连续（_current_app 已为 None）已由上方
            # ``app == self._current_app`` 早退覆盖，不会重复结算。
            self._focus[self._current_app] = (
                self._focus.get(self._current_app, 0.0) + (now - self._last_flip)
            )
        # app is None（焦点丢失/无活动窗口）：该时段不计入任何应用；
        # 门控关闭期间置空的 current_app 恢复后也不会错记时长。

        self._current_app = app
        self._current_title = title if app is not None else ""
        if app is not None:
            self._titles[app] = title
        self._last_flip = now

    # ─── 焦点读取（xprop，无 X 环境降级） ──────────────────

    def _read_focus(self) -> tuple[str | None, str]:
        """经 xprop 读当前活动窗口：返回 (应用名, 窗口标题)。

        xprop 缺失/失败/超时/无活动窗口 → (None, "")，不抛异常。
        """
        try:
            out = subprocess.run(
                ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout or ""
            win_id = _parse_active_window(out)
            if not win_id or win_id == "0x0":
                return None, ""
            out2 = subprocess.run(
                ["xprop", "-id", win_id, "WM_CLASS", "WM_NAME"],
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout or ""
            return _parse_wm_class(out2), _parse_wm_name(out2)
        except (subprocess.SubprocessError, OSError):
            if not self._degraded_logged:
                self._degraded_logged = True
                log.warning(
                    "xprop unavailable, behavior collection degraded "
                    "(no X environment?)"
                )
            return None, ""

    # ─── 聚合落库 ─────────────────────────────────────────

    def _flush(self) -> None:
        """把当前聚合的活跃统计转为 behavior evidence 落库（60s 一次）。"""
        cfg = self._config.get()
        if not (cfg.get("enabled") and cfg.get("sources", {}).get("behavior")):
            # 关闭期间不累积待落库聚合
            self._focus.clear()
            self._titles.clear()
            return

        aggregates = [
            (app, self._titles.get(app, ""), int(seconds))
            for app, seconds in self._focus.items()
        ]
        self._focus.clear()
        self._titles.clear()
        for app, title, seconds in aggregates:
            self._schedule(self._aggregate(app, title, seconds))

    def _schedule(self, coro: Coroutine[Any, Any, None]) -> None:
        """把 async 聚合持久化调度回主循环（轮询线程无事件循环）。"""
        loop = self._main_loop
        if loop is not None and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(coro, loop)
                return
            except RuntimeError:
                log.exception("behavior persist scheduling failed")
                # 调度失败时协程尚未被包装为 task：显式 close() 避免孤儿
                # 协程 "never awaited" 告警。
                coro.close()
                return
        # 主循环句柄缺失（测试直调/降级启动）：当前线程无运行中循环时
        # 内联执行一次（asyncio.run）；有运行中循环则放弃并记录。
        try:
            asyncio.run(coro)
        except RuntimeError:
            log.exception(
                "behavior persist fallback failed (no main loop registered)"
            )
            # asyncio.run 在运行中循环内抛 RuntimeError 时协程从未被启动：
            # 显式 close() 释放，避免 "coroutine was never awaited" 告警。
            coro.close()

    async def _aggregate(
        self, app: str, title: str, focus_seconds: int
    ) -> None:
        """把单应用聚合量转为行为 evidence 并落库（门控/敏感判定在先）。"""
        if not title:
            # S2.1：忽略无标题窗口——无标题不构成可用的行为 evidence。
            return
        cfg = self._config.get()
        if not (cfg.get("enabled") and cfg.get("sources", {}).get("behavior")):
            return
        if focus_seconds <= 0:
            return

        # 隐私边界：标题经既有 detector 判定，sensitivity>0 直接丢弃。
        if self._security is not None and title:
            try:
                sensitivity = await self._security.detect_sensitivity(
                    {"title": title}
                )
            except Exception:
                # detector 异常时无法确认标题非敏感：fail-closed 直接丢弃
                # （不落库），与「敏感即丢弃」的隐私姿态一致。
                log.exception(
                    "behavior sensitivity detect failed, dropping evidence"
                )
                return
            if sensitivity > 0:
                # 只记 app，不记标题原文（敏感标题不进日志文件）。
                log.info("drop behavior evidence (sensitive title): app=%s", app)
                return

        now = time.localtime()
        day_type = "workday" if now.tm_wday < 5 else "weekend"
        raw = {
            "app": app,
            "title": title,
            "focus_seconds": focus_seconds,
            "hour_bucket": now.tm_hour,
            "day_type": day_type,
            # USER_BEHAVIOR connector 只透传 title/events/summary：
            # 聚合字段同时放入 events，保证 evidence.raw 完整保留。
            "events": [
                {
                    "app": app,
                    "title": title,
                    "focus_seconds": focus_seconds,
                    "hour_bucket": now.tm_hour,
                    "day_type": day_type,
                }
            ],
        }
        await self._persist(raw)

    async def _persist(self, raw: dict) -> None:
        """复用 /memory/write 同进程管线：ingest → structure（异常只记日志）。"""
        try:
            evidence = await self._ingestion.ingest(
                SOURCE_TYPE_BEHAVIOR, raw, BEHAVIOR_SCOPE, sensitivity=0
            )
            await self._knowledge.structure(evidence)
        except Exception:
            log.exception("behavior persist failed")


# ─── xprop 输出解析（健壮性：逐行匹配、缺失返回 None/""）────

def _parse_active_window(text: str) -> str | None:
    """从 `xprop -root _NET_ACTIVE_WINDOW` 输出解析窗口 id。

    典型输出：``_NET_ACTIVE_WINDOW(WINDOW): window id # 0x3a00007``。
    """
    for line in text.splitlines():
        if "_NET_ACTIVE_WINDOW" not in line or "#" not in line:
            continue
        return line.split("#", 1)[1].strip()
    return None


def _parse_wm_class(text: str) -> str | None:
    """从 WM_CLASS 行解析应用名（取逗号分隔的第一段，去掉引号）。

    典型输出：``WM_CLASS(STRING) = "org.kylin.files", "org.kylin.files"``。
    """
    for line in text.splitlines():
        if "WM_CLASS" not in line or "=" not in line:
            continue
        value = line.split("=", 1)[1].strip()
        parts = [part.strip().strip('"') for part in value.split(",")]
        # xprop 缺失属性时打印 "not found."：视为无应用名，返回 None。
        if parts and parts[0].lower() not in ("not found.", "not found"):
            return parts[0]
    return None


def _parse_wm_name(text: str) -> str:
    """从 WM_NAME 行解析窗口标题（去掉首尾引号；缺失返回空串）。

    典型输出：``WM_NAME(STRING) = "支出清单"``。
    """
    for line in text.splitlines():
        if "WM_NAME" not in line or "=" not in line:
            continue
        value = line.split("=", 1)[1].strip().strip('"')
        # xprop 缺失属性时打印 "not found."：视为无标题，返回空串。
        if value.lower() in ("not found.", "not found"):
            return ""
        return value
    return ""


__all__ = [
    "BEHAVIOR_SCOPE",
    "BehaviorCollector",
    "SOURCE_TYPE_BEHAVIOR",
]
