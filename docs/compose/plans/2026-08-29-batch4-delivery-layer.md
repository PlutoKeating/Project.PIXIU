# 批次④ · 递送层 Implementation Plan

> 2026-09-06 代码复核：洞察实际只返回 recent 类，简报按请求计算，不存在每日后台自动推送；偏好型洞察仍未实现。两项 REST 由 foundation/api/delivery.py 提供。
> 下文实施步骤、旧接口草图和测试数字保留作阶段历史，不作为当前操作手册；当前契约见 docs/API.md，发布见 docs/DELIVERY_PLAN.md。

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让「一次配置、永久监控」沉淀的记忆转化为主动递上——洞察流（聊天窗欢迎页动态建议）、定时简报（按日汇总）、相关性提醒（目录事件/偏好变更的轻提醒），兑现产品愿景「主动服务」半句。

**Architecture:** 后端新增 `backend/engine/delivery/`（insights + digest 规则化生成器，无 LLM 依赖）+ `backend/foundation/api/delivery.py`（两个 GET 端点）；前端改造 ChatWindow 欢迎页（动态建议卡）+ PixiuApp（captureEvent 相关主题轻提醒 + 偏好变更提醒 + 简报入口）。

**Tech Stack:** Python 3.12 · FastAPI · SQLite（既有仓储） | C++17 · Qt5 · QtTest(offscreen)

## Global Constraints

- **模块边界**：Plan-B 只改 `backend/`；Plan-F 只改 `frontend/`。契约写回 `docs/API.md`。
- **隐私铁律**：summary/简报/洞察均为服务端生成中文文案，**不含敏感原文全文**；sensitivity>0 的知识不进洞察候选。
- **无 LLM 依赖**：insights/digest 均为规则化模板生成，离线可运行；不做系统推送（仅应用内通知/角标）。
- **验收口径**：后端全量 pytest 绿；前端 OFF/ON 双路径 ctest + regression.sh 绿；GET /delivery/insights 与 /delivery/digest 契约测试通过。
- **节制原则**：相关性提醒每类每天上限 3 条；MANUAL 冲突待处理时不递送相关洞察。
- 提交前缀 `feat(delivery)/feat(frontend)/test(...)/docs(...)`；禁止 push；个人分支同步 `--ff-only`。
- 依赖批次①-③已合入（main @ bc8d18d）。

---

## Task B4-1: 洞察流服务（后端）

**Covers:** [S2.1, S3]

**Files:**
- Create: `backend/engine/delivery/__init__.py`、`backend/engine/delivery/insights.py`
- Create: `backend/foundation/api/delivery.py`（GET /delivery/insights 端点）
- Modify: `backend/foundation/api/di.py`（get_delivery_service）
- Test: `backend/engine/tests/test_delivery_insights.py`、`backend/foundation/tests/test_delivery_api.py`

**Interfaces:**
- Consumes: `KnowledgeRepository`（list recent by quality/created_at——先读 SqliteKnowledgeRepo 现有查询方法，可能需要加 `recent(scope, limit, since_ts)`）、`PreferenceService.resolve`、既有 ConflictRepository（MANUAL 待处理检测）、settings
- Produces: `DeliveryInsightsService(knowledge_repo, preference_service, conflict_repo)` — `async def insights(scope: str, limit: int = 3) -> list[dict]`（每项 {title, summary, knowledge_id, score, kind: "recent"|"preference"}）；`GET /delivery/insights?limit=3` → `{"insights": [...]}`（limit 缺省 3 上限 10，>10 → 400；空 → `{"insights": []}`）

- [ ] **Step 1: 写失败测试**（insights 排序/sensitivity 过滤/MANUAL 抑制/kind 区分/空列表 + 端点契约）

