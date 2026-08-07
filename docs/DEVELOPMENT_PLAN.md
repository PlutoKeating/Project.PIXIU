# PIXIU 开发计划与分工

> 本文档定义 PIXIU 项目的模块划分、团队分工、契约边界与开发规范。
> 所有开发人员必须阅读并理解本文档后方可开始编码。

---

## 1. 项目概述

**PIXIU（貔貅）**—— 面向银河麒麟 OS Agent 的去中心化分布式记忆系统。

- **目标**：多设备记忆共享、神经-符号混合检索（≤500ms）、偏好动态捕捉、安全与精准遗忘
- **截止**：2026年9月15日（挑战杯作品提交）
- **团队**：4人（2-3名开发 + 1-2名支持/测试）

### 1.5 当前进度总览（2026-08-07）

> 本小节随实际开发状态持续更新；各模块详细任务清单见模块内 `DEV_TASKS.md`。

| 模块 | 负责人 | 当前状态 | 已实现 | 待实现 |
|------|--------|----------|--------|--------|
| A · frontend | 团队负责人 | ❌ 未开始 | — | 悬浮球/聊天框/记忆面板/设备配对等全部内容（见 `frontend/docs/DEV_TASKS.md`） |
| B · engine | @Ø是铯 | ✅ 核心管线已实现并集成 | ingest/knowledge/conflict/security/preference 全部 Service；core 契约对齐（ULID ID、版本化）；真实麒麟 SDK 绑定源码（pybind11） | 麒麟环境 SDK 绑定构建与端到端验证；向量库检索接入 |
| C · foundation | @17% | 🟡 Phase 1 完成 | core 契约 + config/idgen/logger；SQLite 存储（schema/migrations/5 仓储）；API 网关部分真实端点；WS 推送 | retrieval 混合检索（`/memory/query`）；flow 记忆流转；sync CRDT；eval 评测 |
| D · tests/support | @捌嘎君 | ❌ 未开始 | foundation 侧测试已由集成工作补齐（229 项全绿） | 测试数据集、性能压测、Docker 容器化、评测报告（见 `backend/docs/SUPPORT_TASKS.md`） |

**已完成的集成工作（integration/backend-v0.2 → main，2026-08-07）**

- 契约扩展：`list_active / get_by_key / find_entity_by_name / list_relations` 已加入 core ABC 与 SQLite 实现
- 引擎全面切换到 foundation core 契约（core 模型 / ULID ID / 仓储语义 / 偏好版本化）
- API 网关真实 DI 注入引擎 Service；`/memory/write`、`/preference/extract`、`/preference/{id}/history`、`/forget`、`/conflicts` 已实现真实逻辑
- 移除全部 mock（`engine/mocks`、`MockEmbedding`、`PIXIU_EMBEDDING=mock`），接入麒麟 SDK（官方仓库以 submodule 纳入 `third_party/`）
- 测试：229 项通过（含引擎 × SQLite 全链路集成测试与 API 端点测试）

---

## 2. 模块划分

整个系统按**架构维度**拆分为 **3 个开发模块 + 1 个支持岗位**，模块间零代码交叉。

```
┌──────────────────────────────────────────────────────────┐
│  模块 A: UKUI 桌面客户端 (frontend/)                       │  C++17 · Qt5 · KylinSDK
│  负责：悬浮球 · 聊天框 · 记忆面板 · 设备配对 · IPC 通信      │
│  与后端契约：仅通过 12 个预定义 REST API + WS 事件通信       │
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

  支持岗 D (scripts/ + tests/):
    测试数据集 · 评测框架 · Docker 容器化 · 文档补全 · 集成测试
```

### 2.1 模块 A — UKUI 桌面客户端

| 属性 | 说明 |
|------|------|
| 目录 | `frontend/` |
| 技术栈 | C++17, Qt5 Widgets, KylinSDK (kysdk-shortcut, kysdk-notification, theme, 扩展控件) |
| 开发人员 | 1人（Qt/C++ 桌面开发） |
| 与其他模块 | **零代码依赖** — 仅通过 HTTP REST / WebSocket / D-Bus 调用后端 API |
| 自身完整 | 含完整 src/（widgets/services/models/app）+ CMakeLists.txt + resources/ |

**对外契约**：`docs/API.md` 中定义的 12 个端点及其请求/响应 JSON 结构。

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

### 2.3 模块 C — 后台基础设施

| 属性 | 说明 |
|------|------|
| 目录 | `backend/foundation/` |
| 技术栈 | Python 3.10, SQLite (WAL+FTS5), hnswlib/sqlite-vec, asyncio |
| 开发人员 | 1人（Python 后端，偏检索/存储/分布式系统） |
| 子包 | `core/`, `api/`, `storage/`, `retrieval/`, `flow/`, `sync/`, `eval/` |
| 提供的契约 | `core/` 中的数据模型和 Repository 接口（ABC） |

**职责**：实现全部基础设施——API 网关（HTTP/WS/D-Bus）、SQLite 存储实现（仓储模式）、混合检索管线（BM25∥ANN∥Graph→融合→重排→组装）、短中/长期记忆流转、P2P CRDT 分布式同步、量化评测框架。

**状态（2026-08-07）**：Phase 1（core/storage/api）完成；Phase 2（retrieval）、Phase 3（flow/sync/eval）待实现。

### 2.4 支持岗 D — 测试与工具

| 属性 | 说明 |
|------|------|
| 目录 | `backend/scripts/`, `backend/tests/` |
| 技术栈 | Python, Shell, Docker |
| 开发人员 | 1人（测试 / 运维 / 工具开发） |
| 对其他模块 | 零依赖，可使用 mock 独立工作 |

**职责**：测试数据集构造、单元/集成测试、性能压测、Docker 容器化、环境变量模板、评测脚本、文档补全。

**状态（2026-08-07）**：尚未开工；`backend/.env.example` 已由 foundation 阶段补充。

---

## 3. 契约定义

### 3.1 前端 ↔ 后端的 API 契约

唯一定义在 `docs/API.md`。包含：

- 12 个 REST 端点的路径、方法、请求体/响应体 JSON Schema
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
│   ├── Dockerfile
│   ├── docker-compose.yml
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
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── .env.example

├── third_party/                    # 第三方依赖（官方麒麟 SDK submodule）
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
