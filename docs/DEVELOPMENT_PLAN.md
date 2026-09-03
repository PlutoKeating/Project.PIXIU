# PIXIU 开发计划与分工

> 本文档定义 PIXIU 项目的模块划分、团队分工、契约边界与开发规范。
> 所有开发人员必须阅读并理解本文档后方可开始编码。

---

## 1. 项目概述

**PIXIU（貔貅）**—— 面向银河麒麟 OS Agent 的去中心化分布式记忆系统。

- **目标**：多设备记忆共享、神经-符号混合检索（≤500ms）、偏好动态捕捉、安全与精准遗忘
- **截止**：按官方平台文字方案的精确节点，2026-09-15 前向发榜单位提交；PPT 的“10 月上旬”作为赛事阶段概览共同留档，不覆盖精确节点
- **团队**：4人（2-3名开发 + 1-2名支持/测试）

### 1.1 平台兼容与验收基线

1. 银河麒麟桌面操作系统 V11 是 PPT 硬门槛；不满足计 0 分。正式赛题验收必须
   验证最终安装包、系统 Embedding 接口和系统向量数据库 SDK 的真实生产调用。
2. Debian 系发行版是强制兼容基线。没有 KylinSDK/UKUI 时，前端以纯 Qt5
   编译，后端以 `PIXIU_EMBEDDING=auto` 自动选择可移植软件向量器，核心写入、
   检索、同步和 API 不得因专有 SDK 缺失而整体不可用。
3. 专有能力必须通过适配层和能力探测接入；严格验收可设置
   `PIXIU_EMBEDDING=kylin` 使 SDK 缺失立即失败，通用验证可设置 `portable`。
4. 开发依据优先级：仓库归档的 `docs/kylin_sdk_docs/` → `third_party/` 官方 SDK
   submodule 源码/头文件 → `build/release/profiles/` 已验证平台事实。
5. CI 必须持续验证 Debian 系通用构建；麒麟真机/自托管 runner 验证单独记录，
   不能用软件降级测试冒充 KylinSDK 验收。

### 1.2 2026-09-03 赛题复核后的 P0 纠偏

> **决策状态：已批准。** 华南理工大学 PIXIU 团队负责人已批准
> [ADR-0001](decisions/0001-use-openkylin-agent-host.md)。下列 Agent 宿主和
> Module E 适配路线是后续开发基线，不再是待选建议；它仍不是赛方指定技术路线。

此前“各模块全部完成/全项达标”只描述既定记忆子系统范围，不能外推为赛题完成。
当前必须优先完成：

1. 系统 Vector Engine 接管生产向量建库、写入、删除和查询；公共 `VectorStore`、
   双适配器、生产注入与 strict/auto/portable 选择已实现，当前 P0 是 V11 真服务
   端到端和 capabilities 取证；SQLite INT8 扫描只保留降级/对照。
2. 最终版本在 V11 严格画像同时真实调用指定 Embedding 与 Vector Engine，并生成可复现证据。
3. 工程上复用 `third_party/kylin-agent` 与 `third_party/kylin-agent-runtime`，实现
   原创 MemoryProvider 适配；这不是赛方指定技术路线。不得把上游开源软件原样作为作品提交。
4. 跑通多轮会话、自主规划、Shell/联网搜索/其他工具、记忆召回与工具结果回写闭环。
5. 用至少三台设备证明分布式记忆的离线、并发、重连、冲突、遗忘和最终收敛。

在上述 P0 完成前，历史 portable 指标仅标记“开发回归通过”，不得写“最终验收达标”。

### 1.3 已批准路线的交付顺序

| 顺序 | 工作包 | 主责 | 完成定义 |
|------|--------|------|----------|
| 1 | H-02 Vector Engine 生产接线 | B + C | 建库、写入、删除、查询均走指定 SDK；严格模式缺失即失败 |
| 2 | H-03 Embedding 与 V11 严格画像 | B + D | 最终包在 V11 真实调用，日志/链接/失败测试可复现 |
| 3 | Module E MemoryProvider 适配 | E | 生命周期映射、显式记忆工具、能力探测与审计通过契约测试 |
| 4 | 完整 Agent 闭环 | E + D | 多轮→自主召回→工具/Shell/搜索→结果回写→新会话复用 |
| 5 | 分布式创新实证 | C + D | 至少三设备完成离线/并发/重连/冲突/遗忘/收敛矩阵 |
| 6 | 单一安装包与版本/升级闭环 | A + C + E + D | V11 图形安装；GUI 签名升级、健康检查、恢复和数据保留通过 |
| 7 | 最终文档与答辩 | D + Human | D-01～D-10、源码、PPT、视频、许可证和原创边界证据同版且审核完成 |

不得用“适配器已创建”替代第 4 步端到端结果，也不得在第 1～2 步失败时宣称赛题
验收通过。各工作包的证据编号以 `AcceptanceTestSpecification.md` 为准。

### 1.4 交付治理入口

单一 `.deb`、GUI 一键升级、版本/兼容矩阵、恢复策略和 D-01～D-10 文档状态统一
维护在 `DELIVERY_PLAN.md` 与 `delivery/`。所有最终材料必须绑定同一候选 commit；
工作稿结构完成不等于最终证据已审核。

