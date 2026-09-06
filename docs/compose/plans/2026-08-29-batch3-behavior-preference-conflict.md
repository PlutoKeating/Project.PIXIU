# 批次③ · 行为采集 + 自动偏好 + 冲突分级 Implementation Plan

> 2026-09-06 代码复核：行为采集与冲突 severity 已实现；focus_seconds 自动偏好规则和生产 collector→extract 闭环仍不能由 15 例评测标签达标代替，保持原收窄边界。
> 下文实施步骤、旧接口草图和测试数字保留作阶段历史，不作为当前操作手册；当前契约见 docs/API.md，发布见 docs/DELIVERY_PLAN.md。

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 行为采集器（窗口焦点+应用活跃时长）供数 → 偏好提取规则补齐使 `preference_accuracy` 从 0.33 达 0.85 → 冲突打扰按 Arbiter 三态分级（MERGE 静默 / NEW_WINS 通知 / MANUAL 角标+切 Tab）。

**Architecture:** 后端 monitor 模块新增 `behavior.py`（采集器，复用批次② runtime 生命周期与 /memory/write 同进程管线）；`preference/rules.py` 补行为规则并修正既有规则与评测 evidence 形状的对齐；`conflict_detected` 帧与 /conflicts 响应加 `severity`；前端 EventRouter/PixiuApp 按 severity 分流打扰。

**Tech Stack:** Python 3.12 · FastAPI · xprop（焦点轮询，无 X 环境降级） | C++17 · Qt5 · QtTest(offscreen)

## Global Constraints

- **模块边界**：Plan-B（后端）只改 `backend/`；Plan-F（前端）只改 `frontend/`。契约变更写回 `docs/API.md`。
- **隐私铁律（用户确认）**：只采集窗口焦点变化（应用名+标题）与应用活跃时长；**不记键击、不截屏、不读聊天内容**；标题经既有 detector 判定，sensitivity>0 不落库。
- **验收口径**：`python -m backend.foundation.eval --dataset reference-v1 --predictions ... --output-dir ...`（capture_eval_predictions.py 重采）`preference_accuracy >= 0.85`；后端全量 pytest 绿；前端 OFF/ON 双路径 ctest + regression.sh 绿。
- **canonical key 铁律**：同一偏好流的 key 必须稳定（Extractor 按 key 去重、PreferenceService 以 key 判新建 vs 升版）——动态信号只能进 value 不能改 key。
- **severity 向后兼容**：旧前端忽略新字段；旧后端广播无 severity → 前端缺省按 high 处理。
- 提交前缀 `feat(monitor)/feat(preference)/feat(frontend)/test(...)/docs(...)`；禁止 push；个人分支同步 `--ff-only`。
- 依赖批次②已合入（main @ 53495a5）。

---

## Task B3-1: BehaviorCollector 采集器

**Covers:** [S2.1]

**Files:**
- Create: `backend/foundation/monitor/behavior.py`
- Modify: `backend/foundation/api/di.py`（get_behavior_collector / start/stop 并入 monitor runtime 生命周期）
- Modify: `backend/foundation/api/http_app.py`（_lifespan 启动/停止 behavior collector）
- Test: `backend/foundation/tests/test_behavior_collector.py`

**Interfaces:**
- Consumes: `MonitorConfigStore.get()`（同步）、`IngestionService.ingest`、`KnowledgeService.structure`、`settings.monitor_enabled`、既有 detector（security）
- Produces: `BehaviorCollector(config_store, ingestion, knowledge, security)` — `.start()/.stop()`；内部 1s 轮询线程读焦点（`xprop -root _NET_ACTIVE_WINDOW` → `xprop -id <win> WM_NAME`），60s 聚合一次 `{"app","title","focus_seconds","hour_bucket","day_type"}` evidence 经 ingest→structure 落库；无 X 环境（xprop 失败）降级记录日志不采集；`sources["behavior"]` 与 `enabled` 门控（仿 watcher effective）；sensitivity>0 不落库。

- [ ] **Step 1: 写失败测试**（mock xprop 输出 + 假 ingestion/knowledge）

