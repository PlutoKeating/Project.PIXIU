# PIXIU 后端架构设计（Memory Daemon）

> **角色**：端侧常驻的记忆服务守护进程，承载 M1~M8 全部记忆能力。
> **上游**：OS Agent 主进程 / UKUI 前端（聊天框）。
> **依赖**：麒麟 `coreai/embedding` C 接口、SQLite、本机 P2P 同步。
> **总体架构见**：`docs/ARCHITECTURE.md`；通俗介绍见同目录 `README.md`。
>
> 本文目标：完整阐述后端**分为哪些模块**、**模块间如何协作完成全部典型用例**、以及**每个业务模块的内部架构与实现机制**。

---

## 1. 设计哲学与全局约束

后端是一个"写入重、检索轻"的系统，所有设计都围绕三条主线展开：

- **写入路径可以慢，但要稳、要可追溯。** 接入、清洗、抽取、向量化、建图都在异步管线里完成，允许耗时，但每条记忆都必须能回溯到原始证据。
- **检索路径必须快，硬指标 P95 ≤ 500ms。** 在线检索**禁用 LLM 与任何网络调用**，只用本地 embedding 推理 + SQL + 图遍历（SC-06 / F4-04）。
- **数据默认不出端，共享必须可控。** 所有记忆先落本地；跨设备同步通过 CRDT 对等合并，敏感数据默认不参与同步。

### 1.1 技术选型

| 层面 | 选型 | 理由 |
|------|------|------|
| 服务语言 | Python 3.10（编排层） + C++（embedding shim） | 开发效率 + 端侧原生 SDK 绑定 |
| 服务框架 | FastAPI + Uvicorn（localhost）/ Unix Socket / D-Bus | 同时服务前端与 OS Agent，低开销 |
| 存储 | SQLite（WAL）+ FTS5（BM25）+ sqlite-vec/hnswlib（ANN） | 单文件、零运维、端侧轻量化（F4-03） |
| 图存储 | SQLite 邻接表（entities / relations 表）| 免额外图数据库，支持 BELONG_TO 遍历 |
| embedding | 麒麟 `coreai/embedding`（C，经 pybind11/ctypes 封装） | 强制使用麒麟 embeddingSDK（F4-02） |
| 任务队列 | 进程内 asyncio + 持久化 outbox 表 | 写入路径异步化，检索路径不阻塞 |
| 同步 | 自研 CRDT + mDNS/Gossip + TLS | 去中心化、无单点 |

---

## 2. 模块全景

后端由 **8 个业务模块（M1~M8）** + **3 个支撑层（KylinSDK 适配 / 存储 / 同步）** + **1 个接入层（API）** 组成。

```
                         ┌──────────────────────────────────────────┐
   OS Agent / 前端  ───▶ │  API 接入层  HTTP · WS · D-Bus · Unixsock  │
                         └───────────────┬────────────────────────────┘
                                         │
   ┌─────────────────────── 写入管线（异步，可慢）───────────────────────┐
   │                                     │                                │
   │   ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐                  │
   │   │M1 接入 │──▶│M2 偏好 │   │M3 知识 │──▶│M4 冲突 │                  │
   │   │清洗标准化│   │偏好捕捉│   │结构化建图│   │仲裁审计│                  │
   │   └───┬────┘   └───┬────┘   └───┬────┘   └────────┘                  │
   │       │            │            │  （M7 敏感识别贯穿写入入口）         │
   └───────┼────────────┼────────────┼───────────────────────────────────┘
           ▼            ▼            ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │  存储层  evidence · knowledge_items · preferences · 向量 · 图 · 审计 │
   └──────────────────────────────────────────────────────────────────┘
           ▲            ▲            ▲
   ┌───────┼────────────┼────────────┼─── 检索管线（在线，≤500ms）────────┐
   │   ┌────────┐                                                         │
   │   │M5 检索 │  路由 → BM25 ∥ ANN ∥ Graph → 融合 → 重排 → 组装          │
   │   └────────┘                                                         │
   └──────────────────────────────────────────────────────────────────┘

   横切：M6 记忆流转（短/中/长期）· M7 安全与遗忘 · M8 评测
   底座：KylinEmbedding 适配层 · 存储仓储 · P2P CRDT 同步
```