从 H-02 到最终 Release 的阶段门、依赖关系、逐切片完成定义和提交顺序统一维护在
[`IMPLEMENTATION_MASTER_PLAN.md`](IMPLEMENTATION_MASTER_PLAN.md)。开发人员领取任务前
必须确认其前置阶段门；模块历史进度不得覆盖主计划中的当前阻断状态。

### 1.5 当前进度总览（2026-08-07 · 历史基线）

> 本节为 2026-08-07 历史基线，仅作进度回溯；最新状态见 §1.6。

| 模块 | 负责人 | 当前状态 | 已实现 | 待实现 |
|------|--------|----------|--------|--------|
| A · frontend | 团队负责人 | ❌ 未开始 | — | 悬浮球/聊天框/记忆面板/设备配对等全部内容（见 `frontend/docs/DEV_TASKS.md`） |
| B · engine | @Ø是铯 | ✅ 核心管线已实现并集成 | ingest/knowledge/conflict/security/preference 全部 Service；core 契约对齐（ULID ID、版本化）；真实麒麟 SDK 绑定源码（pybind11） | 麒麟环境 SDK 绑定构建与端到端验证；向量库检索接入 |
| C · foundation | @17% | 🟡 Phase 1 完成 | core 契约 + config/idgen/logger；SQLite 存储（schema/migrations/5 仓储）；API 网关部分真实端点；WS 推送 | retrieval 混合检索（`/memory/query`）；flow 记忆流转；sync CRDT；eval 评测 |
| D · tests/support | @捌嘎君 | ❌ 未开始 | foundation 侧测试已由集成工作补齐（229 项全绿） | 测试数据集、性能压测、验收评测报告（见 `backend/docs/SUPPORT_TASKS.md`） |

**已完成的集成工作（integration/backend-v0.2 → main，2026-08-07）**

- 契约扩展：`list_active / get_by_key / find_entity_by_name / list_relations` 已加入 core ABC 与 SQLite 实现
- 引擎全面切换到 foundation core 契约（core 模型 / ULID ID / 仓储语义 / 偏好版本化）
- API 网关真实 DI 注入引擎 Service；`/memory/write`、`/preference/extract`、`/preference/{id}/history`、`/forget`、`/conflicts` 已实现真实逻辑
- 移除全部 mock（`engine/mocks`、`MockEmbedding`、`PIXIU_EMBEDDING=mock`），接入麒麟 SDK（官方仓库以 submodule 纳入 `third_party/`）
- 测试：229 项通过（含引擎 × SQLite 全链路集成测试与 API 端点测试）

### 1.6 记忆子系统历史进度总览（2026-08-29，不代表赛题完成）

> 本节是赛题复核前的记忆子系统快照：同步网络批次（SN-1..SN-7）与被动监控
> 四批次（①掌控层 → ②目录监视 → ③行为偏好 → ④递送层）已全部完成并合入 main；
> §1.5 为 2026-08-07 历史基线，§1.7 保留 2026-08-10 的分支同步摘要。

| 模块 | 负责人 | 当前状态 | 已实现 | 待实现 / 阻塞 |
|------|--------|----------|--------|--------|
| A · frontend | 团队负责人 | ✅ 全部完成（含四批次前端） | Qt5/CMake 桌面应用：悬浮球/聊天框/记忆面板/遗忘/设置/配对/同步 Tab；监控中心双 Tab 面板 + 三处暂停入口 + 徽标；确认式配对（发现+弹窗确认）+ 同步 Tab 全量管理（整网退出）；洞察卡/「今日简报」/相关主题提醒；i18n 279 条 0 未完成；ctest 32/32 + `regression.sh` 双路径绿 | 真实麒麟会话人工复测（全局快捷键真机按键、xprop 方言验证） |
| B · engine | @Ø是铯 | ✅ 核心管线 + 行为采集/冲突分级/递送层完成 | ingest/knowledge/conflict/security/preference 全部 Service；BehaviorCollector（USER_BEHAVIOR 证据，敏感标题 fail-closed）；冲突 severity 三态映射；DeliveryInsights/DeliveryDigest；麒麟 SDK 绑定（embedding/OCR）本机构建成功 | 麒麟环境端到端验证（embedding/OCR 真机调用）；离线文本生成（麒麟 apt 源无对应 SDK 包，持续缺口） |
| C · foundation | @17% | 🟡 旧范围完成，Agent 公共契约已供 E 消费 | core/storage/api（含 `/version`/`/health`）、retrieval、六类生命周期 context、失败 receipt 一次性恢复授权、flow、sync P2P CRDT、eval、monitor、D-Bus | 长期化策略/日志贯通；麒麟真实 SDK 性能与局域网互操作 |
| D · tests/support | @捌嘎君 | 🟡 portable 回归完成，赛题验收未完成 | foundation+engine 757 passed；Module E 契约 16 passed；前端 ctest 37/37；portable 基线 100%/100%/96%/115ms | H-01～H-03、完整 Agent、V11 双 SDK 和多设备最终验收 |

