# PIXIU 后端架构设计（Memory Daemon）

> **角色**：端侧常驻的记忆服务守护进程，承载 M1~M8 全部记忆能力。
> **上游**：OS Agent 主进程 / UKUI 前端（聊天框）。
> **依赖**：麒麟 `coreai/embedding` C 接口、SQLite、本机 P2P 同步。
> **总体架构见**：`docs/ARCHITECTURE.md`。

---

## 1. 技术选型

| 层面 | 选型 | 理由 |
|------|------|------|
| 服务语言 | Python 3.10（编排层） + C++（embedding shim） | 开发效率 + 端侧原生 SDK 绑定 |
| 服务框架 | FastAPI + Uvicorn（localhost）/ Unix Socket / D-Bus | 同时服务前端与 OS Agent，低开销 |
| 存储 | SQLite（WAL）+ FTS5（BM25）+ sqlite-vec/hnswlib（ANN） | 单文件、零运维、端侧轻量化（F4-03） |
| 图存储 | SQLite 邻接表（entities / relations 表）| 免额外图数据库，支持 BELONG_TO 遍历 |
| embedding | 麒麟 `coreai/embedding`（C，经 pybind11/ctypes 封装） | 强制使用麒麟 embeddingSDK（F4-02） |
| 任务队列 | 进程内 asyncio + 持久化 outbox 表 | 写入路径异步化，检索路径不阻塞 |
| 同步 | 自研 CRDT + mDNS/Gossip + TLS | 去中心化、无单点 |

> **设计原则**：检索在线路径（P2）**禁用 LLM 与网络**，仅本地 embedding + SQL + 图遍历，确保 P95 ≤ 500ms（F4-04 / SC-06）。

---

## 2. 模块划分

```
backend/
├── pixiu/
│   ├── api/                # 对外接口：HTTP/WS + D-Bus + Unix socket
│   │   ├── http_app.py     # FastAPI: /memory/write /memory/query /forget ...
│   │   ├── ws.py           # 流式检索 / 事件推送
│   │   └── dbus_service.py # com.kylin.pixiu.Memory
│   ├── m1_ingest/          # 多源数据接入 (要求1)
│   │   ├── connectors/     # tool_result / user_behavior / manual_config / ocr
│   │   ├── cleaner.py      # 去噪/去重/缺失处理
│   │   ├── normalizer.py   # 格式标准化 + 实体规范化
│   │   └── quality.py      # quality_score + Schema 校验
│   ├── m2_preference/      # 偏好动态捕捉 (要求2)
│   │   ├── extractor.py    # OP_HABIT / OUTPUT_STYLE / SECURITY_POLICY
│   │   ├── versioning.py   # 版本化 + 回溯
│   │   └── adapter.py      # 跨场景适配
│   ├── m3_knowledge/       # 知识结构化整合 (要求3)
│   │   ├── structurer.py   # FACT/WORKFLOW/CASE/TEMPLATE 结构化
│   │   ├── graph.py        # 实体-关系图构建
│   │   └── embed_writer.py # 调用 embedding 写向量
│   ├── m4_conflict/        # 冲突仲裁 (要求3)
│   │   └── arbiter.py      # 检测/裁决/ConflictRecord/审计
│   ├── m5_retrieval/       # 混合检索 (要求4 + 附录A)
│   │   ├── router.py       # 意图分类 + 实体抽取 + 通道选择
│   │   ├── bm25.py / ann.py / graph_search.py
│   │   ├── fuse.py         # RRF + context_hint 加权
│   │   ├── rerank.py       # INT8 reranker
│   │   └── assembler.py    # 结构化聚合 + evidence 回溯
│   ├── m6_flow/            # 短/中/长期记忆流转 (要求6)
│   ├── m7_security/        # 敏感识别 + 精准遗忘 (要求5)
│   │   ├── detector.py     # 身份证/银行卡等敏感识别
│   │   └── forget.py       # 自然语言遗忘 + 级联清理
│   ├── m8_eval/            # 量化评测 (要求7)
│   ├── kylin/              # KylinSDK 适配层
│   │   ├── embedding.py    # ctypes/pybind 封装 coreai/embedding
│   │   └── _shim/          # C++ 源码 (text/image embedding)
│   ├── storage/            # SQLite + 索引 + 仓储模式
│   ├── sync/               # P2P CRDT 同步
│   └── core/               # 数据模型、配置、日志、ID 生成
├── scripts/                # 建库/评测/压测脚本
└── docs/
```

---

## 3. KylinEmbedding 适配层

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

## 4. 存储 Schema（SQLite）

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

---

## 5. 对外接口（API 摘要）

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

## 6. 性能与轻量化策略

- **延迟预算（≤500ms）**：路由 15ms + 三通道并行 ≈ 90ms + 融合 10ms + INT8 重排 150ms + 组装 30ms ≈ P50 200 / P95 380ms。
- **并行检索**：BM25 / ANN / Graph 三通道用 `asyncio.gather` 并发。
- **向量 INT8 量化**：存储与算力双优化，适配端侧。
- **embedding 会话常驻 + 批处理**：写入路径批量向量化。
- **WAL + 索引**：读写分离，检索不被写入阻塞。

---

## 7. 评测框架（M8，要求7）

- **数据集**：构造 50 组家庭支出清单 + 语义查询黄金集（SC-K1），偏好/冲突用例集。
- **指标脚本**：`scripts/eval.py` 输出偏好提取准确率(P-01)、检索召回率(P-02)、P50/P95 延迟(P-03)、冲突处理正确率(P-04)、聚合正确率、证据追溯成功率。
- **目标**：准确率≥85%、召回率≥85%、延迟≤500ms、冲突正确率≥88%。

---

## 8. 与前端/OS Agent 的集成

- 前端通过 **localhost HTTP + WS**（或 D-Bus `com.kylin.pixiu.Memory`）调用；推荐 D-Bus 以贴合桌面生态。
- OS Agent 工具调用结果通过 `/memory/write`（source_type=TOOL_RESULT）流入。
- 事件（写入完成、冲突、遗忘确认）经 WS/D-Bus 信号通知前端，由前端用 `kysdk-notification` 弹窗。
