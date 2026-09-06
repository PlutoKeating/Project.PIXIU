# 模块 C · 后台基础设施架构设计

> **角色**：基础服务设施 —— 存储、API、检索、同步、评测。
> **与模块 B 的边界**：Foundation **提供** `core/` 中的接口，**消费** 引擎 Service 并通过 `api/di.py` 注入路由。
> **与模块 E 的边界**：Foundation 只提供 `docs/API.md` 中的公共 HTTP/WS 契约；
> E 不得导入 Service、Repository 或数据库实现。真实 capability/runtime 端点已实现；
> Agent 关联 ID 已进入 evidence 模型/API，schema v12 已提供持久化幂等 receipt、
> 一次性失败恢复授权和审计；
> `/agent/context` 已提供 scope/敏感过滤、预算、freshness、冲突状态与 evidence 引用；
> `/memory/write` 已先检测敏感度再占用 receipt，敏感内容不可进入 `shared:*`，检测
> 故障 fail closed；`/memory/update` 以存储层原子 compare-and-swap 更新同一 ID，追加
> evidence、重建图/向量并生成 shared 同步 op；`/agent/lifecycle` 已幂等写入六类短/中期 context；日志贯通、Module E
> 真实触发及长期化策略仍待完成。
> `/version` 分离产品/API/Agent Memory/schema 版本，`/health` 校验实际数据库迁移；
> 两者与 `/capabilities` 共同构成 Module E 的启动前握手。

> **状态（2026-08-11，功能冻结）**：Phase 0～Phase 7 全部完成——core/storage/api、
> retrieval、flow、sync、eval、D-Bus 均已实现；REST 全端点 + WS + D-Bus 可用；
> request_id 统一错误契约；四故事端到端与硬化测试通过，377 项全绿；
> 1000 次查询压测 P95=19.18ms。Module A 联调已完成；最终麒麟 SDK 性能、局域网
> 多机互操作与 Agent 生命周期仍待验收（详见 docs/ACCEPTANCE.md）。WS `/events` 路由已于
> 2026-08-20 完成真实入口注册与麒麟 V11 握手验证。

同步协议的确定性三节点回归现进一步覆盖：全互信节点创建共享事实，第三节点离线
期间产生删除墓碑，重连后通过 oplog 摘要补齐，旧创建操作在回收前后重放均不能复活
数据；墓碑只有在其余两个未撤销节点均 ACK 后才回收。该测试是单进程、三份独立
数据库的协议证据，不替代最终三台 V11 设备的网络、资源与身份取证。
`python -m backend.foundation.eval.sync_evidence` 已把全连接配对、并发收敛、离线反熵、
遗忘防复活和私有 scope 拒绝汇总为绑定 commit/产品版本的 JSON；报告固定声明
`final_device_evidence=false`，不能误作真机验收。

> [!CAUTION]
> 上述“功能冻结/全绿”只覆盖旧的记忆子系统范围。PPT 要求生产向量数据库必须
> 使用系统 Vector Engine；SQLite INT8 只能作为 portable 降级。revision 8 已取得
> 系统 Vector Engine 产品链强实证，但最终 user service、依赖和性能证据仍未闭环；
> portable/stub 延迟不能替代 V11 双 SDK 最终性能验收。

---

## 1. 子包详解

### 1.1 core/ —— 共享契约

这是 **Module B 和 Module C 共同持有**的契约包，必须最先实现并冻结。

**包含**：

```
core/
├── models.py       # Pydantic 数据模型
├── repository.py   # ABC 抽象接口
├── config.py       # 配置加载
├── logger.py       # 日志
└── idgen.py        # ID 生成器
```

**数据模型**：