### 1.7 2026-08-10 分支同步摘要

> 以下两个分支相对 `main`（748636b）各有新提交，均已 fetch 到本地 `origin/*`，
> 尚未合入 main，也尚未同步到本地工作分支（`feat/foundation` 落后 23、
> `feature/frontend` 落后 102）。

#### feat/foundation（Module C · @17%，作者 xzy，23 commits，2026-08-07 ~ 08-10）

| 更新位置 | 内容 |
|----------|------|
| `backend/foundation/retrieval/` | 混合检索 MVP 落地并加固：路由/FTS5 BM25/INT8 ANN/图召回/三通道并发/RRF 融合/词法重排/组装；`/memory/query` 已真实上线；实体-知识链接持久化 |
| `backend/foundation/flow/` | 记忆流转 Phase 2：短/中期上下文持久化、批量预校验与幂等 promote、长期知识 demote、TTL 清理；`/memory/flow/promote` 真实接入 |
| `backend/foundation/sync/` | P2P CRDT 同步 Phase 3 全部组件：Ed25519 身份、QR/PIN 配对、mDNS 信任过滤、TLS 1.3 mTLS、签名协议、Gossip、反熵、LWW+版本向量、墓碑回收、物化器、运行时与调度；`/sync/*` 4 个端点真实接入 |
| `backend/foundation/eval/` | 评测框架 Phase 4/5：6 项验收指标 + recall@1/3/5、P50/P95/P99、scope 隔离；同步收敛与系统资源基准；stub 自检：收敛率 1.0、同步 P95 55ms |
| `backend/foundation/api/` | D-Bus 服务 `com.kylin.pixiu.Memory` 实现（Write/Query/Forget/SyncStatus 镜像 HTTP）；桌面传输与共享服务对齐；`/events` 广播扩展至 sync/conflict 事件 |
| `backend/foundation/storage/` `core/` | schema 扩至 16 张表（sync_identity/peers/state/acks/meta）；仓储持久化 knowledge↔entity 链接；核心契约加固 |
| 测试与文档 | foundation+engine 测试全绿（麒麟 V11 真机 pytest 377 passed）；PHASE0~4、BASELINE、ACCEPTANCE、任务书/架构更新；`docs/compose/spec/` 阶段规格 6 份 |

**未完成 / 遗留**：麒麟真实 embedding + 正式数据集的召回率/P95 验收（当前为 stub
基线 P95=13.3ms）；真实局域网多设备互操作；**WS `/events` 注册问题仍未修复**（见下方阻塞项）。

#### feature/frontend（Module A · 团队负责人，作者 2728113182-ship-it，102 commits，2026-08-07 ~ 08-10）

| 更新位置 | 内容 |
|----------|------|
| `frontend/src/`（70 个文件） | Qt5 应用全量实现：悬浮球（自由拖拽/角标/右键菜单）、侧边聊天窗（欢迎页/建议卡/多行输入/证据卡/骨架屏）、记忆面板（偏好/冲突/同步三 Tab）、遗忘/录入/设置/配对/解绑对话框、EventRouter、SyncController、健康探测、主题感知图标 |
| `frontend/tests/`（30 个文件 + 契约套件） | QtTest 双路径（KYSDK OFF/ON）31/31 全绿；端到端回归（首击、窗口恢复等）与后端契约一致性测试；自动回归脚本 `scripts/regression.sh` |
| `frontend/resources/` | 设计令牌/全局 QSS/主题感知图标/内嵌 pixiu.svg/i18n（en_US 180 条 0 未完成） |
| `frontend/docs/`（85 个文件） | 任务书/架构/执行计划/UI_UX_POLISH/适配报告更新 + 真实桌面截图（明暗主题、UI 演示 36 张） |
| `frontend/debian/` `scripts/` | `.deb` 打包 + desktop 入口；WS 演示桩与桌面复验脚本 |

**未完成 / 阻塞**：真实麒麟会话人工复测（全局快捷键真实按键触发、HiDPI/多屏）；
后端契约未落地部分（偏好列表、证据详情、二维码配对令牌、flow 上下文来源、真实
同步数据、真实 WS 事件广播）。

#### 跨模块阻塞项（Module A → C 交接，状态核实于 2026-08-10）

`frontend/docs/BACKEND_ISSUES.md` 记录的两项 `/events` 注册/导入问题已于
2026-08-20 修复，并通过 TestClient 与麒麟 V11 安装包真实握手复测。
`memory_ready`/`sync_event` 已具备广播路径；`conflict_detected` 与
`forget_confirmation` 事件补齐仍是跨模块缺口。

### 1.8 打包发布与测试交付（2026-08-11 更新）

**全量 deb 打包 + CICD 脚手架（`build/release/`，main 分支）**

- 一条命令产出整包 .deb：`make -C build/release deb`（前端构建+ctest → 后端
  源码随包 → 目标 Python ABI 离线 wheels → dpkg 打包），发布用
  `publish-staging` / `publish-production`。
- 目标平台画像 `profiles/`（麒麟 V11 x86_64 / 通用 Ubuntu）把发行版事实全部
  编码（apt 包名、Python ABI、KYSDK 可用性），禁止一次性手工补丁。
