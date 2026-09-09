# 模块 C · 后台基础设施 —— 开发任务书

> **目录**：`backend/foundation/`
> **开发人员**：1人

---

## 实现状态（2026-08-11 旧范围冻结；赛题 P0 已重新打开）

> [!IMPORTANT]
> 2026-09-04 按完整 PPT 复核后，Vector Engine 接线与 Module E 已实现并取得阶段性
> 实证；user service/依赖已随包实现，最终 V11 双 SDK 性能和模型驱动 Agent 场景仍是 P0；不得继续使用“功能冻结后不新增”
> 阻止这些必需整改。以下完成项仅描述旧记忆子系统范围。

### ✅ 已完成（Phase 0～Phase 7）

- `core/`：`models.py`（11 个 Pydantic 模型，含 AgentProvenance/FileCaptureSource；另有枚举/校验）、`repository.py`（5 个 ABC，
  含集成期扩展：`list_active` / `get_by_key` / `find_entity_by_name` / `list_relations`）、
  `config.py`（`auto`/`kylin`/`portable` 能力选择）、`idgen.py`（9 个 ULID 生成器）、`logger.py`
  （request_id + 敏感过滤）
- `storage/`：`schema.py`（20 张基础表 + FTS5/向量表惰性创建）、`migrations.py`（v14 版本化迁移，含 evidence provenance、Agent 幂等 receipt、恢复审计与独立文件采集来源列）、
  `repository.py`（5 个 SQLite 仓储，含 evidence/entity 回填、偏好版本化、冲突读写修复）
- `api/`：全部 REST 契约端点真实接入（含 `/sync/*`），request_id 中间件 + API.md §5
  统一错误契约（`{error, message, request_id}`），D-Bus 服务（`com.kylin.pixiu.Memory`：
  Write/Query/Forget/SyncStatus 复用共享 Service，bus name 冲突处理）；
  `ws.py` + `ws_manager.py` 事件推送，`di.py` 组装真实服务与仓储
- `retrieval/`：路由、FTS5 BM25、INT8 向量召回、持久化图召回、三通道并发、
  scope/time_range 硬过滤、RRF 融合、词法重排、查询类别聚合与 evidence 回溯
- `flow/`：短/中期上下文持久化、批量预校验与幂等 promote、长期知识可逆 demote、
  分层 TTL 和到期内容清理
- `sync/`：加密 Ed25519 身份、QR/PIN 配对、LWW+vclock、反熵、ACK/墓碑回收、
  mDNS 信任过滤、TLS 1.3 mTLS、Gossip 重传、远端物化及默认开启的运行时（SN-4）；
  远端首次物化的知识也进入 `source=sync` 语义仲裁，稳定全序保证反向收包结果一致；
  shared 本地冲突写入会在仲裁后重读持久化条目，确保 oplog 携带最终正文和版本；
  快进/更新/自动仲裁产物复用 KnowledgeService 重建图与向量，墓碑同步删除向量；
  knowledge 先到时持久登记待补 evidence，跨批次后到后自动补链并清理；
  三份独立数据库的三节点回归已覆盖离线节点补墓碑、旧操作重放防复活和全活跃
  节点 ACK 后安全回收；新增去载荷 CRDT 状态端点供真实设备核验墓碑，最终真机矩阵仍待取证
- `eval/`：评测引擎（Recall@1/3/5、P50/P95/P99、scope 隔离、聚合/追溯/冲突/偏好指标）、
  基准框架（CRDT 收敛率/同步耗时/DB/内存/CPU，runtime=stub|kylin 双结果）、CLI 与报告
- **Phase 7 验收**：四条端到端故事全通过；WAL 并发/并发 embedding/错误契约/脱敏/迁移/
  崩溃恢复/资源边界硬化测试；1000 次查询压测 P95=19.18ms（≤500ms PASS）
- 2026-09-06 最新通用 CI：Python 3.12/3.13 各 823 项 pytest 通过；历史分模块统计不作为当前数量。Foundation 356 + Engine 21 = 377 仅为 2026-08-11 快照。

### 🔴 赛题 P0 待完成