```python
# backend/foundation/tests/test_behavior_collector.py
"""行为采集器：焦点轮询、聚合、门控、降级。"""
import asyncio
import pytest

from backend.foundation.monitor.behavior import BehaviorCollector


class _FakeConfig:
    def __init__(self, enabled=True, behavior=True):
        self._cfg = {"enabled": enabled,
                     "sources": {"behavior": behavior}}
    def get(self):
        return self._cfg


class _FakeIngestion:
    def __init__(self):
        self.evidence = []
    async def ingest(self, source_type, raw, scope, *, sensitivity=0):
        self.evidence.append((source_type, raw, scope, sensitivity))
        return type("E", (), {"id": f"evd_{len(self.evidence)}",
                              "source_type": source_type,
                              "raw": raw})()


class _FakeKnowledge:
    def __init__(self):
        self.items = []
    async def structure(self, evidence):
        self.items.append(evidence)
        return type("K", (), {"id": f"knw_{len(self.items)}"})()


def _make_collector(**kw):
    cfg = _FakeConfig(**kw)
    ing = _FakeIngestion()
    know = _FakeKnowledge()
    return BehaviorCollector(cfg, ing, know, security=None), cfg, ing, know


@pytest.mark.asyncio
async def test_aggregates_focus_into_behavior_evidence():
    collector, cfg, ing, _ = _make_collector()
    # 直接调用内部聚合方法（绕开 1s 轮询线程，确定性测试）
    collector._aggregate("org.kylin.files", "支出清单", 42)
    assert ing.evidence
    source_type, raw, scope, sens = ing.evidence[-1]
    assert str(source_type) == "behavior"
    assert raw["app"] == "org.kylin.files"
    assert raw["focus_seconds"] == 42
    assert raw["hour_bucket"] >= 0
    assert scope == "user:local"


@pytest.mark.asyncio
async def test_gated_off_does_not_emit():
    collector, cfg, ing, _ = _make_collector(enabled=True, behavior=False)
    collector._aggregate("org.kylin.files", "t", 10)
    assert not ing.evidence


@pytest.mark.asyncio
async def test_sensitive_title_dropped():
    collector, cfg, ing, _ = _make_collector()
    collector._security = type("S", (), {
        "classify": lambda self, text: 2})()

    async def _guard(raw):
        collector._aggregate("app", "含敏感词标题", 5, _title="含敏感词标题")

    await _guard(None)
    assert not ing.evidence
```

- [ ] **Step 2: 运行验证失败**

Run: `cd /home/pluto/Project.PIXIU && PYTHONPATH=. PIXIU_EMBEDDING=portable pytest backend/foundation/tests/test_behavior_collector.py -q`
Expected: FAIL（ModuleNotFoundError: backend.foundation.monitor.behavior）

- [ ] **Step 3: 实现 behavior.py**