```python
class Evidence(BaseModel):
    id: str; source_type: str; raw: dict
    quality_score: float; sensitivity: int
    provenance: AgentProvenance | None  # session/run/turn/tool-call/time/approval
    scope: str; created_at: int

class KnowledgeItem(BaseModel):
    id: str; kind: str; title: str; body: dict; status: str
    version: int; scope: str; evidence_ids: list[str]; updated_at: int

class Preference(BaseModel):
    id: str; category: str; key: str; value: dict
    confidence: float; version: int; scope: str; updated_at: int

class PreferenceSnapshot(BaseModel):
    version: int; value: dict; updated_at: int

class Entity(BaseModel):
    id: str; name: str; norm_name: str; type: str

class Relation(BaseModel):
    src: str; dst: str; type: str  # e.g. BELONG_TO

class ConflictRecord(BaseModel):
    id: str; target_knowledge: str; field: str
    old_value: Any; new_value: Any; resolution: str; created_at: int

class MemoryAtom(BaseModel):
    answer: str; source_evidence: list[str]
    source_knowledge: str; confidence: float; latency_ms: int

class SyncOp(BaseModel):
    op_id: str; entity: str; payload: dict; vclock: dict; ts: int
```

**Repository 接口**（详见 `DEVELOPMENT_PLAN.md` 第 3.2 节）：

```python
class EvidenceRepository(ABC): ...
class KnowledgeRepository(ABC): ...
class PreferenceRepository(ABC): ...
class EntityRepository(ABC): ...
class ConflictRepository(ABC): ...
```

### 1.2 api/ —— API 网关

**三协议支持**：

```
http_app.py  → FastAPI app + 路由（/memory/write、/memory/update、/memory/query、/preference/*、/forget、
               /agent/context、/agent/lifecycle、/conflicts、/memory/flow/promote、/sync/* 已实现）
ws.py + ws_manager.py → WebSocket /events（连接/心跳/广播，memory_ready 已接入写入链路）
dbus_service.py → com.kylin.pixiu.Memory（桌面 D-Bus）
```

**依赖注入**（`api/di.py`，已真实注入引擎 Service）：

```python
# api/di.py —— 唯一跨模块 import 点
from backend.engine.ingest import IngestionService
from backend.engine.preference import PreferenceService
from backend.engine.knowledge import KnowledgeService
from backend.engine.conflict import ConflictService
from backend.engine.security import SecurityService
from backend.engine.kylin import get_embedder
from backend.foundation.storage.repository import (
    SqliteConflictRepo, SqliteEntityRepo, SqliteEvidenceRepo,
    SqliteKnowledgeRepo, SqlitePreferenceRepo,
)

# 依赖注入：工厂函数经 FastAPI Depends 组装（get_db 惰性连接 + 迁移）
async def get_ingestion_service(db=Depends(get_db)) -> IngestionService:
    return IngestionService(evidence_repo=SqliteEvidenceRepo(db))

async def get_knowledge_service(db=Depends(get_db)) -> KnowledgeService:
    return KnowledgeService(
        knw_repo=SqliteKnowledgeRepo(db),
        entity_repo=SqliteEntityRepo(db),
        embedder=get_embedder(settings.embedding),  # auto / kylin / portable
    )

async def get_conflict_service(db=Depends(get_db)) -> ConflictService:
    return ConflictService(knw_repo=SqliteKnowledgeRepo(db), conflict_repo=SqliteConflictRepo(db))

async def get_preference_service(db=Depends(get_db)) -> PreferenceService:
    return PreferenceService(pref_repo=SqlitePreferenceRepo(db))

async def get_security_service(db=Depends(get_db)) -> SecurityService:
    return SecurityService(knw_repo=SqliteKnowledgeRepo(db), entity_repo=SqliteEntityRepo(db))
```

### 1.3 storage/ —— 存储层

**SQLite 仓储模式**，实现 `core/repository.py` 中定义的所有接口。

**Schema**（由 `storage/migrations.py` 版本化迁移创建，`storage/schema.py` 定义）：