```python
# backend/engine/tests/test_delivery_insights.py
"""洞察流生成规则。"""
import time
import pytest

from backend.engine.delivery.insights import DeliveryInsightsService


class _FakeKnowledgeRepo:
    def __init__(self, items):
        self.items = items
    async def recent(self, scope, limit, since_ts=None):
        return [i for i in self.items if i["created_at"] >= (since_ts or 0)][:limit]


class _FakePreference:
    async def resolve(self, scope, key=None, preferences=None):
        return []


class _FakeConflict:
    def __init__(self, has_manual=False):
        self.has_manual = has_manual
    async def list(self, *, status=None):
        return [{"resolution": "MANUAL"}] if self.has_manual else []


def _item(kid, title, quality, created_at, sensitivity=0):
    return {
        "id": kid, "title": title, "body": {"text": "摘要" + title},
        "quality_score": quality, "sensitivity": sensitivity,
        "created_at": created_at, "scope": "user:local",
    }


@pytest.mark.asyncio
async def test_insights_sorted_by_quality_recent():
    now = int(time.time())
    svc = DeliveryInsightsService(
        _FakeKnowledgeRepo([_item("k1", "A", 0.3, now), _item("k2", "B", 0.9, now)]),
        _FakePreference(), _FakeConflict())
    out = await svc.insights("user:local", limit=3)
    assert [i["knowledge_id"] for i in out] == ["k2", "k1"]
    assert out[0]["kind"] == "recent"


@pytest.mark.asyncio
async def test_insights_excludes_sensitive():
    now = int(time.time())
    svc = DeliveryInsightsService(
        _FakeKnowledgeRepo([_item("k1", "A", 0.9, now, sensitivity=2),
                            _item("k2", "B", 0.5, now)]),
        _FakePreference(), _FakeConflict())
    out = await svc.insights("user:local")
    assert [i["knowledge_id"] for i in out] == ["k2"]


@pytest.mark.asyncio
async def test_insights_suppressed_when_manual_conflict_pending():
    now = int(time.time())
    svc = DeliveryInsightsService(
        _FakeKnowledgeRepo([_item("k1", "A", 0.9, now)]),
        _FakePreference(), _FakeConflict(has_manual=True))
    out = await svc.insights("user:local")
    assert out == []
```

- [ ] **Step 2: 运行验证失败**（ModuleNotFoundError: backend.engine.delivery）
- [ ] **Step 3: 实现 insights.py + delivery.py 端点 + di 注入**

```python
# backend/engine/delivery/insights.py
"""洞察流生成：最近高质量记忆 + 偏好信号（无 LLM，规则化）。"""
from __future__ import annotations

import time

_SINCE_WINDOW_S = 24 * 3600
_SENSITIVE_THRESHOLD = 0


class DeliveryInsightsService:
    def __init__(self, knowledge_repo, preference_service, conflict_repo) -> None:
        self._knowledge = knowledge_repo
        self._preferences = preference_service
        self._conflicts = conflict_repo

    async def insights(self, scope: str, limit: int = 3) -> list[dict]:
        manual = await self._conflicts.list()
        if any(r.get("resolution") == "MANUAL" for r in manual):
            return []  # 人工仲裁待处理：不递送，避免干扰
        since = int(time.time()) - _SINCE_WINDOW_S
        items = await self._knowledge.recent(scope, limit * 2, since_ts=since)
        items = [i for i in items if i.get("sensitivity", 0) <= _SENSITIVE_THRESHOLD]
        items.sort(key=lambda i: i.get("quality_score", 0.0), reverse=True)
        return [
            {
                "title": i["title"],
                "summary": _summarize(i),
                "knowledge_id": i["id"],
                "score": i.get("quality_score", 0.0),
                "kind": "recent",
            }
            for i in items[:limit]
        ]


def _summarize(item: dict) -> str:
    body = item.get("body") or {}
    text = body.get("text") or ""
    # 摘要取标题 + 正文前 60 字（不含敏感原文——候选已过滤 sensitivity）
    snippet = text[:60].strip()
    return f"{item.get('title', '')}：{snippet}" if snippet else item.get("title", "")
```

> 注：`conflict_repo.list()` 的签名需先读既有 SqliteConflictRepo（B3 已有 list 方法）；knowledge_repo 若无 `recent(scope, limit, since_ts)` 需补——**以编译/测试为准绳**，实现时先读 repository.py 现有查询。

- [ ] **Step 4: 运行验证通过**（test_delivery_insights + test_delivery_api + test_api 回归）
- [ ] **Step 5: docs/API.md**：GET /delivery/insights 行 + §3.23 说明（请求/响应示例照 spec S3）
- [ ] **Step 6: 提交** `git commit -m "feat(delivery): insights endpoint with recent-memory ranking"`

---

## Task B4-2: 定时简报服务（后端）

**Covers:** [S2.2, S3]

**Files:**
- Create: `backend/engine/delivery/digest.py`
- Modify: `backend/foundation/api/delivery.py`（GET /delivery/digest）
- Test: `backend/engine/tests/test_delivery_digest.py`、`backend/foundation/tests/test_delivery_api.py`

**Interfaces:**
- Consumes: `MonitorLogStore`（批次②，get by date——先读 monitor_log.py 现有 list_events 是否支持按日过滤，可能需要补 `list_events_by_day(date)`）、`PreferenceRepository`（当日版本变化——或简化：简报只统计 monitor 日志 + 冲突计数）、`ConflictRepository`（当日裁决）
- Produces: `DeliveryDigestService(monitor_log, conflict_repo)` — `async def digest(date: str) -> dict`（`{"date", "summary"}`）；`GET /delivery/digest?date=YYYY-MM-DD`（缺省今天；非法日期 → 400 INVALID_REQUEST；空日 → summary 为「当日无新记忆」）