```python
"""行为采集器：窗口焦点 + 应用活跃时长（隐私边界：不记键击/截屏/聊天内容）。"""

from __future__ import annotations

import subprocess
import threading
import time

from ..core.logger import get_logger

log = get_logger(__name__)

_POLL_INTERVAL_S = 1.0
_AGGREGATE_INTERVAL_S = 60.0


class BehaviorCollector:
    def __init__(self, config_store, ingestion, knowledge, security=None) -> None:
        self._config = config_store
        self._ingestion = ingestion
        self._knowledge = knowledge
        self._security = security
        self._running = False
        self._thread: threading.Thread | None = None
        self._focus: dict[str, float] = {}  # app -> 累计秒
        self._current_app: str | None = None
        self._current_title: str = ""
        self._last_flip = 0.0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log.info("behavior collector started")

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _run(self) -> None:
        last_agg = time.monotonic()
        while self._running:
            try:
                self._poll_focus()
            except Exception:
                log.exception("focus poll failed")
            now = time.monotonic()
            if now - last_agg >= _AGGREGATE_INTERVAL_S:
                self._flush()
                last_agg = now
            time.sleep(_POLL_INTERVAL_S)

    def _poll_focus(self) -> None:
        cfg = self._config.get()
        if not (cfg.get("enabled") and cfg.get("sources", {}).get("behavior")):
            self._current_app = None
            return
        app, title = self._read_focus()
        now = time.monotonic()
        if self._current_app is not None and self._current_app != app:
            self._focus[self._current_app] = self._focus.get(
                self._current_app, 0.0) + (now - self._last_flip)
        if app is not None:
            self._current_app = app
            self._current_title = title
            self._last_flip = now

    def _read_focus(self) -> tuple[str | None, str]:
        try:
            out = subprocess.run(
                ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                capture_output=True, text=True, timeout=2,
            ).stdout
            win_id = out.split("#")[1].strip() if "#" in out else None
            if not win_id or win_id == "0x0":
                return None, ""
            out2 = subprocess.run(
                ["xprop", "-id", win_id, "WM_CLASS", "WM_NAME"],
                capture_output=True, text=True, timeout=2,
            ).stdout
            app = _parse_wm_class(out2)
            title = _parse_wm_name(out2)
            return app, title
        except (subprocess.SubprocessError, OSError, IndexError):
            return None, ""

    def _flush(self) -> None:
        cfg = self._config.get()
        if not (cfg.get("enabled") and cfg.get("sources", {}).get("behavior")):
            self._focus.clear()
            return
        for app, seconds in self._focus.items():
            self._aggregate(app, "", int(seconds))
        self._focus.clear()

    def _aggregate(self, app: str, title: str, focus_seconds: int) -> None:
        cfg = self._config.get()
        if not (cfg.get("enabled") and cfg.get("sources", {}).get("behavior")):
            return
        if focus_seconds <= 0:
            return
        if self._security is not None and title:
            try:
                if self._security.classify(title) > 0:
                    log.info("drop behavior evidence (sensitive title)")
                    return
            except Exception:
                log.exception("sensitivity classify failed")
        hour_bucket = time.localtime().tm_hour
        asyncio_loop = None  # flush 在轮询线程，经 run_coroutine_threadsafe
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        raw = {
            "app": app, "title": title,
            "focus_seconds": focus_seconds,
            "hour_bucket": hour_bucket,
            "day_type": "workday" if time.localtime().tm_wday < 5 else "weekend",
        }
        # 轮询线程无事件循环：交由调用方（di）经 loop.call_soon_threadsafe 执行
        if loop is None:
            # 测试直调路径：直接协程
            try:
                asyncio.run(self._persist(raw))
            except RuntimeError:
                pass
        else:
            asyncio.run_coroutine_threadsafe(self._persist(raw), loop)

    async def _persist(self, raw: dict) -> None:
        try:
            evidence = await self._ingestion.ingest(
                "behavior", raw, "user:local", sensitivity=0)
            await self._knowledge.structure(evidence)
        except Exception:
            log.exception("behavior persist failed")


def _parse_wm_class(text: str) -> str | None:
    for line in text.splitlines():
        if "WM_CLASS" in line and "=" in line:
            return line.split("=", 1)[1].strip().strip("\"").split(",")[0]
    return None


def _parse_wm_name(text: str) -> str:
    for line in text.splitlines():
        if "WM_NAME" in line and "=" in line:
            return line.split("=", 1)[1].strip().strip("\"")
    return ""


__all__ = ["BehaviorCollector"]
```
> 注：上例聚合持久化路径较繁（线程→事件循环桥接）。**实现时以仓库既有模式为准**：若 di 的 monitor runtime 已有主循环句柄（批次② `_main_loop` 先例），直接经 `call_soon_threadsafe` 调 async 持久化；测试直调 `_aggregate` 断言 evidence 形状即可。`_aggregate` 的 loop 桥接是实现细节，可简化——**以编译/测试为准绳**。

- [ ] **Step 4: 运行验证通过 + di/lifespan 接线**

Run: `cd /home/pluto/Project.PIXIU && PYTHONPATH=. PIXIU_EMBEDDING=portable pytest backend/foundation/tests/test_behavior_collector.py backend/foundation/tests/test_di.py -q`
Expected: PASS

di.py：`get_behavior_collector()` 惰性单例（复用 get_db/get_ingestion_service/get_knowledge_service/get_security_service）；`start_monitor_runtime` 内 start、`stop_monitor_runtime` 内 stop。

- [ ] **Step 5: 提交**

```bash
git add backend/foundation/monitor/behavior.py backend/foundation/api/di.py backend/foundation/api/http_app.py backend/foundation/tests/test_behavior_collector.py
git commit -m "feat(monitor): behavior collector for focus and app activity"
```

---

## Task B3-2: 偏好规则对齐（preference_accuracy 0.33 → 0.85）

**Covers:** [S2.2]

