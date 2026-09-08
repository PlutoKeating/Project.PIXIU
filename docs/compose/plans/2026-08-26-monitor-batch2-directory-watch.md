# 批次② · 目录监视闭环 Implementation Plan

> 2026-09-06 代码复核：监控配置、目录/行为采集和 HTTP/WS/UI 已接通；图片 OCR 需要另行可用的原生扩展，剪贴板/截图开关不等于采集器已实现。当前服务为 systemd --user。
> 下文实施步骤、旧接口草图和测试数字保留作阶段历史，不作为当前操作手册；当前契约见 docs/API.md，发布见 docs/DELIVERY_PLAN.md。

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通「用户指定目录 → 新文件落地 → 自动识别入库 → 捕获事件推送 → 前端活动记录/通知」的被动监控核心闭环，对齐赛题附录 A 的 T0 场景（清单图片落地即入库）。

**Architecture:** 后端 MonitorConfigStore、DirectoryWatcher 和公开 monitor 接口提供配置、采集及日志；正式前端为唯一宿主 PrivacyPage，使用 HttpBackendTransport 和 BackendEventStatus。配置只由后端持久化，失败保留未保存草稿，不再使用已删除的 PixiuApp/旧监控中心或本地授权镜像。敏感捕获只写私有 user:*，仍可能已经入库。

**Tech Stack:** Python 3.12 · FastAPI · watchdog(inotify) · SQLite(既有 storage 层) | C++17 · Qt5 · QtTest(offscreen)

## Global Constraints

- **模块边界**：Plan-BE 由 Module B/C 授权执行（本计划获批即视为团队负责人授权）；Plan-A 只改 `frontend/`。两侧通过 MONITOR_API_REQUIREMENTS.md 契约对齐，任何契约变更须双向确认并回写 docs/API.md。
- **验收口径**：麒麟 V11 真机可演示「向受监视目录放入 PNG 支出清单 → 数秒内聊天区活动记录出现『记住文件 ×××』且 /memory/query 可检索」；后端 pytest 全绿；前端 OFF/ON 双路径 ctest 全绿 + regression.sh。
- **隐私铁律**：sensitivity>0 的捕获不落 shared:*、summary 不含原文全文；daemon 关停配置持久；前端离线时展示本地缓存的上次配置。
- **effective 开关语义**：采集器层自行实现 effective = 总闸 && 单源开关（控制器/UI 故意不做门控）。
- 提交前缀 `feat(monitor)/feat(frontend)/test(...)`；禁止 force-push；个人分支同步一律 `--ff-only`。
- 前端按 ADR-0006 的唯一宿主实现对接，旧监控控制器及双 Tab 面板已删除；当前契约见 docs/API.md 和 frontend/docs/MONITOR_API_REQUIREMENTS.md。

---

## Plan-BE（后端 · Module B/C）

### Task BE-1: MonitorConfigStore 配置存储与热生效

**Files:** Create `backend/foundation/monitor/__init__.py`、`config_store.py`；Modify `backend/foundation/storage/schema.py`（monitor_config KV 表或复用 settings 表）；Test `backend/foundation/tests/test_monitor_config.py`

**Interfaces:** `MonitorConfigStore(db)` — `.get() -> dict(enabled,sources,directories)`、`.put(dict) -> dict`（校验 source 名白名单、directories 去空去重去相对路径；非法抛 `InvalidMonitorConfig`）；`.subscribe(cb)` 供 runtime 注册热生效回调。

Steps: 失败测试（roundtrip/白名单拒绝/去重/订阅回调）→ 实现（SQLite KV JSON）→ pytest 绿 → 提交 `feat(monitor): persistent config store with validation`。

### Task BE-2: DirectoryWatcher 采集器

**Files:** Create `backend/foundation/monitor/watcher.py`、`ingest_bridge.py`；Test `backend/foundation/tests/test_directory_watcher.py`

**Interfaces:** `DirectoryWatcher(config_store, ingest_bridge)` — `.start()/.stop()`；内部 watchdog Observer 监视 directories（recursive=False）；防抖 500ms + 稳定性检查（文件大小 2 次采样不变）；忽略隐藏文件与临时后缀（.part/.tmp/~）；事件回调 `on_capture(source,status,summary,evidence_id,knowledge_id,ts)`。`IngestBridge`：图片 → 既有 OCR 服务（POST 内部直调 engine ocr adapter）→ 组装 MANUAL 风格 raw{title=文件名,text}；文本(.txt/.md/.csv ≤1MB) → 读文本入 ingest；两者均走既有 /memory/write 同进程管线函数（复用 api 层 service 注入），产出 evidence_id/knowledge_id；异常吞掉记日志不中断监视。