基础表 20 张：原有记忆/流转表加 `sync_identity`、`sync_peers`、`sync_state`、
`sync_peer_acks`、`sync_meta`；`sync_oplog` 保存签名操作，私钥仅以加密 PKCS#8 保存。
`knowledge_fts`（FTS5 trigram）与 `knowledge_vec`（INT8）由仓储首次使用时惰性创建。
`vector_id_map` 持久化 PIXIU 字符串知识 ID 与系统 Vector Engine `int64` 主键的
唯一双向映射；候选冲突时加盐重试，进程/数据库重启后保持稳定。
`agent_ingest_receipts` 以请求哈希和状态机保存 Agent 写入的幂等所有权与完成响应；
完成态可安全重放，进行中/失败态保持 fail-closed。
WAL + foreign_keys + busy_timeout 已启用。

**Schema 概要**：

```sql
-- 证据
CREATE TABLE evidence (
  id TEXT PRIMARY KEY, source_type TEXT, raw JSON,
  quality_score REAL, sensitivity INTEGER, provenance JSON,
  scope TEXT, created_at INTEGER);

CREATE TABLE agent_ingest_receipts (
  idempotency_key TEXT PRIMARY KEY, request_hash TEXT, state TEXT,
  response JSON, created_at INTEGER, updated_at INTEGER);

-- 知识条目
CREATE TABLE knowledge_items (
  id TEXT PRIMARY KEY, kind TEXT, title TEXT, body JSON,
  status TEXT, version INTEGER, scope TEXT, updated_at INTEGER);
CREATE TABLE knowledge_evidence (knowledge_id TEXT, evidence_id TEXT);
CREATE TABLE knowledge_entities (knowledge_id TEXT, entity_id TEXT);

-- BM25 全文索引
CREATE VIRTUAL TABLE knowledge_fts USING fts5(title, body_text);

-- 向量（INT8）
CREATE TABLE knowledge_vec (knowledge_id TEXT, dim INTEGER, vec BLOB);

-- 实体-关系图
CREATE TABLE entities (id TEXT PRIMARY KEY, name TEXT, norm_name TEXT, type TEXT);
CREATE TABLE relations (src TEXT, dst TEXT, type TEXT);

-- 偏好
CREATE TABLE preferences (id TEXT PRIMARY KEY, category TEXT, key TEXT, value JSON,
  confidence REAL, version INTEGER, scope TEXT, updated_at INTEGER);
CREATE TABLE preference_history (pref_id TEXT, version INTEGER, snapshot JSON, ts INTEGER);

-- 冲突审计
CREATE TABLE conflict_records (id TEXT PRIMARY KEY, target_knowledge TEXT,
  old JSON, new JSON, resolution TEXT, created_at INTEGER);

-- 短/中期上下文
CREATE TABLE memory_contexts (id TEXT PRIMARY KEY, tier TEXT, payload JSON,
  scope TEXT, status TEXT, created_at INTEGER, updated_at INTEGER,
  expires_at INTEGER, knowledge_id TEXT);

-- CRDT 同步日志
CREATE TABLE sync_oplog (op_id TEXT PRIMARY KEY, entity TEXT, payload JSON,
  vclock JSON, ts INTEGER, synced INTEGER);
```

**WAL 模式**实现读写分离：写入管线持续落库时检索不被阻塞。

### 1.4 retrieval/ —— 混合检索

> ✅ **MVP 已实现**。`/memory/query` 已接入 `RetrievalService`，当前实现覆盖路由、
> 三通道召回、融合、重排、结果组装和 evidence 回溯；进入加固阶段。

**唯一在线、最敏感延迟的模块**。七步流水线：