- 麒麟实测中沉淀的修复：PEP 668 pip 自举、`--ignore-installed`（RECORD 缺失包）、
  profile 优先级、后端顶层包 `backend` 的 PYTHONPATH、uvicorn CLI 启动、
  `apt-get install ./deb`（dpkg 锁等待）、HTTP 级就绪等待、
  `PIXIU_SYNC_KEY_PASSPHRASE` ≥16 字符默认值（后端强制要求，否则 `/sync/*` 500）、
  前端单实例守护（冒烟前先结束桌面实例）。

**麒麟 V11 历史验证（2026-08-11）**

- 安装：apt 预置 + `apt-get install ./deb` 一次通过，依赖从包内 wheels 离线安装。
- 后端：`pixiu-backend.service` active，`/conflicts` 200，SQLite 库自动创建；
  当时版本全量 pytest **377 passed**。
- 前端：真实桌面窗口映射确认，团队负责人验收"整体比较丝滑"。
- 已发布 GitHub staging Release：`v0.1.0-staging`（附 deb + sha256）。

**下一步（按优先级）**

1. 引擎麒麟 SDK 绑定构建（Module B）→ 重新出包后写入/检索/同步链路即通。
2. 后端 WS `/events` 注册修复（Module C）→ 前端实时事件链路复测。
3. 麒麟 SDK 开发环境就绪后 `PIXIU_KYSDK=ON` 出原生版（原生快捷键/通知）。
4. 正式验收：性能压测（P95≤500ms、召回率≥85%）、验收评测报告。

---

## 2. 模块划分

整个系统按**架构维度**拆分为 **4 个开发模块 + 1 个支持岗位**，模块间零代码交叉。

```
┌──────────────────────────────────────────────────────────┐
│  模块 A: UKUI 桌面客户端 (frontend/)                       │  C++17 · Qt5 · KylinSDK
│  负责：悬浮球 · 聊天框 · 记忆面板 · 设备配对 · IPC 通信      │
│  与后端契约：仅通过 `docs/API.md` 定义的全部 REST API + WS 事件通信     │
└────────────────────────┬─────────────────────────────────┘
                         │  ★ 固定 API 契约（JSON over HTTP / D-Bus）
                         │  前端不引用后端一行代码
                         ▼
┌──────────────────────────────────────────────────────────┐
│  模块 B: 记忆业务引擎 (backend/engine/)                    │  Python 3.10
│  负责：多源接入·偏好捕捉·知识结构化·冲突仲裁·安全遗忘·       │
│        KylinSDK embedding 封装                             │
│  与模块 C 契约：消费 foundation/core 的 Repository 接口     │
└────────────────────────┬─────────────────────────────────┘
                         │  ★ Repository 接口契约 (ABC)
                         │  引擎只调接口不调实现
                         ▼
┌──────────────────────────────────────────────────────────┐
│  模块 C: 后台基础设施 (backend/foundation/)                │  Python 3.10 + SQL + C++
│  负责：API网关·存储层·混合检索·记忆流转·P2P同步·评测框架    │
│  与模块 B 契约：提供 core/ 接口；在 api/ 中注入引擎 Service  │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  模块 E: Agent 集成适配 (integrations/kylin_agent/)        │  Python · MemoryProvider
│  负责：生命周期映射 · 记忆工具 · 能力探测 · 运行审计        │
│  与 A/B/C 契约：仅消费 docs/API.md，不跨目录导入私有实现    │
└──────────────────────────────────────────────────────────┘

  支持岗 D (scripts/ + tests/):
    测试数据集 · 评测框架 · 文档补全 · 集成测试
```

### 2.1 模块 A — UKUI 桌面客户端

| 属性 | 说明 |
|------|------|
| 目录 | `frontend/` |
| 技术栈 | C++17, Qt5 Widgets, KylinSDK (kysdk-shortcut, kysdk-notification, theme, 扩展控件) |
| 开发人员 | 1人（Qt/C++ 桌面开发） |
| 与其他模块 | **零代码依赖** — 仅通过 HTTP REST / WebSocket / D-Bus 调用后端 API |
| 自身完整 | 含完整 src/（widgets/services/models/app）+ CMakeLists.txt + resources/ |

**对外契约**：`docs/API.md` 中定义的全部端点（当前 27 个 REST + WS）及其请求/响应 JSON 结构。

**状态（2026-08-11）**：独立功能与 UI/UX polish 全部完成（双路径 ctest 31/31、
i18n 180 条、`.deb` 打包）；剩余项为真实麒麟会话人工复测与后端契约阻塞，
详见 §1.7。

**状态（2026-08-29）**：被动监控四批次前端 + 同步网络前端全部落地——监控中心
双 Tab 面板与三处暂停入口、确认式配对（发现+弹窗确认）、同步 Tab 全量管理
（总开关/暂停/整网退出/立即同步）、洞察卡/「今日简报」/相关主题提醒；
ctest 32/32、i18n 279 条 0 未完成；见 §1.6。

### 2.2 模块 B — 记忆业务引擎

