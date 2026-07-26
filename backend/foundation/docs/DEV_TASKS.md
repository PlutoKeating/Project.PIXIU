# 模块 C · 后台基础设施 —— 开发任务书

> **目录**：`backend/foundation/`
> **开发人员**：1人

---

## 第一阶段：核心契约与骨架

### core/ —— 共享契约（最先实现，B 和 C 双方都依赖）

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `core/__init__.py` | ★★★ | 导出全部模型和接口 |
| `core/models.py` | ★★★ | 所有 Pydantic 数据模型（Evidence, KnowledgeItem, Preference, Entity, Relation, ConflictRecord, MemoryAtom, SyncOp...） |
| `core/repository.py` | ★★★ | 全部 Repository ABC 接口（EvidenceRepository, KnowledgeRepository, PreferenceRepository, EntityRepository, ConflictRepository） |
| `core/config.py` | ★★★ | 配置加载（环境变量：端口、数据库路径、embedding 后端类型） |
| `core/idgen.py` | ★★ | ID 生成器（带前缀：evd_, knw_, pref_, cfl_, dev_...） |
| `core/logger.py` | ★★ | 日志配置 |

### api/ —— API 网关

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `api/__init__.py` | ★★★ | 导出 `app`（FastAPI 实例） |
| `api/http_app.py` | ★★★ | FastAPI 应用 + 全部路由注册 |
| `api/ws.py` | ★★ | WebSocket `/events` 处理 |
| `api/dbus_service.py` | ★ | D-Bus `com.kylin.pixiu.Memory` |
| `api/di.py` | ★★★ | 依赖注入容器（组装引擎 Service + foundation Repository） |

### storage/ —— 存储层

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `storage/__init__.py` | ★★★ | 导出全部 Repository 类 |
| `storage/repository.py` | ★★★ | SQLite 实现全部 Repository 接口（8 个类） |
| `storage/schema.py` | ★★★ | DDL 建表语句 + 索引创建 |
| `storage/migrations.py` | ★ | 数据库迁移 |

---

## 第二阶段：检索引擎

### retrieval/ —— 混合检索

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `retrieval/__init__.py` | ★★★ | 导出 `RetrievalService` |
| `retrieval/router.py` | ★★★ | 意图分类 + 实体抽取 + 通道选择 |
| `retrieval/bm25.py` | ★★★ | FTS5 BM25 全文检索 |
| `retrieval/ann.py` | ★★★ | INT8 ANN 语义检索（sqlite-vec/hnswlib） |
| `retrieval/graph_search.py` | ★★★ | 实体关系图遍历（BELONG_TO 沿边聚合） |
| `retrieval/fuse.py` | ★★★ | RRF 融合 + context_hint 加权 |
| `retrieval/rerank.py` | ★★ | INT8 reranker 细粒度重排 |
| `retrieval/assembler.py` | ★★★ | 结构化过滤 + 聚合计算 + evidence 回溯 |

---

## 第三阶段：同步与流转

### flow/ —— 记忆流转

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `flow/__init__.py` | ★★ | 导出 `FlowService` |
| `flow/promoter.py` | ★★ | promote/demote 逻辑 |
| `flow/ttl.py` | ★ | TTL 衰减策略 |

### sync/ —— P2P 同步

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `sync/__init__.py` | ★★ | 导出 `SyncService` |
| `sync/identity.py` | ★★ | 节点身份 + Ed25519 密钥对生成 |
| `sync/discovery.py` | ★ | mDNS/Gossip 节点发现 |
| `sync/pairing.py` | ★★ | 设备配对（扫码/PIN + 公钥交换） |
| `sync/transport.py` | ★ | TLS 1.3 双向加密传输 |
| `sync/crdt.py` | ★★★ | LWW-Element-Set + 版本向量合并 |
| `sync/anti_entropy.py` | ★★ | 反熵对账（digest 比对 + 补齐缺失） |
| `sync/gc.py` | ★ | tombstone 回收 |
| `sync/scheduler.py` | ★ | 同步轮次调度 + 退避 |

### eval/ —— 评测框架

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `eval/__init__.py` | ★★ | 导出 `EvalService` |
| `eval/eval.py` | ★★ | 评测引擎（加载数据集→跑指标→输出报告） |

---

## 测试

| 文件 | 说明 |
|------|------|
| `tests/test_api.py` | 各 REST 端点的请求/响应测试 |
| `tests/test_storage.py` | SQLite 仓储实现测试 |
| `tests/test_retrieval.py` | 三通道 + 融合 + 重排 + 组装测试 |
| `tests/test_sync.py` | CRDT 合并 + Gossip 扩散测试（mock transport）|
| `tests/test_flow.py` | promote/demote + TTL 测试 |
| `tests/test_eval.py` | 评测框架正确性测试 |