| 模块 | 职责 | 赛题要求 | 所在路径 |
|------|------|----------|----------|
| **API** | 统一接入，协议适配，事件推送 | — | `pixiu/api/` |
| **M1 接入** | 多源接入、清洗、标准化、质量/敏感度评分 | (1) | `pixiu/m1_ingest/` |
| **M2 偏好** | 偏好提取、版本化、跨场景适配与回溯 | (2) | `pixiu/m2_preference/` |
| **M3 知识** | 结构化整合、实体关系图、向量写入 | (3) | `pixiu/m3_knowledge/` |
| **M4 冲突** | 新旧矛盾检测、裁决、审计 | (3) | `pixiu/m4_conflict/` |
| **M5 检索** | 混合检索全链路 | (4)+附录A | `pixiu/m5_retrieval/` |
| **M6 流转** | 短/中/长期记忆双向流转 | (6) | `pixiu/m6_flow/` |
| **M7 安全** | 敏感识别过滤、自然语言遗忘 | (5) | `pixiu/m7_security/` |
| **M8 评测** | 量化评测与报告 | (7) | `pixiu/m8_eval/` |
| **KylinSDK 适配** | embedding / OCR / 文本生成封装 | (4) | `pixiu/kylin/` |
| **存储层** | SQLite + 三索引 + 仓储模式 | (4) | `pixiu/storage/` |
| **同步层** | CRDT + Gossip + TLS | 创新点 | `pixiu/sync/` |

完整目录树见 `README.md` 的「目录结构」一节。

---

## 3. 模块如何协作：典型用例全链路

下面用四个**典型用例**说明模块之间如何串起来工作。它们覆盖了赛题全部核心功能与附录 A 场景。

### 3.1 用例 A：写入一条记忆（OCR 支出清单，对应附录 A 步骤 1）

```
前端/Agent ──POST /memory/write {source_type:OCR, raw}──▶ API
   │
   ▼
[M7.detector] 敏感度预检（身份证/银行卡等）→ sensitivity 标记
   │
   ▼
[M1.cleaner]    去噪 / 去重 / 缺失补齐
[M1.normalizer] 格式标准化 + 实体规范化（"国家电网"→标准名）
[M1.quality]    Schema 校验 + quality_score
   │
   ├──同步落 evidence 表（<50ms）──▶ 立即向前端 ACK
   │
   ▼ （投递 outbox，异步触发）
[M3.structurer] 结构化为 KnowledgeItem(kind=FACT)
[M3.graph]      抽取实体→建 BELONG_TO 关系（国家电网→水电燃气）
[M3.embed_writer] 调 KylinEmbedding 生成 INT8 向量 → 写 knowledge_vec / knowledge_fts
   │
   ▼
[M4.arbiter] 与既有知识比对，无冲突 → status=ACTIVE
[M2.extractor] 若样本含偏好信号，旁路触发偏好提取
   │
   ▼
[sync] 写入 sync_oplog → Gossip 广播给其他设备
[API/WS] 推送 "记忆已沉淀" 事件 → 前端通知
```

**关键点**：`evidence` 同步落库后立即 ACK，重处理全部异步，写入不阻塞用户。

### 3.2 用例 B：模糊语义检索（对应附录 A 步骤 2）