- `retrieval/` + `eval/` 环境验收：麒麟机器上真实 embedding 跑 reference-v1（50 组数据集、
  90 查询、1000 压测），验证召回≥85%、P95≤500ms，产出 runtime="kylin" 报告
- 双 SDK 原生绑定、user service 与组件依赖已随包落地；最终候选仍需原生性能报告。
- openKylin Agent/Runtime 可重建离线供应链已有实现与审阅证据；最终模型驱动多轮/工具结果场景需归档。

其中 Agent 接入的 Module C 责任已由团队批准并冻结为：

- C-A1：提供可判定 V11、Embedding、Vector Engine 实际 runtime 的 capability 契约。
  `GET /capabilities` 已实现配置/实际分栏与脱敏平台判定，严格双 SDK 启动预检已接入；
  `/version` 与 `/health` 已提供产品/API/schema/数据库就绪握手，Module E 已校验
  runtime 0.9.x、组件身份和同包版本；`api/install_health.py` 已把安装后的已装版本、
  后端/schema/数据库与包内 Provider 一致性接入特权升级 helper。该判定不包含发布
  签名或旧包自动回滚。
- C-A2：🟡 session_id/run_id/turn_id/tool_call_id/审批/时间已贯通到 evidence、写入
  API 和 schema v10；schema v12 已实现完成态幂等、冲突拒绝与审计式失败恢复。日志、
  按关联 ID 查询仍待完成；`POST /agent/context` 已提供 session/turn 回显、
  scope/敏感过滤、预算、freshness、冲突状态与 evidence 引用。
- C-A3：🟡 `/agent/lifecycle` 已提供六类短/中期 context 创建、完成态幂等与独立
  命名空间失败恢复；既有 promote/demote/TTL 清理可复用。Module E 真实触发与更新
  策略仍待完成。
- C-A4：Vector Engine 成为严格画像的生产向量 Repository；SQLite/INT8 仅为降级。

进度：C-A4 的公共 `VectorStore` seam 与 `SqliteVectorStore` portable 适配器已实现，
生产 DI 的知识写入和 ANN 查询已注入并通过禁用旧扫描的端到端组合根测试；Kylin
Kylin 适配与 strict/auto/portable 选择已完成；生产遗忘已注入 seam 并在确认后
删除向量；组合根已改用官方 `ConnectParam(appId)` 本地传输，不再传递测试专用
host/port；当前源码还会在 strict 预检时装载 `PIXIU_VECTOR_DB_PATH`，进程级复用
store 并在退出时断开，修复旧探针“capabilities 假绿、首次写入无 local storage”的
问题。`GET /capabilities` 已报告实际适配器。提交 `6f6002e` 的 revision 8 已完成
V11 产品写入、检索、遗忘与隐藏；最终 user service/安装依赖和正式取证仍未完成。
- C-A5：与 Module E 做 HTTP/WS 契约测试，禁止 E 直接导入本模块。

> Module A 三通道联调与 WS `/events` 注册已在 2026-08-29 前完成，已从当前 P0
> 清单删除；历史段落仅作过程记录，不再视为阻塞项。

> 下文的文件清单为任务定义与优先级；已实现项以"实现状态"为准。

---

## 开工要求（本地环境准备）

开始开发前，**必须先补齐仓库内的官方麒麟 SDK submodule**：

```bash
git submodule update --init --recursive
```

- `third_party/kylin-coreai-embedding` —— 文本向量化 SDK（C API）
- `third_party/libkysdk-vector-engine-client` —— 向量数据库客户端（C++/gRPC）

未补齐 submodule 时，依赖 SDK 的绑定构建与验证无法进行，请勿跳过此步骤。

---

## 第一阶段：核心契约与骨架

### core/ —— 共享契约（最先实现，B 和 C 双方都依赖）