- [ ] **Step 1: 写失败测试**（按日聚合计数/文案不含敏感原文/空日/非法日期 400）
- [ ] **Step 2: 运行验证失败**
- [ ] **Step 3: 实现 digest.py + 端点**（monitor_log 按日过滤 + 冲突计数 → 中文模板：`当日新增 %d 条记忆（目录 %d、文本 %d…），%d 项偏好更新，%d 项冲突已自动合并`——若 monitor_log 的 source 枚举含 directory/text 则按组；summary 服务端生成不含敏感原文）
- [ ] **Step 4: 运行验证通过**（digest + api 回归）
- [ ] **Step 5: docs/API.md**：GET /delivery/digest 行 + §3.24
- [ ] **Step 6: 提交** `git commit -m "feat(delivery): daily digest endpoint"`

---

## Task B4-3: 前端欢迎页动态建议 + 相关性提醒

**Covers:** [S2.1, S2.3]

**Files:**
- Modify: `frontend/src/services/BackendTransport.h/.cpp`（deliveryInsights() 默认空实现 → 信号 insightsResult(QJsonArray)）
- Modify: `frontend/src/services/HttpBackendTransport.cpp`（GET /delivery/insights）
- Modify: `frontend/src/widgets/ChatWindow.h/.cpp`（欢迎页动态建议卡：接 insightsResult 渲染 suggestionCard 列表；点击 → 信号 insightActivated(knowledge_id)）
- Modify: `frontend/src/app/PixiuApp.h/.cpp`（启动/打开聊天窗时拉 insights；captureEvent 相关主题轻提醒——文件名 token vs 近期 knowledge title token 交集 + 每日上限 3；偏好变更提醒——preferencesList 对比版本；今日简报入口）
- Modify: `frontend/src/app/SyncController.h/.cpp` 或新建 DeliveryController（insights 状态机——仿 SyncController 模式，PixiuApp 增长已多次评估，倾向新建 DeliveryController 独立职责）
- Test: `frontend/tests/t_chat_window.cpp`、`frontend/tests/t_app_navigation.cpp`

**Interfaces:**
- Consumes: `BackendTransport::deliveryInsights()`（新虚方法默认空实现 + insightsResult 信号）、既有 captureEvent（EventRouter）、preferencesList、悬浮球/角标
- Produces: `DeliveryController(transport)` — `loadInsights()` → `insightsLoaded(QJsonArray)`；ChatWindow 欢迎页动态建议卡（objectName=suggestionCard 复用既有样式）；PixiuApp captureEvent 相关主题判断（token 交集 + 每日上限）+ 偏好变更提醒；简报入口（悬浮球菜单或欢迎页卡）

- [ ] **Step 1: 写失败测试**（ChatWindow 动态卡渲染 + 点击信号、PixiuApp 相关主题提醒触发/抑制/上限、DeliveryController 状态机）
- [ ] **Step 2: 运行验证失败**（ctest 红）
- [ ] **Step 3: 实现**（transport 方法 + DeliveryController + ChatWindow 欢迎页 + PixiuApp 接线）
- [ ] **Step 4: 运行验证通过**（`QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend --output-on-failure` → 32+ 绿）
- [ ] **Step 5: 提交** `git commit -m "feat(frontend): delivery insights and relevance reminders"`

---

## Task B4-4: i18n + 双路径回归 + 文档收尾

**Covers:** [S4, S6]

**Files:**
- Modify: `frontend/resources/i18n/pixiu_en_US.ts/.qm`（新文案「今日简报」「已记住 文件 %1（与您近期的 %2 相关）」等）
- Modify: `docs/API.md`（若 B4-1/2 已写则核对一致性）、`README.md`（主动服务亮点更新）
- Test: 回归

- [ ] **Step 1: lupdate/lrelease**（cd frontend/resources/i18n && lupdate ../../src ../../tests -no-obsolete -locations none -ts pixiu_en_US.ts，0 unfinished）
- [ ] **Step 2: 文档更新**（README 主动服务/递送层亮点；API.md 核对）
- [ ] **Step 3: 全量回归**：`bash frontend/scripts/regression.sh`（OFF/ON）+ 后端全量 pytest（后台轮询）
- [ ] **Step 4: 提交**（i18n 与 docs 分开）

---

## 执行顺序

B4-1 → B4-2（后端，可并行勘察）→ B4-3（前端，依赖 B4-1 契约）→ B4-4 收尾。每任务独立提交供两阶段审查；契约以 docs/API.md 为唯一事实源。