| 步骤 | 组件 | 机制 | 预算 |
|------|------|------|------|
| 路由 | `router.py` | 意图分类 + 实体抽取 + 通道选择 | ~15ms |
| 全文 | `bm25.py` | FTS5 BM25 打分 | 并行 |
| 语义（当前降级） | `ann.py` | query embedding → SQLite INT8 扫描 | 并行；不满足 H-02 |
| 图 | `graph_search.py` | 从命中实体沿 BELONG_TO 遍历 | 并行 |
| 融合 | `fuse.py` | RRF + context_hint 加权 | ~10ms |
| 重排 | `rerank.py` | 词面重叠与业务年月匹配，无神经网络模型 | 以实测日志为准 |
| 组装 | `assembler.py` | 结构化过滤 + 聚合计算 + evidence_ids 回溯 | ~30ms |

**当前机制**：规则路由；FTS5 trigram（含 CJK 回退）；INT8 向量线性扫描；
持久化 knowledge↔entity 与 `BELONG_TO` 一跳图召回；三通道 `asyncio.gather` 并发；
scope/time_range 硬过滤；RRF 融合；词法重排；查询类别聚合与证据组装。

已新增 `core.VectorStore` seam，接口仅暴露 `upsert/search/delete` 与真实 runtime；
`storage.SqliteVectorStore` 是首个适配器，封装 INT8 量化、持久化、相似度和删除。
生产 DI 的 `KnowledgeService` 与 `ANNChannel` 已通过该 seam 完成写入和查询，
portable 适配器在内部执行 INT8 量化/扫描；组合根测试会主动禁用旧 Repository 扫描
并验证端到端检索。Kylin 适配器已可由
`PIXIU_VECTOR_STORE=auto|kylin|portable` 选择：`kylin` 对 SDK/连接错误 fail
closed，`auto` 明确告警后才降级。V11 真 SDK 证据完成前 H-02 仍为不通过。
组合根只向客户端传递安全的 `PIXIU_VECTOR_APP_ID`，生产连接使用 SDK 官方
`ConnectParam(appId)` 本地传输；不再把仅供 SDK 测试的 host/port 重载当成产品配置。
客户端连接后必须先 `LoadDBFile(PIXIU_VECTOR_DB_PATH)`；该文件默认位于 data 目录。
store 在进程内单例复用并由 lifespan 调用 `Disconnect`，strict 预检因而会真实验证
数据库装载，而不再以“仅成功构造客户端”判定可用。
`GET /capabilities` 从实际实例化的 embedding/vector store 读取 runtime，并只输出
验收相关的 OS 家族/主版本；配置意图与运行事实分栏，且不暴露主机、网络或路径信息。
平台解析同时接受发行版常见的 `11` 与 `V11`/`v11` 版本格式并统一输出 `11`。
应用 lifespan 在启动其他后台运行时前预检所有显式 `kylin` 后端，任一 SDK 无法实例化
即中止启动；`auto` 模式仍允许带明确 runtime 标识的 portable 降级。
所有启动步骤现处于同一清理边界：正常退出或 strict 预检/后台运行时启动失败时，依次
停止行为采集、监控、同步和 Vector Engine，最后幂等关闭全局 aiosqlite 连接并失效
DB 绑定服务，避免工作线程在事件循环关闭后回调。
未显式注入 seam 的旧测试/自定义构造暂保留 Repository 兼容路径，不得用于生产
或验收。

开发基线（50 条记录、1000 次查询、测试 stub embedding）为 P50=11.4ms、P95=13.3ms。
该数据仅用于回归，不代表真实麒麟 SDK 和正式验收数据下的最终性能。

**Phase 1 加固结果**：前五项代码与回归测试已完成，包括 SQLite 关闭重开后的图召回、
三通道并发、scope 隔离、结构化业务日期过滤，以及附录 A 的 434.50 聚合。
真实麒麟 embedding + 正式数据集的召回率/P95 验收无法在 Windows 环境执行，必须在安装
原生扩展与 AI 运行时的银河麒麟机器上完成。

### 1.5 flow/ —— 记忆流转

> ✅ **Phase 2 已实现**。上下文使用 `ctx_` ULID 和 `memory_contexts` 持久化，
> `/memory/flow/promote` 已复用引擎 `ingest → knowledge` 真实链路。