范围校验已修复点号范围无法进入 Evidence/KnowledgeItem/Preference 的不一致，
并使用完整字符串匹配拒绝尾随换行；保留输入原值及同步的私有域拒绝规则。
回归复用现有 `test_models.py` 与通用 CI 的 Foundation 测试目录，无新增依赖、
构建目标或 schema 迁移；入口长度限制及真实安装数据链路仍需验证。

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `core/__init__.py` | ★★★ | 导出全部模型和接口 |
| `core/models.py` | ★★★ | 所有 Pydantic 数据模型（Evidence, KnowledgeItem, Preference, Entity, Relation, ConflictRecord, MemoryAtom, SyncOp...） |
| `core/repository.py` | ★★★ | 全部 Repository ABC 接口（EvidenceRepository, KnowledgeRepository, PreferenceRepository, EntityRepository, ConflictRepository） |
| `core/config.py` | ★★★ | 配置加载（环境变量：端口、数据库路径、embedding 后端类型） |
| `core/idgen.py` | ★★ | ID 生成器（带前缀：evd_, knw_, pref_, cfl_, dev_...） |
| `core/logger.py` | ★★ | 日志配置 |

### api/ —— API 网关

目录桥接新增私有 scope 构造前检，拒绝共享域及非法格式，保留合法自定义私有
域原值；复用已有核心校验器、pytest 与 CI 目录，无新依赖/构建目标/数据迁移。
文件来源元数据已通过独立参数接入，文本/OCR 方法、实际读取绝对路径与取得内容
后的时间戳保存至 schema v13 证据列；不解析符号链接，不改正文，不补猜历史路径。
目录/配置/API 的 70 项本地回归通过，含真实 watchdog 与 SQLite；OCR、embedding
使用隔离桩，不作麒麟能力验收。正式界面与原生新包验证仍待完成。复用现有后端
源码打包规则及依赖，无新增编译开关。

范围语法校验已前移至 HTTP 请求模型及查询参数；回归覆盖九个入口的非法范围
拒绝、数据库不变、点号私有域/已配置共享域写入与详情精确匹配。复用现有
Pydantic/FastAPI 和 CI 测试目录，无新增依赖、构建目标或迁移。各入口长度上限
统一仍待完成。非本机共享域写入/更新已增加失败前置检查，HTTP 回归对比完整
数据库快照，证明拒绝时没有新业务记录、身份或幂等收据；合法共享写入及同步
回归保留。遗忘确认也前置检查全部审核目标，回归覆盖显式共享域及私有/共享
混合目标，拒绝时完整数据库快照不变且凭证不能重放。HTTP 与 D-Bus 共用该
确认编排；其他修改路径和执行中途故障仍须核查，不宣称跨组件事务原子化。

管理编辑新增 `GET /memory/items/{knowledge_id}?scope=...` 完整快照读取。
API 回归覆盖长正文/嵌套数据不截断、读取不改变数据库、范围必填与非 ACTIVE 隐藏，
以及读取后被另一更新抢先提交时拒绝陈旧版本。此接口不代表桌面编辑交互已接入。

HTTP API 当前为 0.5.0：遗忘确认强制预览凭证，与旧无凭证调用不兼容；Provider
握手只接受 0.5.x。此版本不同于根产品 VERSION 和 Agent Memory API v1，不得在
发布探针或兼容夹具中混用。无新增依赖或数据库迁移。

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `api/__init__.py` | ★★★ | 导出 `app`（FastAPI 实例） |
| `api/http_app.py` | ★★★ | FastAPI 应用 + 全部路由注册 |
| `api/ws.py` | ★★ | WebSocket `/events` 处理 |
| `api/dbus_service.py` | ★ | D-Bus `com.kylin.pixiu.Memory` |
| `api/di.py` | ★★★ | 依赖注入容器（组装引擎 Service + foundation Repository） |

### storage/ —— 存储层

安全遗忘新增 `forget_if_versions` 原子批量 ID/版本检查；测试覆盖另一连接更新
版本、整批拒绝、缺失目标、成功版本递增和阻止旧版本 CAS 编辑。使用既有 SQLite
JSON 能力，无新增依赖或 schema 变更；HTTP 已接入一次性预览凭证，绑定指令、范围
与目标版本，缺失/过期/重放拒绝。其余调用方及跨组件恢复仍待迁移。

