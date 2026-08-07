---
feature: foundation-bootstrap
status: delivered
updated: 2026-07-29
branch: feature/foundation-bootstrap
commits: fde244b..10f5650
---

# Foundation Bootstrap — Module C Phase 1

## Report

**What was built** — Module C（后台基础设施）第一阶段引导完成。交付了三个子包共 14 个实现文件 + 2 个配置/依赖文件：

- `core/` 共享契约层 — 9 个 Pydantic v2 数据模型（含 `@field_validator` ID 格式校验）、5 个 ABC Repository 接口、8 个 ULID 前缀 ID 生成器、统一日志工具。Module B（引擎）可据此并行开发。
- `storage/` SQLite 存储层 — 12 张表的全量 DDL（WAL 模式）、5 个基于 aiosqlite 的异步 Repository 实现类（含 FTS5 全文检索、偏好版本快照、实体关系图操作、冲突审计 CRUD）。
- `api/` API 网关骨架 — FastAPI 应用注册 11 个占位端点（与 `docs/API.md` 规格一一对应）、WebSocket `/events` 端点 + 30s 心跳 + `WsManager` 单例广播、DI 依赖注入骨架（惰性 aiosqlite 连接 + 5 个 Service 占位工厂）、D-Bus 服务类声明。

额外交付 `backend/.env.example`（6 个环境变量，作为 `core/config.py` 的唯一真相源）和 `backend/requirements.txt`（fastapi, uvicorn, pydantic, aiosqlite, pytest）。

**Verification** — Python 运行时不在此环境中可用，无法执行 `init_db()`、`uvicorn` 启动或 pytest。已完成以下静态验证：
- 文件结构：16 个文件全部创建，与 Spec 一一对应
- 导入完整性：无循环依赖，相对导入路径正确
- 变量名一致性：`.env.example` ↔ `di.py`/`logger.py` 中的 `os.getenv` 引用全部一致
- 独立审查（2 轮）：首轮发现 3 个关键缺陷（C1: ID 校验未接入模型；C2: conflict_records DDL 缺少 field 列；C3: FTS5 rowid 类型不匹配），第二轮确认全部修复通过

**Journey log**
1. FTS5 `content=` 外部内容表模式中，`rowid` 必须为整数匹配内容表行号，不能使用业务主键字符串。容易忽略的陷阱。
2. Pydantic v2 的 `@field_validator` 须显式导入，`class Config` 已废弃为 `model_config`。
3. 审查循环首轮发现 3 关键缺陷，修复后第二轮通过 — 证明两轮审查在无运行时环境下的价值。第一个 commit（`fde244b..09e52d6`）为基础实现，第二个 commit（`09e52d6..10f5650`）为审查修复。
4. `.env.example` 作为变量名真相源的设计决策 — 后续 `core/config.py` 必须与此文件保持一致。
5. `backend/requirements.txt` 初始为空，本次补充了 Minimal 依赖集。

## [S1] Problem

`backend/foundation/` 七个子包目录已建但均为空壳（仅有空 `__init__.py`），Module B 无法对接，后续的检索、同步、流转开发也无限期阻塞。第一阶段必须交付 core/（共享契约）、api/（API 网关骨架）、storage/（SQLite 存储层），使 Module C 具备独立可运行的最小系统。

## [S2] Design

### S2.1 core/ — 共享契约

**文件清单**：

`core/models.py` — Pydantic v2 数据模型，含 `Evidence`, `KnowledgeItem`, `Preference`, `PreferenceSnapshot`, `Entity`, `Relation`, `ConflictRecord`, `MemoryAtom`, `SyncOp`。所有模型使用 `BaseModel`，字段类型严格，`id` 字段格式校验（前缀匹配正则）。

`core/repository.py` — 五个 ABC 接口：
- `EvidenceRepository`: `save(Evidence) -> str`, `get(str) -> Optional[Evidence]`, `delete(str) -> None`, `list_by_scope(str, int, int) -> list[Evidence]`
- `KnowledgeRepository`: `save(KnowledgeItem) -> str`, `get(str) -> Optional[KnowledgeItem]`, `delete(str) -> None`, `search_fts(str, int) -> list[KnowledgeItem]`, `list_by_status(str) -> list[KnowledgeItem]`, `link_evidence(str, str) -> None`
- `PreferenceRepository`: `save(Preference) -> str`, `get(str) -> Optional[Preference]`, `get_history(str) -> list[PreferenceSnapshot]`, `list_by_category(str) -> list[Preference]`
- `EntityRepository`: `save_entity(Entity) -> str`, `get_entity(str) -> Optional[Entity]`, `save_relation(str, str, str) -> None`, `get_relations(str) -> list[Relation]`, `find_entity_by_name(str) -> Optional[Entity]`
- `ConflictRepository`: `save(ConflictRecord) -> str`, `get(str) -> Optional[ConflictRecord]`, `list(Optional[int], int) -> list[ConflictRecord]`, `resolve(str, str) -> None`

`core/config.py` — **暂不实现**。后续实现时 `os.getenv` 读取的环境变量名必须与 `backend/.env.example` 完全一致（见 S2.4）。

`core/idgen.py` — 前缀+ULID 生成器，每个实体类型一个函数：`gen_evidence_id()`, `gen_knowledge_id()`, `gen_pref_id()`, `gen_conflict_id()`, `gen_device_id()`, `gen_sync_op_id()`, `gen_entity_id()`, `gen_request_id()`。所有 ID 可读可排序。

`core/logger.py` — 统一日志配置，`get_logger(name)` 返回配置好的 `logging.Logger`，输出到 stdout。