| 属性 | 说明 |
|------|------|
| 目录 | `backend/engine/` |
| 技术栈 | Python 3.10, C++17 (pybind11, KylinSDK embedding 封装) |
| 开发人员 | 1人（Python 后端，偏业务逻辑/数据处理/AI） |
| 子包 | `ingest/`, `preference/`, `knowledge/`, `conflict/`, `security/`, `kylin/` |
| 依赖的契约 | `foundation/core/` 中的 Repository 抽象接口和数据模型 |

**职责**：实现全部业务逻辑——多源数据清洗标准化、偏好动态捕捉与版本化、知识结构化整合与实体关系建图、冲突检测与仲裁、敏感识别与自然语言遗忘、麒麟 coreai/embedding 真实调用（pybind11 绑定，无 mock 降级）。

**状态（2026-08-07）**：核心管线已实现并完成集成；真实 SDK 绑定源码就绪，待麒麟环境构建验证。

**状态（2026-08-11）**：无新增实现变更；麒麟 V11 真机全量测试 377 passed，
整包 .deb 已随包安装引擎源码，SDK 绑定构建待验证。

**状态（2026-08-29）**：新增行为采集（USER_BEHAVIOR 证据，B3-1）、冲突 severity
三态映射（B3-3）、递送层 insights/digest（B4-1/B4-2）；麒麟 SDK 绑定
（embedding/OCR）已在本机构建成功；见 §1.6。

**Agent 记忆契约进展（2026-09-03）**：新增第 5 类 `CONVERSATION` Connector；
对话与 Agent 工具结果可把 session/run/turn/tool-call/审批/时间作为独立 provenance
写入 evidence；schema v12 receipt 已保证完成态重试不重复执行，并提供失败请求的
显式风险确认、原载荷校验、一次性授权及持久审计。Module E 已消费写入契约；专用
语义策略及真实宿主取证仍待完成。

### 2.3 模块 C — 后台基础设施

| 属性 | 说明 |
|------|------|
| 目录 | `backend/foundation/` |
| 技术栈 | Python 3.10, SQLite (WAL+FTS5), hnswlib/sqlite-vec, asyncio |
| 开发人员 | 1人（Python 后端，偏检索/存储/分布式系统） |
| 子包 | `core/`, `api/`, `storage/`, `retrieval/`, `flow/`, `sync/`, `eval/` |
| 提供的契约 | `core/` 中的数据模型和 Repository 接口（ABC） |

**职责**：实现全部基础设施——API 网关（HTTP/WS/D-Bus）、SQLite 存储实现（仓储模式）、混合检索管线（BM25∥ANN∥Graph→融合→重排→组装）、短中/长期记忆流转、P2P CRDT 分布式同步、量化评测框架。

**状态（2026-08-11）**：Phase 0~7 全部完成（功能冻结）——retrieval（`/memory/query`）、
flow（`/memory/flow/promote`）、sync（`/sync/*`）、eval（评测框架+基准）、
D-Bus 服务与 request_id 统一错误契约均已落地，麒麟 V11 真机 377 项测试通过；
剩余为麒麟真实 SDK 性能验收与真实局域网互操作。