```
前端 ──POST /memory/query {text, context_hint, k}──▶ API ──▶ M5
   │
   ▼
[M5.router] 15ms   意图分类(FACT_RETRIEVAL) + 实体抽取(水电燃气) + 通道选择
   │
   ├──────────────┬──────────────┐   （asyncio.gather 并行）
   ▼              ▼              ▼
[bm25] FTS5    [ann] INT8向量  [graph] BELONG_TO 遍历
 标题命中       语义近邻        找到 3 个子实体
   │              │              │
   └──────────────┴──────────────┘
   ▼
[M5.fuse] 10ms   RRF 融合 + context_hint(time_range) 加权
   ▼
[M5.rerank] 150ms  INT8 reranker 细粒度打分
   ▼
[M5.assembler] 30ms  过滤 category==水电燃气 子项 → 聚合金额 → 附 evidence_ids
   ▼
返回 MemoryAtom{answer, source_evidence, source_knowledge, confidence, latency_ms}
```

**关键点**：全程不调用 LLM、不发网络请求；三通道并行 + INT8 量化是达成 500ms 的核心手段。

### 3.3 用例 C：冲突修正（"燃气费不是 156，是 186"）

```
前端 ──/memory/write {修正语句}──▶ M1 → M3 结构化为候选新知识
   ▼
[M4.arbiter] 检测到与 knw_xxx 的字段级直接矛盾（同实体同字段不同值）
   ▼
生成 ConflictRecord{old, new, resolution:NEW_WINS}
旧版本 status=SUPERSEDED，新版本 version+1 且 ACTIVE
   ▼
[sync] 以版本向量合并广播；[WS] 推送冲突提醒事件 → 前端审计视图可见
```

### 3.4 用例 D：自然语言精准遗忘（"忘记那张 4 月支出清单"）

```
前端 ──POST /forget {nl_command}──▶ M7
   ▼
[M7.forget] 解析意图 → 构造匹配条件(title~"4月" AND source_type=OCR)
   ▼
定位目标 knowledge_item + 其 evidence + 关联 entities/relations
   ▼
前端 ForgetDialog 二次确认 ──▶ 执行级联删除（标记 FORGOTTEN + 物理清理）
   ▼
[sync] 生成 tombstone 同步删除；[WS] 推送遗忘确认事件
```

---

## 4. 各业务模块内部架构与实现机制

### 4.1 API 接入层（`pixiu/api/`）

- **`http_app.py`**：FastAPI 应用，暴露 `/memory/write`、`/memory/query`、`/forget` 等 REST 端点；请求体经 Pydantic 校验后分发给对应模块服务。
- **`ws.py`**：WebSocket `/events`，向前端推送写入完成、冲突、遗忘确认、同步状态等事件；同时支持流式检索结果。
- **`dbus_service.py`**：注册 `com.kylin.pixiu.Memory`，贴合桌面生态，随会话总线生命周期管理。
- **设计机制**：三种协议（HTTP/WS/D-Bus/Unix socket）共享同一组**服务对象（Service）**，协议层只做编解码与鉴权，不含业务逻辑，保证一处实现多协议复用。

### 4.2 M1 多源数据接入（`pixiu/m1_ingest/`）—— 要求(1)

| 子组件 | 职责 | 实现机制 |
|--------|------|----------|
| `connectors/` | 四类来源适配：`tool_result` / `user_behavior` / `manual_config` / `ocr` | 每类一个 Connector，把异构输入转成统一 `RawRecord`；统一入口满足 F1-04 |
| `cleaner.py` | 去噪、去重、缺失处理 | 规则 + 指纹去重（内容 hash）；缺失字段按 Schema 默认值或丢弃（F1-05）|
| `normalizer.py` | 格式标准化 + 实体规范化 | 字段映射到统一结构；实体经别名词典/规则归一（"国家电网"统一名）（F1-06）|
| `quality.py` | 质量评分 + Schema 校验 | `quality_score`（含 OCR 置信度、字段完整度），低于阈值标记待审（F1-07）|

**内部流水线**：`Connector → Cleaner → Normalizer → Quality → 落 evidence`。每一步是可插拔的处理器，按管线顺序执行，便于扩展新来源与新规则。

### 4.3 M2 偏好动态捕捉（`pixiu/m2_preference/`）—— 要求(2)