**Files:**
- Modify: `backend/engine/preference/rules.py`（新增/修正行为规则；修复既有规则与评测 evidence 形状的对齐）
- Modify: `backend/engine/preference/extractor.py`（如需）
- Test: `backend/engine/tests/test_preference_rules.py`（新增行为用例）
- 验证: `backend/scripts/capture_eval_predictions.py` 重采基线 → `preference_accuracy >= 0.85`

**Interfaces:**
- Consumes: 评测 evidence 形状（capture_eval_predictions.py:135-140——OP_HABIT 走 source_type=USER_BEHAVIOR、raw=`{"title": key, "key": key, "enabled": true}`；OUTPUT_STYLE/SECURITY_POLICY 走 MANUAL_CONFIG 同形状）；`_CANONICAL_PREFERENCE_KEYS`（rules.py:244-257，已含 tool.selection.frequent→OP_HABIT）；`_canonical_from_key`
- Produces: 三类标签全部命中——`OP_HABIT:tool.selection.frequent`、`OUTPUT_STYLE:output_style.compact`、`SECURITY_POLICY:security.confirm_sensitive`（category:key 精确匹配评测 expected.labels）

- [ ] **Step 1: 先诊断现状（不要先写代码）**

Run: `cd /home/pluto/Project.PIXIU && PYTHONPATH=. PIXIU_EMBEDDING=portable python3 -m backend.foundation.eval --dataset reference-v1 --predictions <(python3 backend/scripts/capture_eval_predictions.py ...) --output-dir /tmp/eval-b3 2>&1 | tail -20`（或按 acceptance/README.md 的既有命令）
观察：哪几类 label 命中/漏掉（0.33 = 15 例中约 5 例命中——通常是 SECURITY_POLICY 命中、OP_HABIT/OUTPUT_STYLE 漏）。**把诊断结论写入任务报告**。

- [ ] **Step 2: 写失败测试**（针对漏掉的分支）

```python
# backend/engine/tests/test_preference_rules.py 追加（按诊断结果补对应分支）
import pytest
from backend.engine.preference.extractor import Extractor

def _evidence(source_type, raw):
    from backend.foundation.core.models import Evidence
    return Evidence(
        id="evd_t", source_type=source_type, raw=raw,
        quality_score=1.0, sensitivity=0, scope="user:eval", created_at=1,
    )

def test_habit_from_behavior_evidence():
    ev = _evidence("USER_BEHAVIOR", {"title": "tool.selection.frequent",
                                     "key": "tool.selection.frequent",
                                     "enabled": True})
    out = Extractor().extract(ev)
    assert any(c["category"] == "OP_HABIT" and c["key"] == "tool.selection.frequent"
               for c in out)

def test_output_style_from_config_evidence():
    ev = _evidence("MANUAL_CONFIG", {"title": "output_style.compact",
                                     "key": "output_style.compact",
                                     "enabled": True})
    out = Extractor().extract(ev)
    assert any(c["category"] == "OUTPUT_STYLE" and c["key"] == "output_style.compact"
               for c in out)

def test_security_from_config_evidence():
    ev = _evidence("MANUAL_CONFIG", {"title": "security.confirm_sensitive",
                                     "key": "security.confirm_sensitive",
                                     "enabled": True})
    out = Extractor().extract(ev)
    assert any(c["category"] == "SECURITY_POLICY" and c["key"] == "security.confirm_sensitive"
               for c in out)
```

- [ ] **Step 3: 运行验证失败**

Run: `cd /home/pluto/Project.PIXIU && PYTHONPATH=. PIXIU_EMBEDDING=portable pytest backend/engine/tests/test_preference_rules.py -q`
Expected: 至少一用例 FAIL（诊断出的漏报分支）

- [ ] **Step 4: 修正规则**（读 rules.py 全文后，按诊断精确修改；原则：canonical key 稳定、动态信号只进 value；不改 reference.py 期望标签——那是 85fb7e9 定的语料契约，改它属移动球门）

- [ ] **Step 5: 重采基线验证**

Run: 按 acceptance/README.md 或 eval 命令重采 → 报告 `preference_accuracy` 数值（须 >= 0.85）。长命令后台跑，输出重定向 + 轮询。

- [ ] **Step 6: 提交**

```bash
git add backend/engine/preference/ backend/engine/tests/test_preference_rules.py
git commit -m "feat(preference): align extraction rules to evaluation labels"
```

---

## Task B3-3: 冲突 severity 分级（后端）