### S2.2 api/ — API 网关骨架

**文件清单**：

`api/http_app.py` — FastAPI 应用实例，注册全部 11 个 REST 路由（不含 WS），每个路由返回 `{"status": "not_implemented"}` 占位响应 + OpenAPI metadata。路由按 `docs/API.md` 规格注册：
- `POST /memory/write`
- `POST /memory/query`
- `POST /preference/extract`
- `GET /preference/{id}/history`
- `POST /forget`
- `GET /conflicts`
- `POST /memory/flow/promote`
- `POST /sync/pair`
- `GET /sync/peers`
- `GET /sync/status`
- `POST /sync/peers/{id}/revoke`

`api/ws.py` — WebSocket `/events` 端点，接受连接后发送欢迎消息 `{"event": "connected"}` 并维持心跳（30s ping）。后续各模块通过 `ws_manager` 单例推送事件。

`api/di.py` — 依赖注入骨架。工厂函数返回 Service 实例（当前用 `None`/mock 占位，引擎包尚不存在时不会崩溃）。`get_db()` 返回 `aiosqlite` 连接。

`api/dbus_service.py` — 占位（仅有 docstring 和类声明），D-Bus 集成留到后续阶段。

### S2.3 storage/ — SQLite 存储层

**文件清单**：

`storage/schema.py` — DDL 全量建表脚本，`init_db(path)` 创建 WAL 模式数据库。包含所有 12 张表：
- `evidence`, `knowledge_items`, `knowledge_evidence`（关联表）
- `knowledge_fts`（FTS5 虚拟表）
- `knowledge_vec`（INT8 向量表）
- `entities`, `relations`
- `preferences`, `preference_history`
- `conflict_records`
- `sync_oplog`

`storage/repository.py` — 五个 SQLite 实现类，全部基于 `aiosqlite` 异步操作：
- `SqliteEvidenceRepo(EvidenceRepository)`
- `SqliteKnowledgeRepo(KnowledgeRepository)`
- `SqlitePreferenceRepo(PreferenceRepository)`
- `SqliteEntityRepo(EntityRepository)`
- `SqliteConflictRepo(ConflictRepository)`

每个类构造函数接收 `db: aiosqlite.Connection`，方法返回类型与 ABC 定义完全一致。JSON 字段使用 `json.dumps/loads` 序列化。FTS5 搜索使用 `MATCH` 语法。

### S2.4 backend/.env.example — 团队配置模板

文件位置 `backend/.env.example`，向队友声明本项目需要的全部环境变量及其默认值。**变量名必须与 `core/config.py` 完全一致**，形成唯一的真相源：

```bash
# PIXIU Foundation — 环境变量配置模板
# 复制为 backend/.env 后按需修改，切勿提交真实 .env 文件

# SQLite 数据库路径
PIXIU_DB_PATH=./pixiu.db

# API 网关监听地址与端口
PIXIU_API_HOST=127.0.0.1
PIXIU_API_PORT=8765

# Embedding 后端：mock（本地测试无需麒麟 SDK）/ kylin（调用 coreai/embedding）
PIXIU_EMBEDDING=mock

# 日志级别：DEBUG / INFO / WARNING / ERROR
PIXIU_LOG_LEVEL=INFO

# 数据目录（证据文件、缓存等）
PIXIU_DATA_DIR=./data
```

## [S3] Out of Scope

- 检索管线（retrieval/）— Phase 2
- 记忆流转（flow/）— Phase 3
- P2P 同步（sync/）— Phase 3
- 评测框架（eval/）— Phase 3
- D-Bus 完整实现 — 仅占位
- 引擎 Service 对接（di.py 仅骨架，不 import engine）
- 端到端集成测试
- 数据库迁移框架 — 当前仅全量建表

## Tasks

- [x] T1: 实现 core/models.py — 全部 9 个 Pydantic 数据模型，id 格式校验，类型安全 (covers: S2.1)
- [x] T2: 实现 core/repository.py — 5 个 ABC 接口，含完整方法签名和 abstractmethod 装饰 (covers: S2.1)
- [x] T3: 创建 backend/.env.example — 团队配置模板，变量名作为后续 config.py 的唯一真相源 (covers: S2.4)
- [x] T4: 实现 core/idgen.py + core/logger.py — ULID 前缀 ID 生成、统一日志 (covers: S2.1)
- [x] T5: 实现 core/__init__.py — 导出全部模型、接口、ID 生成器、日志（不含 config） (covers: S2.1)
- [x] T6: 实现 storage/schema.py — 建表 DDL + WAL 模式 init_db(path) (covers: S2.3)
- [x] T7: 实现 storage/repository.py — 5 个 SQLite Repository 类，全部 CRUD + FTS5 搜索 + 关联操作 (covers: S2.3; depends: T1, T2, T6)
- [x] T8: 实现 storage/__init__.py — 导出全部 Repository 类 (covers: S2.3)
- [x] T9: 实现 api/http_app.py — FastAPI 应用 + 11 个占位路由 (covers: S2.2)
- [x] T10: 实现 api/ws.py — WebSocket /events 端点 + 心跳 (covers: S2.2)
- [x] T11: 实现 api/di.py + api/dbus_service.py — DI 骨架 + D-Bus 占位 (covers: S2.2)
- [x] T12: 实现 api/__init__.py — 导出 app, ws_manager (covers: S2.2)
- [x] T13: 验证 — 静态结构检查通过，审查 2 轮（3 关键缺陷 → 已修复） (covers: S2.1, S2.2, S2.3; depends: T5, T8, T12)
