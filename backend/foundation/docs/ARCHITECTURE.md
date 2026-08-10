# 模块 C · 后台基础设施架构设计

> **角色**：基础服务设施 —— 存储、API、检索、同步、评测。
> **与模块 B 的边界**：Foundation **提供** `core/` 中的接口，**消费** 引擎 Service 并通过 `api/di.py` 注入路由。

> **状态（2026-09-09，功能冻结）**：Phase 0～Phase 7 全部完成——core/storage/api、
> retrieval、flow、sync、eval、D-Bus 均已实现；REST 全端点 + WS + D-Bus 可用；
> request_id 统一错误契约；四故事端到端与硬化测试通过，377 项全绿；
> 1000 次查询压测 P95=19.18ms。仅真实麒麟 SDK 性能 / 局域网互操作 / Module A 联调
> 待银河麒麟环境验收（详见 docs/ACCEPTANCE.md）。

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
    quality_score: float; sensitivity: int; scope: str; created_at: int

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
http_app.py  → FastAPI app + 路由（/memory/write、/memory/query、/preference/*、/forget、
               /conflicts、/memory/flow/promote、/sync/* 已实现）
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
        embedder=get_embedder(),   # 真实麒麟 SDK，无 mock
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

基础表 16 张：原有记忆/流转表加 `sync_identity`、`sync_peers`、`sync_state`、
`sync_peer_acks`、`sync_meta`；`sync_oplog` 保存签名操作，私钥仅以加密 PKCS#8 保存。
`knowledge_fts`（FTS5 trigram）与 `knowledge_vec`（INT8）由仓储首次使用时惰性创建。
WAL + foreign_keys + busy_timeout 已启用。

**Schema 概要**：

```sql
-- 证据
CREATE TABLE evidence (
  id TEXT PRIMARY KEY, source_type TEXT, raw JSON,
  quality_score REAL, sensitivity INTEGER, scope TEXT, created_at INTEGER);

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
| 语义 | `ann.py` | query embedding → INT8 ANN 近邻 | 并行 |
| 图 | `graph_search.py` | 从命中实体沿 BELONG_TO 遍历 | 并行 |
| 融合 | `fuse.py` | RRF + context_hint 加权 | ~10ms |
| 重排 | `rerank.py` | INT8 reranker 细粒度 relevance | ~150ms |
| 组装 | `assembler.py` | 结构化过滤 + 聚合计算 + evidence_ids 回溯 | ~30ms |

**当前机制**：规则路由；FTS5 trigram（含 CJK 回退）；INT8 向量线性扫描；
持久化 knowledge↔entity 与 `BELONG_TO` 一跳图召回；三通道 `asyncio.gather` 并发；
scope/time_range 硬过滤；RRF 融合；词法重排；查询类别聚合与证据组装。

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

> ✅ **Phase 3 已实现**。网络运行时默认关闭，需显式安全配置后启动。

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
├── materializer.py # CRDT 胜者物化到本地仓储
├── gc.py           # 全网 ACK 后 tombstone 回收
├── scheduler.py    # 有界退避调度
└── runtime.py      # 默认关闭的 mDNS/mTLS 生命周期
```

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


**安全与运行边界**：

- 网络默认关闭；只有 `PIXIU_SYNC_NETWORK_ENABLED=true` 且地址、证书、CA 均显式配置后启动。
- mDNS 结果必须与本地已配对、未撤销 peer 的设备 ID、`shared:*` 域和 Ed25519 公钥完全匹配。
- `user:*` 不进入 oplog；嵌套 payload scope 必须与签名 envelope scope 一致。
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