Steps: 用 tmp_path+真实 watchdog 的集成测试（写入 png mock ocr、写入 txt、写入 .tmp 忽略、总闸关不捕获）→ 实现 → pytest 绿 → 提交 `feat(monitor): directory watcher with debounce and ocr/text ingest`。

### Task BE-3: API 三端点 + capture_event 广播

**Files:** Modify `backend/foundation/api/http_app.py`（GET/PUT /monitor/config、GET /monitor/log）；Create `backend/foundation/api/monitor_log.py`（events 写 SQLite monitor_log 表 + 分页查询）；Modify ws 广播处（对齐既有 memory_ready 广播路径）；Modify `docs/API.md`（契约从需求单转正，标注双方确认日期）；Test 扩展 `backend/foundation/tests/test_api.py`

**Interfaces:** 见 frontend/docs/MONITOR_API_REQUIREMENTS.md §1–§3（字段一字不改）；PUT 成功后调用 watcher.apply_config 热生效；每次捕获写 monitor_log 并广播 capture_event；GET /monitor/log 支持 limit≤500 默认 100、offset。

Steps: 契约测试（PUT→GET roundtrip、非法 400、log 分页、WS TestClient 收到 capture_event）→ 实现 → 全量 pytest 绿 → 提交 `feat(monitor): expose monitor config/log endpoints and capture_event broadcast`。

### Task BE-4: systemd 集成与真机冒烟

**Files:** Modify `build/release/debian/pixiu.env`（可选 PIXIU_MONITOR_ENABLED=1 默认开）；文档 `frontend/docs/MONITOR_API_REQUIREMENTS.md` 状态行更新为 ✅ 已实现（2026-08-XX）

Steps: 本机 systemd 重启 pixiu-backend → mkdir 受监视目录 → 落一张测试图 → curl /monitor/log 断言 ingested 记录 → 记录实测输出到提交说明。提交 `chore(monitor): enable monitor service in packaging profile`。

---

## Plan-A（前端 · Module A）

### Task A-1: Transport 扩展（默认空实现模式）

**Files:** Modify `frontend/src/services/BackendTransport.h/.cpp`（虚函数 monitorConfig()/updateMonitorConfig(payload)/monitorLog(limit,offset) 默认空实现；信号 configResult(QJsonObject)/monitorLogResult(QJsonArray)）；Modify `frontend/src/services/HttpBackendTransport.h/.cpp`（GET/PUT /monitor/config、GET /monitor/log 解析，容忍未知字段）；Test 扩展 `frontend/tests/t_contract_fixtures.cpp`（TCP 桩补三组契约形状，取自 MONITOR_API_REQUIREMENTS.md）

**Interfaces:** 沿用契约文档 §5 签名；错误经既有 errorOccurred。

Steps: 桩测试先行红 → transport 实现 → 契约用例绿 → 提交 `feat(frontend): add monitor transport contract`。

### Task A-2: EventRouter 路由 capture_event

**Files:** Modify `frontend/src/app/EventRouter.h/.cpp`（isKnownBusinessEvent 加 capture_event；信号 `captureEvent(QString source, QString status, QString summary, qint64 ts)`）；Modify `frontend/src/services/WebSocketClient.cpp` kKnownEvents 集合同步；Test 扩展 `frontend/tests/t_event_router.cpp`（正常帧/未知帧/data 缺失三态）

Steps: 红 → 实现 → 绿 → 提交 `feat(frontend): route capture_event frames`。

### Task A-3: 远端配置优先 + 活动日志接入 UI

**Files:** frontend/management/PrivacyPage.{h,cpp}、BackendEventStatus.{h,cpp} 与正式管理回归。配置须读取后显式保存；日志按公共接口分页，事件只触发过期标记，不自动拼接为权威历史、不覆盖草稿。剪贴板/自动截图明确未实现；敏感事件不额外触发未接入的隔离区通知。

验证：保留配置门控、来源字段保留、失败草稿、目录选择、日志和退出保护的正式用例；旧 t_monitor_center/t_app_navigation 不再存在，不恢复相应目标。

### Task A-4: i18n 再生成 + 双路径回归 + 真机联调记录

同批次① Task 5 流程；另在 DEMO_GUIDE.md 追加批次②演示脚本（附录 A 场景）。提交 `chore(frontend): regenerate i18n for capture feed` 与 docs 提交。

---

## 执行顺序与协调点

BE-1→BE-2 可并行于 A-1/A-2（纯契约先行）；A-3 依赖 BE-3 联调环境（无后端时用 demo_stub_server.py 扩展 monitor 桩先行开发）。每任务独立提交供审查；跨模块冲突由团队负责人裁决。