D-Bus 新增 `ReviewedForget(s)→s`，复用 HTTP 遗忘编排及显式 DI；旧无凭证确认
拒绝执行。回归覆盖旧入口拒绝、预览后执行、重放拒绝、共享墓碑和五方法注册。
测试不连接真实 session bus，真实总线与桌面客户端仍需验收。

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `storage/__init__.py` | ★★★ | 导出全部 Repository 类 |
| `storage/repository.py` | ★★★ | SQLite 实现全部 Repository 接口（5 个仓储类） |
| `storage/schema.py` | ★★★ | DDL 建表语句 + 索引创建 |
| `storage/migrations.py` | ★ | 数据库迁移 |
| `storage/vector_store.py` | ★★★ | portable INT8 `VectorStore` 适配器（写入/检索/删除） |
| `storage/vector_id_map.py` | ★★★ | Kylin int64 主键与知识 ULID 的持久化唯一映射 |

---

## 第二阶段：检索引擎

> 下列文件均已完成 MVP 与 Phase 1 加固；后续只保留银河麒麟原生性能验收。

### retrieval/ —— 混合检索

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `retrieval/__init__.py` | ★★★ | 导出 `RetrievalService` |
| `retrieval/router.py` | ★★★ | 意图分类 + 实体抽取 + 通道选择 |
| `retrieval/bm25.py` | ★★★ | FTS5 BM25 全文检索 |
| `retrieval/ann.py` | ★★★ | 委托注入的 VectorStore；strict 为系统 SDK，portable 为 SQLite INT8 |
| `retrieval/graph_search.py` | ★★★ | 实体关系图遍历（BELONG_TO 沿边聚合） |
| `retrieval/fuse.py` | ★★★ | RRF 融合 + context_hint 加权 |
| `retrieval/rerank.py` | ★★ | 词面重叠 + 业务年月匹配重排，无神经网络依赖 |
| `retrieval/assembler.py` | ★★★ | 结构化过滤 + 聚合计算 + evidence 回溯 |

---

## 第三阶段：同步与流转

### flow/ —— 记忆流转

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `flow/__init__.py` | ★★ | `FlowService` 门面与 demote 快照 |
| `flow/models.py` | ★★ | 短/中期上下文、层级与状态模型 |
| `flow/store.py` | ★★ | `memory_contexts` SQLite 持久化 |
| `flow/promoter.py` | ★★ | promote 预校验、沉淀与幂等逻辑 |
| `flow/ttl.py` | ★ | TTL 衰减策略 |

### sync/ —— P2P 同步

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `sync/__init__.py` | ★★ | 导出 `SyncService` |
| `sync/identity.py` | ★★ | 节点身份 + Ed25519 密钥对生成 |
| `sync/discovery.py` | ★ | mDNS 广告 + 已配对 peer 信任过滤 |
| `sync/pairing.py` | ★★ | 设备配对（扫码/PIN + 公钥交换） |
| `sync/transport.py` | ★ | TLS 1.3 双向加密传输 |
| `sync/crdt.py` | ★★★ | LWW-Element-Set + 版本向量合并 |
| `sync/anti_entropy.py` | ★★ | 反熵对账（digest 比对 + 补齐缺失） |
| `sync/gc.py` | ★ | tombstone 回收 |
| `sync/protocol.py` | ★★ | 已配对 sender + 签名 SyncOp 协议 |
| `sync/gossip.py` | ★★ | 有界 fanout、ACK 与持久化重传 |
| `sync/materializer.py` | ★★ | CRDT 胜者物化到本地仓储 |
| `sync/runtime.py` | ★ | 默认开启的 mDNS/mTLS 生命周期（缺配置自动降级）；停机取消当前轮次并完成资源清理 |
| `sync/scheduler.py` | ★ | 同步轮次调度 + 退避 |