三层模型：

```
短期（会话上下文）
  → promote（复用引擎的 ingest→knowledge 管线）
    → 中期（近期会话摘要）
      → promote
        → 长期（evidence + knowledge）

demote：长期 → 短/中期快照（原长期知识保持 ACTIVE）
TTL：短期默认 30 分钟，中期默认 7 天；到期保留审计行、清空 payload
```

`promote` 在任何业务写入前对整批 ID、scope、来源层级和状态进行校验；重复沉淀已
`PROMOTED` 上下文时直接返回原 `knowledge_id`。成功后取消该上下文的 TTL，避免长期知识
已生成后上下文记录被清理。scope 不匹配与不存在统一按 NOT_FOUND 处理，避免跨 scope
探测。

### 1.6 sync/ —— P2P CRDT 同步

> ✅ **Phase 3 已实现**；SN-4（2026-08-29）起网络运行时默认开启
> （`PIXIU_SYNC_NETWORK_ENABLED` 缺省 true），缺 advertise/TLS 证书自动降级不阻塞 API。

**核心创新**：去中心化多设备记忆网络。

**组件**：

```
sync/
├── identity.py     # Ed25519 身份；私钥口令加密
├── discovery.py    # mDNS 广告解析 + 已配对 peer 信任目录
├── pairing.py      # 扫码/PIN、签名、公钥交换、防重放
├── transport.py    # TLS 1.3 mTLS + 1 MiB JSON 帧
├── protocol.py     # 仅接受已配对 sender 的签名 SyncOp
├── gossip.py       # 有界 fanout、持久化重传和 ACK
├── crdt.py         # LWW-Element-Set + 版本向量
├── anti_entropy.py # digest/delta 对账
├── materializer.py # CRDT 胜者物化；远端知识复用 engine 语义冲突仲裁
├── gc.py           # 全网 ACK 后 tombstone 回收
├── scheduler.py    # 有界退避调度
└── runtime.py      # 默认开启的 mDNS/mTLS 生命周期（缺配置自动降级）
```

`SyncRuntime.stop()` 会取消当前反熵调度任务并等待协程 `finally` 清理，然后关闭 mDNS
与 TLS server；停机不再等待正在进行的完整发现/对端超时窗口，保证软件升级和服务
停止有界完成。

**同步流程**：

```
本地写入 → sync_oplog 追加 op
  → gossip 推送给在线 peer（近实时）
    → 对端 crdt.merge（vclock 判定因果）
  → anti_entropy 周期兜底（防丢失）
    → 双机制保证最终一致
```

**与冲突仲裁的边界**：

| 维度 | sync/ CRDT | engine/conflict |
|------|------------|-----------------|
| 处理对象 | 同一条记忆的并发副本 | 不同记忆的语义矛盾 |
| 判定依据 | 版本向量 + LWW | 字段级语义比对新旧 |
| 结果 | 数据层收敛 | 生成 ConflictRecord |

远端首次出现的 `knowledge:*` 虽然在 CRDT 层属于快进，物化时仍会调用
`ConflictService.arbitrate(..., source="sync")`，避免绕过不同 ID 知识的语义冲突。
同步来源先按 `updated_at`、`created_at`、`id` 的全序选定胜负，因此两端以相反顺序
收到同一对矛盾知识时，最终 ACTIVE/SUPERSEDED、version、时间与正文一致。
生产 DI 同时向物化器和冲突服务注入 `KnowledgeService`：远端快进与自动仲裁结果都会
重建实体关联及 embedding/VectorStore 索引，更新替换旧向量；知识墓碑通过同一服务
隐藏条目并删除向量。不得再用直接 repository save 作为生产物化成功口径。
本地 `shared:*` 写入在冲突仲裁后也必须从 repository 重读最终持久化知识，再记录
knowledge op；否则 MERGE 会把仲裁前的新输入广播出去，导致发送端视图与 oplog 分叉。
当 knowledge 引用的 evidence 尚未到达时，物化器以 `sync_meta` 的逐引用键持久记录，
先保存无悬空外键的知识；evidence 后续到达后补写 `knowledge_evidence` 并删除待办键。
墓碑会清除该知识的待补键，防止迟到 evidence 重新挂接已遗忘条目。