| 子组件 | 职责 | 实现机制 |
|--------|------|----------|
| `extractor.py` | 提取三类偏好：`OP_HABIT`（操作习惯）/ `OUTPUT_STYLE`（输出风格）/ `SECURITY_POLICY`（安全策略） | 基于多源融合证据，规则信号 + 离线文本生成（9.5.1）抽取键值对（F2-01~04）|
| `versioning.py` | 版本化管理与回溯 | 每次更新写 `preference_history` 快照，主表 `version+1`；`/preference/{id}/history` 回溯（F2-05/07）|
| `adapter.py` | 跨场景适配 | 偏好带 `scope`（user/shared）与场景标签，调用时按当前上下文解析生效版本（F2-06）|

**机制要点**：偏好提取走**写入路径（可用 LLM/文本生成）**，与检索路径解耦；置信度低于阈值的偏好标记为候选，避免污染。

### 4.4 M3 知识结构化整合（`pixiu/m3_knowledge/`）—— 要求(3)

| 子组件 | 职责 | 实现机制 |
|--------|------|----------|
| `structurer.py` | 整理为四类知识：`FACT`/`WORKFLOW`/`CASE`/`TEMPLATE` | 按 kind 套用结构化 Schema，body 存 JSON；满足 F3-03/04/05 |
| `graph.py` | 实体-关系图构建 | 抽取实体写 `entities`，关系写 `relations`（如 `BELONG_TO`），支撑关联检索（F3-02）|
| `embed_writer.py` | 向量写入 | 调 KylinEmbedding 生成向量 → INT8 量化 → 写 `knowledge_vec`；同步写 `knowledge_fts` 全文索引 |

**机制要点**：一条知识同时落**三套索引**（FTS5 / 向量 / 图），这是后续三通道混合检索的基础；写入用批处理摊薄 embedding 开销。

### 4.5 M4 冲突仲裁（`pixiu/m4_conflict/`）—— 要求(3)

- **`arbiter.py`** 的检测机制：对同实体、同字段的新旧值做**矛盾判定**（数值/枚举直接比较，文本经语义相似度判断是否表达相反）。
- **裁决策略**：默认 `NEW_WINS`（以新为准），可配置 `MERGE` / `MANUAL`；旧版本置 `SUPERSEDED` 而非删除，保证可回溯。
- **审计**：每次裁决生成 `ConflictRecord{old,new,resolution}`，经 `/conflicts` 供前端审计视图查看（F3-01，目标正确率 ≥88%）。

### 4.6 M5 混合检索（`pixiu/m5_retrieval/`）—— 要求(4) + 附录 A

这是**唯一在线、对延迟最敏感**的模块，内部是一条七步流水线：

| 步骤 | 组件 | 机制 | 预算 |
|------|------|------|------|
| 路由 | `router.py` | 意图分类 + 实体抽取 + 通道选择 | ~15ms |
| 全文 | `bm25.py` | FTS5 BM25 打分（标题/正文）| 并行 |
| 语义 | `ann.py` | query embedding → INT8 ANN 近邻 | 并行 |
| 图 | `graph_search.py` | 从命中实体沿 `BELONG_TO` 遍历聚合 | 并行 |
| 融合 | `fuse.py` | RRF（Reciprocal Rank Fusion）+ `context_hint` 加权 | ~10ms |
| 重排 | `rerank.py` | INT8 reranker 细粒度 relevance | ~150ms |
| 组装 | `assembler.py` | 结构化字段过滤 + 聚合计算 + `evidence_ids` 回溯 | ~30ms |

**机制要点**：三通道用 `asyncio.gather` 并行；`assembler` 负责把"找到的知识"转成"算好的答案"（如按 category 过滤再求和），并保证 `source_evidence` 可追溯（SC-05）。

### 4.7 M6 记忆流转（`pixiu/m6_flow/`）—— 要求(6)