**Covers:** [S3.1]

**Files:**
- Modify: `backend/foundation/core/models.py`（ConflictRecord 加 `severity: str = "high"`——向后兼容默认）
- Modify: `backend/engine/conflict/arbiter.py` 或 `__init__.py`（按 resolution 填 severity：MERGE→low、NEW_WINS→medium、MANUAL→high）
- Modify: `backend/foundation/api/http_app.py`（conflict_detected 广播 data 加 severity；/conflicts 序列化含 severity）
- Test: `backend/foundation/tests/test_conflict_api.py` 或扩展 test_api.py

**Interfaces:**
- Produces: `ConflictRecord.severity`（"low"|"medium"|"high"）；WS `conflict_detected` data 含 `"severity"`；GET /conflicts 每项含 severity；映射：MERGE→low、NEW_WINS→medium、MANUAL→high

- [ ] **Step 1: 写失败测试**（三态映射 + 序列化 + 广播）
- [ ] **Step 2: 运行验证失败**
- [ ] **Step 3: 实现**（models 加字段默认 "high"；arbiter/__init__ 填值；http_app 广播与序列化带 severity；repository 序列化兼容）
- [ ] **Step 4: 运行验证通过**（test_conflict_api + test_api 回归）
- [ ] **Step 5: 提交** `git commit -m "feat(monitor): grade conflict severity by resolution"`

---

## Task F3-1: 前端冲突分级打扰

**Covers:** [S3.2]

**Files:**
- Modify: `frontend/src/app/EventRouter.h/.cpp`（conflictDetected 加 `QString severity` 参数或 data 透传——先读现有签名 `conflictDetected(knowledgeTitle, field, oldValue, newValue)` 决定扩展方式）
- Modify: `frontend/src/app/PixiuApp.cpp`（按 severity 分流：low 静默计数 / medium 温和通知+角标 / high 现状全动作）
- Modify: `frontend/src/widgets/MemoryPanel.cpp`（冲突 Tab 条目 severity 标记：low 灰 / medium 蓝 / high 红——ui::UiTokens 语义色）
- Test: `frontend/tests/t_event_router.cpp`、`frontend/tests/t_app_navigation.cpp`

**Interfaces:**
- Consumes: EventRouter::conflictDetected（severity 参数）、ui::UiTokens（Role::Muted/Info/Warning 或等价）
- Produces: 分流逻辑——severity=="low" → 仅内存计数；"medium" → notify(tr("记忆已更新"), title) + 角标+1；缺省/"high" → 现状（「检测到记忆冲突」+ 角标+1 + refresh + 切 Tab）；冲突 Tab 条目 severity 样式

- [ ] **Step 1: 写失败测试**（EventRouter severity 参数断言 + PixiuApp 三态分流 + MemoryPanel severity 标记）
- [ ] **Step 2: 运行验证失败**（ctest event_router / app_navigation 红）
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行验证通过**（`QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend --output-on-failure` → 33+ 绿）
- [ ] **Step 5: 提交** `git commit -m "feat(frontend): grade conflict notifications by severity"`

---

## Task F3-2: i18n + 双路径回归 + 文档收尾

**Covers:** [S4, S5]

**Files:**
- Modify: `frontend/resources/i18n/pixiu_en_US.ts/.qm`（新文案「记忆已更新」等）
- Modify: `docs/API.md`（conflict_detected /conflicts severity 字段）
- Modify: `README.md`（偏好捕捉亮点更新——若 0.85 达成）
- Test: 回归

- [ ] **Step 1: lupdate/lrelease**（cd frontend/resources/i18n && lupdate ../../src ../../tests -no-obsolete -locations none -ts pixiu_en_US.ts，0 unfinished）
- [ ] **Step 2: 文档更新**（API.md severity 说明；README 偏好状态）
- [ ] **Step 3: 全量回归**：`bash frontend/scripts/regression.sh`（OFF/ON）+ 后端全量 pytest（后台轮询）
- [ ] **Step 4: 提交**（i18n 与 docs 分开）

---

## 执行顺序

B3-1 → B3-2（依赖行为 evidence 形状确认，但 B3-2 主要靠评测诊断可先行）→ B3-3 → F3-1 → F3-2。B3-2 是核心（硬指标），若诊断发现既有规则缺陷需较大重构，允许该任务单独扩产并在报告说明。