**状态（2026-08-29）**：sync 网络运行时默认开启（SN-4）+ 确认式配对/mainline 仲裁
（SN-1..SN-3）、monitor daemon（目录监视 + 配置热生效 + 行为采集）与递送层端点
（/delivery/*）全部落地；25 个 REST 端点 + 六类 WS 事件真实实现；后端 pytest
673 passed；见 §1.6。

**Agent 记忆契约进展（2026-09-03）**：`/memory/write` 已校验并传递结构化 Agent
provenance，SQLite schema v12 完成兼容迁移、持久化幂等 receipt 与审计式失败恢复；
关联日志/查询和长期化仍待完成。六类 context 生命周期端点已实现；写入入口已接入
Security detector，`user:*` 敏感 evidence 本地隔离，`shared:*` 敏感写入与检测故障
均 fail closed。

### 2.4 支持岗 D — 测试与工具

| 属性 | 说明 |
|------|------|
| 目录 | `backend/scripts/`, `backend/tests/` |
| 技术栈 | Python, Shell |
| 开发人员 | 1人（测试 / 运维 / 工具开发） |
| 对其他模块 | 零依赖，可使用 mock 独立工作 |

**职责**：测试数据集构造、单元/集成测试、性能压测、环境变量模板、评测脚本、文档补全。

**状态（2026-08-11）**：测试侧已由 A/C 模块补齐（麒麟 V11 真机 foundation+engine
377 passed、frontend ctest 31/31）；打包发布脚手架已交付（`build/release/`，
已发布 `v0.1.0-staging`）；正式支持工作（测试数据集、性能压测、
验收评测报告）尚未开工。

**状态（2026-08-29 portable 范围）**：开发回归支持工作完成——自建测试数据集 `pixiu-family-expense-v1`
（50 检索 + 15 偏好 + 25 冲突）、性能压测（检索 P95 115ms ≤500ms）、验收评测报告
`docs/acceptance/`（portable 路径达到数值阈值，不代表赛题最终验收）；后端 pytest 673 passed；见 §1.6。

### 2.5 模块 E — Agent 集成适配

**目录**：`integrations/kylin_agent/`（已建立独立 Provider、客户端、工具与契约测试）

| 子领域 | 内容 |
|--------|------|
| `provider` | 实现 `agent-runtime` MemoryProvider 生命周期 |
| `client` | 封装 PIXIU HTTP/WS 公共契约、超时、重试与错误映射 |
| `tools` | 查询、记住、遗忘、同步状态等显式记忆工具 |
| `capabilities` | 探测后端、V11、Embedding、Vector Engine 严格状态 |
| `audit` | 通过 provenance、幂等键和本地诊断计数关联召回、写入与生命周期 |

不得把 Agent 循环复制进本模块；不得导入 `frontend/` 或 `backend/` 私有代码；
不得直接修改 `third_party/` 工作树；不得把上游通用 Agent 功能计为团队原创。
vNext Agent 记忆契约已先在 `docs/API.md` 冻结并由 Module E 消费。当前 9 项测试覆盖
固定上游 ABC/插件发现、strict 能力预检、缓存召回、异步写入/背压、生命周期、工具、
遗忘确认和错误脱敏；安装包接入与 W5 真实 Agent 场景仍未完成。

---

## 3. 契约定义

### 3.1 前端 ↔ 后端的 API 契约

唯一定义在 `docs/API.md`。包含：

- 全部 REST 端点（当前 24 个）的路径、方法、请求体/响应体 JSON Schema
- WebSocket 事件名称与 payload 格式
- 错误码枚举

**变更规则**：修改 API 必须有 Module A + Module C 两人签字同意，更新 `docs/API.md` 后通知全员。

### 3.2 引擎 ↔ 基础设施的 Repository 契约

定义在 `backend/foundation/core/repository.py`（Python ABC）。

```python
class EvidenceRepository(ABC):
    @abstractmethod
    async def save(self, evidence: Evidence) -> str: ...
    @abstractmethod
    async def get(self, id: str) -> Optional[Evidence]: ...

class KnowledgeRepository(ABC):
    @abstractmethod
    async def save(self, item: KnowledgeItem) -> str: ...
    @abstractmethod
    async def get(self, id: str) -> Optional[KnowledgeItem]: ...
    @abstractmethod
    async def search_fts(self, query: str, limit: int) -> list[KnowledgeItem]: ...
    @abstractmethod
    async def search_by_title(self, query: str, limit: int) -> list[KnowledgeItem]: ...
    @abstractmethod
    async def save_vector(self, knowledge_id: str, dim: int, vec: bytes) -> None: ...
    @abstractmethod
    async def update_status(self, id: str, status: KnowledgeStatus) -> None: ...
    @abstractmethod
    async def list_active(self) -> list[KnowledgeItem]: ...

class PreferenceRepository(ABC):
    @abstractmethod
    async def save(self, pref: Preference) -> str: ...
    @abstractmethod
    async def get_history(self, pref_id: str) -> list[PreferenceSnapshot]: ...
    @abstractmethod
    async def get_by_key(self, key: str, scope: str) -> Optional[Preference]: ...

class EntityRepository(ABC):
    @abstractmethod
    async def save_entity(self, entity: Entity) -> str: ...
    @abstractmethod
    async def save_relation(self, src: str, dst: str, type: str) -> None: ...
    @abstractmethod
    async def find_entity_by_name(self, name: str) -> Optional[Entity]: ...
    @abstractmethod
    async def list_relations(self) -> list[Relation]: ...

class ConflictRepository(ABC):
    @abstractmethod
    async def save(self, record: ConflictRecord) -> str: ...
    @abstractmethod
    async def list(self) -> list[ConflictRecord]: ...
```

**变更规则**：Module B 提需求 → Module C 在 core/ 中实现接口定义 → 双方确认后冻结。任何变更必须两人同时同意。

### 3.3 模块 C 的 api/ 对引擎 Service 的依赖

唯一的跨模块 Python import 点：`backend/foundation/api/di.py`

```
foundation/api/di.py
  → from backend.engine.ingest import IngestionService
  → from backend.engine.preference import PreferenceService
  → from backend.engine.knowledge import KnowledgeService
  → from backend.engine.conflict import ConflictService
  → from backend.engine.security import SecurityService
```

**约束**：每个 Service 类的构造函数由 `di.py` 统一注入对应 Repository 与 embedder。

**状态（2026-08-07）**：`api/di.py` 已真实注入 5 个引擎 Service 与 SQLite 仓储实现。

---

## 4. 目录结构

```
Project.PIXIU/
├── README.md
├── AGENTS.md                       # AI Agent 开发规范
├── HUMANS.md                       # 人类协作者说明
├── .gitignore
│
├── docs/                           # 项目根文档
│   ├── ARCHITECTURE.md             # 总体架构（含模块边界）
│   ├── API.md                      # API 端点规格（前端↔后端契约）
│   ├── DEVELOPMENT_PLAN.md         # 本文档：开发计划与分工
│   ├── QUICK_START.md              # 快速启动指南
│   ├── OriginProblemDescription.md # 赛题原文
│   ├── AcceptanceTestSpecification.md  # 验收规范
│   ├── OS_AGENT_INTEGRATION_ASSESSMENT.md # Agent 选型与赛题差距
│   ├── DELIVERY_PLAN.md           # 安装、版本、升级和赛事交付文档台账
│   ├── delivery/                  # D-01～D-10 可审查工作源
│   ├── 完整赛题要求.pptx            # 2026.05 权威宣讲材料
│   └── kylin_sdk_docs/             # KylinSDK 参考（不动）
│
├── backend/                        # 后端全部源码
│   ├── docs/                       # 后端整体文档
│   │   ├── README.md               # 后端导读（指向 engine/ 和 foundation/）
│   │   └── ARCHITECTURE.md
│   │
│   ├── engine/                     ★ 模块 B：记忆业务引擎
│   │   ├── __init__.py
│   │   ├── ingest/                 # 多源数据接入
│   │   ├── preference/             # 偏好捕捉与版本化
│   │   ├── knowledge/              # 知识结构化 + 实体关系图
│   │   ├── conflict/               # 冲突仲裁
│   │   ├── security/               # 敏感识别 + 精准遗忘
│   │   ├── kylin/                  # 麒麟 SDK 适配（embedding + 向量库，cpp/ 为 pybind11 绑定）
│   │   ├── tests/                  # 引擎测试（SQLite 集成 + 测试桩）
│   │   └── docs/                   # 本模块开发文档
│   │       ├── README.md
│   │       ├── ARCHITECTURE.md
│   │       ├── DEV_TASKS.md
│   │       └── QUICK_START.md
│   │
│   ├── foundation/                 ★ 模块 C：后台基础设施
│   │   ├── __init__.py
│   │   ├── core/                   # 共享契约（数据模型 + Repository 接口）
│   │   ├── api/                    # API 网关
│   │   ├── storage/                # SQLite 仓储实现
│   │   ├── retrieval/              # 混合检索管线
│   │   ├── flow/                   # 记忆流转
│   │   ├── sync/                   # P2P CRDT 同步
│   │   ├── eval/                   # 评测框架
│   │   └── docs/                   # 本模块开发文档
│   │       ├── README.md
│   │       ├── ARCHITECTURE.md
│   │       ├── DEV_TASKS.md
│   │       └── QUICK_START.md
│   │
│   ├── scripts/                    ★ 支持岗 D：工具脚本
│   ├── tests/                      ★ 支持岗 D：测试
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                       ★ 模块 A：UKUI 桌面客户端
│   ├── src/                        # 所有 C++ 源码
│   ├── docs/                       # 本模块开发文档
│   │   ├── README.md
│   │   ├── ARCHITECTURE.md
│   │   ├── DEV_TASKS.md
│   │   └── QUICK_START.md
│   ├── resources/                  # 图标、QSS 样式、i18n
│   ├── CMakeLists.txt
│   └── .env.example

├── integrations/
│   └── kylin_agent/                ★ 模块 E：Agent/MemoryProvider 适配与契约测试

├── third_party/                    # openKylin 官方源码/SDK submodule
│   ├── kylin-agent/                # 官方桌面 Agent 参考/目标宿主
│   ├── kylin-agent-runtime/        # 官方 Agent 运行时与 MemoryProvider 接口
│   ├── kylin-coreai-embedding/     # 文本向量化 SDK（C API）
│   └── libkysdk-vector-engine-client/  # 向量数据库客户端（C++/gRPC）
```

---

## 5. 开发规范

### 5.0 本地环境准备（强制）

所有开发者在本地开工前必须补齐仓库内的官方麒麟 SDK submodule：

```bash
git submodule update --init --recursive
```

未补齐 `third_party/` 下 submodule 前，禁止进行涉及 SDK 的构建、测试与提交。

### 5.1 文件归属铁律

| 开发人员 | 只能修改 | 严禁触碰 |
|----------|----------|----------|
| 模块 A | `frontend/` 下所有文件 | `backend/` 下任何文件 |
| 模块 B | `backend/engine/` + `backend/foundation/core/`（仅接口） | `backend/foundation/api/storage/retrieval/flow/sync/eval/` |
| 模块 C | `backend/foundation/`（除 engine 子包） | `backend/engine/` 下任何文件 |
| 支持 D | `backend/scripts/`, `backend/tests/`, `docs/`（补全） | `frontend/src/` |
| 模块 E | `integrations/kylin_agent/` 下所有文件 | `frontend/`、`backend/`、`third_party/` 下任何文件 |

Module E 只通过公共 API 与后端交互。若 API 不足，由 E 提交契约需求，A/C 更新
`docs/API.md` 并实现；不得以赶进度为由直接 import 后端 Service 或 Repository。

### 5.2 接口变更流程

1. 任何需要修改契约的变更，必须先提 Issue/Discussion
2. 相关模块的负责人必须在 24h 内 review 并回复
3. 双方确认后，同时在各自分支实现适配
4. 未达成一致前不得提交涉及契约修改的代码

### 5.3 提交规范

- 遵循 `AGENTS.md` 中的 Git 规则
- 提交信息必须标注模块前缀：`feat(engine/ingest):`, `fix(foundation/retrieval):`, `feat(frontend):`
- 禁止跨模块的混合提交

---

## 6. 各模块开发参考文档

### 模块 A 开发者必读

| 文档 | 路径 | 说明 |
|------|------|------|
| 前端架构 | `frontend/docs/ARCHITECTURE.md` | UI 设计、组件树、交互流程 |
| 前端开发任务书 | `frontend/docs/DEV_TASKS.md` | 具体实现清单 |
| API 契约 | `docs/API.md` | 前后端通信端点规格 |
| KylinSDK 快捷键 | `docs/kylin_sdk_docs/8_Desktop_Environment_SDK/8.3_Hotkey_Module.md` | 全局快捷键 |
| KylinSDK 通知 | `docs/kylin_sdk_docs/8_Desktop_Environment_SDK/8.2_Notification_Module.md` | 桌面通知 |
| KylinSDK 主题 | `docs/kylin_sdk_docs/8_Desktop_Environment_SDK/8.5_Theme_Module.md` | 主题跟随 |
| KylinSDK 扩展控件 | `docs/kylin_sdk_docs/4_Application_Support_SDK/4.1.x_*.md` | Qt 控件参考 |

### 模块 B 开发者必读

| 文档 | 路径 | 说明 |
|------|------|------|
| 引擎架构 | `backend/engine/docs/ARCHITECTURE.md` | 引擎内部设计 |
| 引擎开发任务书 | `backend/engine/docs/DEV_TASKS.md` | 具体实现清单 |
| 共享数据模型 | `backend/foundation/core/`（代码） | Repository 接口与 Pydantic 模型 |
| KylinSDK 向量化 | `docs/kylin_sdk_docs/9_AI_SDK/9.4.3_Vectorization.md` | embedding 接口 |
| KylinSDK OCR | `docs/kylin_sdk_docs/9_AI_SDK/9.4.1_OCR.md` | OCR 文字识别 |
| KylinSDK 文本生成 | `docs/kylin_sdk_docs/9_AI_SDK/9.5.1_Text_Generation.md` | 偏好/知识离线抽取 |

### 模块 C 开发者必读

| 文档 | 路径 | 说明 |
|------|------|------|
| 基础设施架构 | `backend/foundation/docs/ARCHITECTURE.md` | Foundation 内部设计 |
| 基础设施开发任务书 | `backend/foundation/docs/DEV_TASKS.md` | 具体实现清单 |
| 总体架构 | `docs/ARCHITECTURE.md` | 系统全貌 |

### 支持岗 D 必读

| 文档 | 路径 | 说明 |
|------|------|------|
| 验收规范 | `docs/AcceptanceTestSpecification.md` | 全部验收条目 |
| 赛题原文 | `docs/OriginProblemDescription.md` | 比赛要求与附录 A 场景 |
| 最终交付计划 | `docs/DELIVERY_PLAN.md` | 单一安装包、版本/升级与 D-01～D-10 台账 |

### 模块 E 开发者必读

| 文档/源码 | 路径 | 说明 |
|-----------|------|------|
| 已批准决策 | `docs/decisions/0001-use-openkylin-agent-host.md` | 宿主、原创与修改边界 |
| 接入评估 | `docs/OS_AGENT_INTEGRATION_ASSESSMENT.md` | 代码事实、生命周期与差距 |
| API 契约 | `docs/API.md` | 当前端点与尚未实现的 vNext 目标 |
| Agent runtime | `third_party/kylin-agent-runtime/` | 固定版本 MemoryProvider/生命周期源码 |
| Agent desktop | `third_party/kylin-agent/` | 固定版本 run/SSE/设置集成源码 |

---

## 7. 附录：旧设计文档的 M 前缀映射

> 以下为参考对照，供理解历史文档与当前模块的对应关系。

| 旧 M 编号 | 旧名称 | 现属模块 | 现目录 |
|-----------|--------|---------|--------|
| M1 | 多源数据接入 | 模块 B | `backend/engine/ingest/` |
| M2 | 偏好动态捕捉 | 模块 B | `backend/engine/preference/` |
| M3 | 知识结构化整合 | 模块 B | `backend/engine/knowledge/` |
| M4 | 冲突仲裁 | 模块 B | `backend/engine/conflict/` |
| M5 | 混合检索 | 模块 C | `backend/foundation/retrieval/` |
| M6 | 记忆流转 | 模块 C | `backend/foundation/flow/` |
| M7 | 安全与遗忘 | 模块 B | `backend/engine/security/` |
| M8 | 评测框架 | 模块 C | `backend/foundation/eval/` |
| — | KylinSDK 适配 | 模块 B | `backend/engine/kylin/` |
| — | 分布式同步（CRDT） | 模块 C | `backend/foundation/sync/` |
| — | API 网关 | 模块 C | `backend/foundation/api/` |
| — | 存储层 | 模块 C | `backend/foundation/storage/` |
| — | 共享契约 | 模块 C | `backend/foundation/core/` |