- **三层模型**：短期（会话上下文）→ 中期（近期会话摘要）→ 长期（本系统 evidence/knowledge）。
- **接口**：`promote`（短/中 → 长期沉淀）与 `demote`（长期 → 召回到上下文）双向流转；`/memory/flow/promote` 暴露。
- **机制**：TTL 衰减策略管理短/中期生命周期；promote 时复用 M1→M3 写入管线，保证沉淀的内容同样结构化、可检索（F6-01~03 / D-05）。

### 4.8 M7 安全与遗忘（`pixiu/m7_security/`）—— 要求(5)

| 子组件 | 职责 | 实现机制 |
|--------|------|----------|
| `detector.py` | 敏感信息识别与过滤 | 正则 + 规则识别身份证/银行卡/手机号等，打 `sensitivity` 分；高敏内容过滤或脱敏、默认不出端（F5-01/02/05）|
| `forget.py` | 自然语言精准遗忘 | 解析指令意图 → 构造匹配条件 → 定位目标 → 级联清理 knowledge + evidence + 实体关系（F5-03/04）|

**机制要点**：`detector` 挂在**写入入口**前置执行（见用例 A）；`forget` 的级联删除生成 tombstone，确保多设备同步删除且不误删他人记忆。

### 4.9 M8 评测框架（`pixiu/m8_eval/`）—— 要求(7)

- **数据集**：50 组家庭支出清单 + 语义查询黄金集（SC-K1），偏好/冲突用例集。
- **指标脚本**：`scripts/eval.py` 输出偏好提取准确率(P-01)、检索召回率(P-02)、P50/P95 延迟(P-03)、冲突处理正确率(P-04)、聚合正确率(SC-K3)、证据追溯成功率(SC-K4)。
- **目标**：准确率≥85%、召回率≥85%、延迟≤500ms、冲突正确率≥88%。

---

## 5. KylinEmbedding 适配层（`pixiu/kylin/`）

封装麒麟 C 接口（`coreai/embedding/embedding.h`），向上提供 Python API：

```python
# pixiu/kylin/embedding.py
class KylinTextEmbedding:
    def __init__(self):
        # text_embedding_create_session + text_embedding_init_session
        ...
    def embed(self, text: str) -> list[float]:
        # text_embedding(session, text, &result)
        # embedding_result_get_vector_data / _length
        # embedding_result_destroy
        ...
    def model_info(self) -> str: ...
    def close(self):
        # text_embedding_destroy_session
        ...
```

要点：
- 会话**复用**（创建一次、常驻），避免每次检索重建模型，降低延迟。
- INT8 量化存储：原始 float 向量量化为 INT8 落库，减小存储与加速距离计算（F4-03）。
- 图像支出清单（附录 A）走 OCR(9.4.1) → 文本接入；如需图文检索可用 `image_embedding_*`。
- 提供 `MockEmbedding` 后端，在非麒麟开发机上跑通流程与单测；运行时通过配置切换真实 SDK。

---

## 6. 存储层与数据模型（`pixiu/storage/`）

采用**仓储模式（Repository）**封装 SQLite 读写，业务模块只面向仓储接口，不直接写 SQL。Schema：