**安全与运行边界**：

- 网络默认开启（`PIXIU_SYNC_NETWORK_ENABLED` 缺省 true，SN-4）；地址、证书、CA 允许
  缺省——空 advertise 自动取本机 LAN IP（回退 loopback 并告警），缺证书由 di 层降级
  （log warning，不阻塞 API）；显式 `false` 或运行时 `enabled=false` 时停止广播与监听。
- mDNS 结果必须与本地已配对、未撤销 peer 的设备 ID、`shared:*` 域和 Ed25519 公钥完全匹配。
- `user:*` 不进入 oplog；嵌套 payload scope 必须与签名 envelope scope 一致。
- `/sync/state/knowledge/{knowledge_id}` 只读暴露 present/tombstone、版本计数、时间和
  原始操作 ID 的 SHA-256，不返回 payload、scope、签名或设备 ID，供墓碑验收取证。
- 传输固定 TLS 1.3 双向认证；单帧和单批分别限制为 1 MiB、256 个操作。

### 1.7 eval/ —— 评测框架

> ✅ **已实现（Phase 4/5）**：评测引擎 `eval/eval.py`（EvalService）、指标 `eval/metrics.py`
> （Recall@1/3/5、P50/P95/P99、scope 隔离、聚合/追溯/冲突/偏好 12 项）、基准
> `eval/benchmark.py`（CRDT 收敛率/同步耗时/DB/内存/CPU）、`eval/service.py`
> （BenchmarkService，runtime=stub|kylin 双结果）、CLI `python -m backend.foundation.eval`、
> 报告 `eval/report.py`（JSON+Markdown 原子写出）。压测证据见 `evidence/`。

**指标脚本**（`scripts/eval.py`）：

| 指标 | 目标 | 数据源 |
|------|------|--------|
| 偏好提取准确率 | ≥85% | 偏好用例集 |
| 知识检索召回率 | ≥85% | 50 组支出清单+黄金查询集 |
| 检索 P95 延迟 | ≤500ms | 压测 1000 次 query |
| 冲突处理正确率 | ≥88% | 冲突用例集 |
| 聚合正确率 | 100% | 金额合计校验 |
| 证据追溯成功率 | 100% | 返回 evidence_ids 校验 |

实现：`eval/`（dataset/metrics/eval/reference/report/service/benchmark）+ CLI
`python -m backend.foundation.eval`；扩展指标 recall@1/3/5、P50/P95/P99、
scope 隔离正确率；`SyncBenchmark`（两节点 CRDT 收敛率 + 同步耗时）与
`SystemBenchmark`（DB 大小/峰值内存/CPU，零新依赖）。stub 自检：收敛率 1.0、
同步 P95 55ms。正式数据集的麒麟性能报告待目标机执行。

---

## 2. 参考文档

| 内容 | 路径 |
|------|------|
| 开发任务书 | `backend/foundation/docs/DEV_TASKS.md` |
| 最终验收清单 | `backend/foundation/docs/ACCEPTANCE.md` |
| Phase 3 同步报告 | `backend/foundation/docs/PHASE3.md` |
| 快速启动 | `backend/foundation/docs/QUICK_START.md` |
| Phase 1 加固报告 | `backend/foundation/docs/PHASE1.md` |
| Phase 2 流转报告 | `backend/foundation/docs/PHASE2.md` |
| 总体架构 | `docs/ARCHITECTURE.md` |
| 开发计划 | `docs/DEVELOPMENT_PLAN.md` |
| API 规格 | `docs/API.md` |