### eval/ —— 评测框架

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `eval/__init__.py` | ★★ | 导出 `EvalService` |
| `eval/eval.py` | ★★ | 评测引擎（加载数据集→跑指标→输出报告） |
| `eval/dataset.py` | ★★ | 版本化参考数据集（`pixiu-family-expense-v1`）+ profile |
| `eval/metrics.py` | ★★ | 12 项指标（6 核心 + recall@1/3/5、P50/P95/P99、scope 隔离） |
| `eval/benchmark.py` | ★★ | SyncBenchmark / SystemBenchmark（收敛率/同步耗时/DB/内存/CPU） |
| `eval/service.py` | ★★ | BenchmarkService（runtime=stub\|kylin 双结果） |
| `eval/report.py` | ★★ | JSON+Markdown 报告原子写出（SHA-256） |
| `eval/reference.py` | ★★ | acceptance 数据集构建（50 检索/15 偏好/25 冲突/1000 样本） |
| `eval/models.py` | ★★ | EvalCase / MetricResult / BenchmarkReport 数据模型 |
| `eval/__main__.py` | ★★ | CLI：`python -m backend.foundation.eval` |

---

## 测试

| 文件 | 说明 |
|------|------|
| `tests/test_api.py` | 各 REST 端点的请求/响应测试 |
| `tests/test_storage.py` | SQLite 仓储实现测试 |
| `tests/test_retrieval.py` | 三通道 + 融合 + 重排 + 组装测试 |
| `tests/test_sync_core.py` | 身份、版本向量、LWW 与 SQLite 状态 |
| `tests/test_sync_service.py` | 配对、签名、反熵、GC 与调度 |
| `tests/test_sync_network.py` | mDNS 信任过滤、协议、Gossip、内存运行时 |
| `tests/test_sync_tls.py` | 仅 loopback 的 TLS 1.3 mTLS 集成测试 |
| `tests/test_sync_materializer.py` | 远端物化、墓碑与 scope 隔离 |
| `tests/test_flow.py` | promote/demote + TTL 测试 |
| `tests/test_eval.py` | 评测框架正确性测试 |
| `tests/test_benchmark.py` | 基准框架测试（收敛率/同步耗时/资源） |
| `tests/test_hardening.py` | Phase 7 硬化测试（WAL 并发/错误契约/脱敏/迁移/崩溃恢复/资源边界） |
| `tests/test_e2e_stories.py` | Phase 7 四条端到端故事 |
| `tests/test_dbus_service.py` | D-Bus 服务契约测试 |
| `tests/test_di.py` | 依赖注入组装测试 |
| `tests/test_config.py` / `test_idgen.py` | 配置与 ID 生成器测试 |
| `tests/test_schema.py` / `test_knowledge_repository.py` / `test_repository_contracts.py` | 存储契约测试 |
| `tests/test_sync_convergence.py` | Phase 4 同步收敛验收测试 |

> ✅ 第一阶段~第三阶段文件清单均已实现（功能冻结），保留作为实现明细参考。

2026-09-09：修正 mDNS 两个浏览入口的 Zeroconf 关键字回调签名。三台独立
V11 虚拟机由发现接口报错恢复为彼此发现；`test_discovery_pairable.py` 8 项通过。
这是开发修复的联机证据，尚未重新构建正式安装包，不替代最终发布门。

同日补充：主线仲裁共用 Foundation 迟到证据物化适配，同 ID 分支延迟到 CRDT
选胜后才落库，删除操作跳过知识候选转换。迟到证据、失败分支不能覆盖本地状态、
不能复活已遗忘知识、空删除载荷四个新增回归先红后绿；Foundation 全套 698 项通过。
三台独立 V11 虚拟机复验已通过断连补齐、并发收敛和遗忘重连传播，三端墓碑摘要一致。
这是同宿主虚拟机开发验证；正式包重建及发布门仍待完成，不能替代最终设备验收。

2026-09-10：完成阶段查看/保留、聊天遗忘桌面交接、人工冲突同步接线与连续应用统计。相关 API、冲突、同步、行为测试 137 项通过；不将此结果计为多设备麒麟真机验收。

2026-09-10：新增 documents 解码、登记及分块 API，schema v14 增加私有暂存表。解码/登记/schema 39 项、API 1 项通过；后端全套 933 项通过。目录 dreaming 尚未替换现有采集入口。