```sql
-- 证据（可追溯源）
CREATE TABLE evidence (
  id TEXT PRIMARY KEY, source_type TEXT, raw JSON,
  quality_score REAL, sensitivity INTEGER, scope TEXT, created_at INTEGER);

-- 知识条目
CREATE TABLE knowledge_items (
  id TEXT PRIMARY KEY, kind TEXT, title TEXT, body JSON,
  status TEXT, version INTEGER, scope TEXT, updated_at INTEGER);
CREATE TABLE knowledge_evidence (knowledge_id TEXT, evidence_id TEXT);

-- BM25 全文索引
CREATE VIRTUAL TABLE knowledge_fts USING fts5(title, body_text, content='');

-- 向量（INT8）—— 由 sqlite-vec / hnswlib 索引
CREATE TABLE knowledge_vec (knowledge_id TEXT, dim INTEGER, vec BLOB);

-- 实体-关系图
CREATE TABLE entities (id TEXT PRIMARY KEY, name TEXT, norm_name TEXT, type TEXT);
CREATE TABLE relations (src TEXT, dst TEXT, type TEXT);  -- 如 BELONG_TO

-- 偏好（版本化）
CREATE TABLE preferences (
  id TEXT PRIMARY KEY, category TEXT, key TEXT, value JSON,
  confidence REAL, version INTEGER, scope TEXT, updated_at INTEGER);
CREATE TABLE preference_history (pref_id TEXT, version INTEGER, snapshot JSON, ts INTEGER);

-- 冲突审计
CREATE TABLE conflict_records (id TEXT PRIMARY KEY, target_knowledge TEXT,
  old JSON, new JSON, resolution TEXT, created_at INTEGER);

-- 记忆流转 outbox / CRDT 同步日志
CREATE TABLE sync_oplog (op_id TEXT PRIMARY KEY, entity TEXT, payload JSON,
  vclock JSON, ts INTEGER, synced INTEGER);
```

> **WAL 模式**实现读写分离：写入管线持续落库时，检索读取不被阻塞，保障延迟稳定。

---

## 7. 分布式同步层（`pixiu/sync/`）

- **节点对等**：每台麒麟设备一个 Memory Daemon，本地完整存储，无中心服务器。
- **同步单元**：`knowledge_item` / `preference` 以 **CRDT（LWW-Element-Set + 版本向量）** 合并，天然解决并发冲突。
- **发现与传输**：局域网 mDNS/Gossip 发现节点，TLS + 设备密钥加密通道。
- **共享域**：`scope` 字段控制可见性（私有 `user:*` vs 共享 `shared:home`），高敏数据默认不出端。
- **删除传播**：遗忘操作生成 tombstone，经 oplog 同步，保证多设备一致删除。

---

## 8. 对外接口（API 摘要）

| 方法 | 路径 | 模块 | 说明 |
|------|------|------|------|
| POST | `/memory/write` | M1 | 多源数据接入（统一入口，F1-04）|
| POST | `/memory/query` | M5 | 混合检索，返回 MemoryAtom + evidence |
| POST | `/preference/extract` | M2 | 触发偏好提取 |
| GET | `/preference/{id}/history` | M2 | 偏好回溯（F2-07）|
| POST | `/forget` | M7 | 自然语言遗忘指令（F5-03）|
| GET | `/conflicts` | M4 | 冲突记录审计 |
| POST | `/memory/flow/promote` | M6 | 短/中期 → 长期流转 |
| WS | `/events` | all | 事件推送（供前端通知）|

检索响应体（对应附录 A）：

```jsonc
{ "answer": "2026年4月，你们在水电燃气方面共支出 434.50 元……",
  "source_evidence": ["evd_..."], "source_knowledge": "knw_...",
  "confidence": 0.93, "latency_ms": 210 }
```

---

## 9. 性能与轻量化策略

- **延迟预算（≤500ms）**：路由 15ms + 三通道并行 ≈ 90ms + 融合 10ms + INT8 重排 150ms + 组装 30ms ≈ P50 200 / P95 380ms。
- **并行检索**：BM25 / ANN / Graph 三通道用 `asyncio.gather` 并发。
- **向量 INT8 量化**：存储与算力双优化，适配端侧。
- **embedding 会话常驻 + 批处理**：写入路径批量向量化。
- **WAL + 索引**：读写分离，检索不被写入阻塞。

---

## 10. 与前端 / OS Agent 的集成

- 前端通过 **localhost HTTP + WS**（或 D-Bus `com.kylin.pixiu.Memory`）调用；推荐 D-Bus 以贴合桌面生态。
- OS Agent 工具调用结果通过 `/memory/write`（source_type=TOOL_RESULT）流入。
- 事件（写入完成、冲突、遗忘确认）经 WS/D-Bus 信号通知前端，由前端用 `kysdk-notification` 弹窗。
