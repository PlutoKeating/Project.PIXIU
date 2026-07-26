# Project.PIXIU 总体架构设计

> **项目代号**：PIXIU（貔貅）
> **题目**：麒麟软件《OSAgent 记忆优化及高效应用研究》
> **定位**：面向居家/办公多用户协作环境的**去中心化分布式 Agent 记忆共享系统**

---

## 1. 设计目标与约束

### 1.1 模块划分（新增）

PIXIU 后端按架构维度拆分为两个独立开发模块，物理上位于 `backend/` 下的不同目录树，通过 `foundation/core/` 中的抽象接口（ABC）解耦：

```
┌──────────────────────────────────────────────────────────┐
│  Module A: UKUI 桌面客户端 (frontend/)                     │  C++17 + Qt5 + Kysdk
│  悬浮球 · 聊天框 · 记忆面板 · 设备配对                     │
│  ★ 与后端仅通过固定 API 契约（12 端点）通信                 │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTP REST · WS · D-Bus
┌────────────────────────┴─────────────────────────────────┐
│  后端 (backend/)                                           │
│                                                           │
│  Module B: 记忆业务引擎 (engine/)                          │  Python 3.10 + C++
│  多源接入 · 偏好捕捉 · 知识结构化 · 冲突仲裁 · 安全遗忘     │
│  ★ 通过 Repository ABC 接口消费存储层                      │
│                                                           │
│  Module C: 后台基础设施 (foundation/)                      │  Python 3.10 + SQLite
│  API 网关 · 存储层 · 混合检索 · 记忆流转 · P2P 同步 · 评测  │
│  ★ 提供 core/ 契约 + 在 api/ 注入引擎 Service              │
└──────────────────────────────────────────────────────────┘
```

详细模块边界、契约定义与开发规则见 `DEVELOPMENT_PLAN.md`。

### 1.2 功能目标（映射赛题要求）

| 编号 | 赛题要求 | 负责模块 | 验收条目 |
|------|----------|----------|----------|
| (1) | 多源数据统一接入、清洗、标准化、质量校验 | B engine/ingest | F1-01~F1-07 |
| (2) | 偏好记忆动态捕捉、版本化、跨场景适配与回溯 | B engine/preference | F2-01~F2-07 |
| (3) | 知识结构化整合、冲突处理、关联检索 | B engine/{knowledge,conflict} + C foundation/retrieval | F3-01~F3-05 |
| (4) | 端侧部署、调用麒麟 embeddingSDK、检索 ≤500ms | B engine/kylin + C foundation/retrieval | F4-01~F4-04 |
| (5) | 敏感信息识别过滤、自然语言精准遗忘 | B engine/security | F5-01~F5-05 |
| (6) | 短/中期记忆数据流转兼容 | C foundation/flow | F6-01~F6-03 |
| (7) | 量化评测机制与测试报告 | C foundation/eval | F7-01~F7-05 |

### 1.3 关键约束

- **端侧轻量化**：x86/ARM 麒麟机型，内存占用低，离线可用
- **检索在线零 LLM**：仅用 embedding + 结构化字段 + 图遍历，保证 P95 ≤ 500ms
- **国产化适配**：embedding 必须经麒麟 `coreai/embedding` C 接口；桌面交互基于 UKUI/Qt5 + KylinSDK

---

## 2. 核心数据模型

```jsonc
// evidence：原始证据（可追溯源）
{ "id": "evd_...", "source_type": "OCR|TOOL_RESULT|USER_BEHAVIOR|MANUAL_CONFIG",
  "raw": {}, "quality_score": 0.94, "sensitivity": 0, "scope": "user:alice", "created_at": "..." }

// knowledge_item：结构化知识条目
{ "id": "knw_...", "kind": "FACT|WORKFLOW|CASE|TEMPLATE", "title": "...",
  "body": {}, "entities": [], "relations": [], "embedding_ref": "vec_...",
  "status": "ACTIVE|SUPERSEDED|FORGOTTEN", "version": 3,
  "evidence_ids": ["evd_..."], "scope": "user:alice|shared:home" }

// preference：偏好记忆（版本化）
{ "id": "pref_...", "category": "OP_HABIT|OUTPUT_STYLE|SECURITY_POLICY",
  "key": "...", "value": {}, "confidence": 0.9, "version": 2,
  "scope": "user:alice", "history": [/* 旧版本快照 */] }

// conflict_record：冲突审计
{ "id": "cfl_...", "target_knowledge": "knw_...", "old": {}, "new": {},
  "resolution": "NEW_WINS|MERGE|MANUAL", "created_at": "..." }
```

---

## 3. 业务逻辑实现机制

### 3.1 写入路径：把"零散信息"变成"结构化记忆"

```
事件源(工具结果/用户行为/手动配置/OCR)
  → 敏感前置（engine/security:detector）：sensitivity 评分
  → 接入处理（engine/ingest）：Connector → Cleaner → Normalizer → Quality
  → 同步落 evidence(<50ms) → 立即 ACK
  → 异步：
      engine/knowledge:structurer → 结构化（FACT/WORKFLOW/CASE/TEMPLATE）
      engine/knowledge:graph → 实体关系建图
      engine/knowledge:embed_writer → 麒麟 embedding → INT8 量化 → 写 knowledge_vec + knowledge_fts
      engine/preference:extractor → 偏好提取
      engine/conflict:arbiter → 与既有知识比对仲裁
  → foundation/sync:CRDT 广播
```

**三索引齐写**：一条知识同时进 FTS5（关键词）、向量库（语义）、图（实体关系），这是混合检索的前提。

### 3.2 在线检索路径：500ms 内给出可信答案

```
query + context_hint
  → 路由（foundation/retrieval:router, ~15ms）：意图分类 + 实体抽取 + 通道选择
  → 三通道并行（asyncio.gather）：
      BM25(FTS5)  关键词/标题命中
      ANN(向量)    query embedding → INT8 近邻
      Graph        从命中实体沿 BELONG_TO 遍历聚合
  → 融合（fuse, ~10ms）：RRF 排名融合 + context_hint 加权
  → 重排（rerank, ~150ms）：INT8 reranker 细粒度 relevance
  → 组装（assembler, ~30ms）：结构化过滤 + 聚合计算 + 附 evidence_ids
  → 返回 MemoryAtom{answer, source_evidence, confidence, latency_ms}
```

### 3.3 偏好动态捕捉与版本化（engine/preference）

- 提取三类偏好：操作习惯 / 输出风格 / 安全策略
- 版本化：每次更新写 preference_history 快照，主表 version+1
- 回溯与适配：`/preference/{id}/history` 回溯历史版本；偏好带 `scope` 与场景标签

### 3.4 冲突仲裁（engine/conflict）

- 检测：同实体同字段新旧值做矛盾判定
- 裁决：默认 NEW_WINS，旧版 SUPERSEDED（保留而非删除），可配 MERGE/MANUAL
- 审计：生成 ConflictRecord，全程留痕

### 3.5 安全识别与精准遗忘（engine/security）

- 敏感识别：写入入口前置 detector（正则 + 规则识别身份证/银行卡等），sensitivity 评分
- 自然语言遗忘：解析指令 → 构造匹配条件 → 级联清理 knowledge + evidence + 实体关系

### 3.6 记忆流转（foundation/flow）

短期（会话上下文）→ 中期（近期会话摘要）→ 长期（evidence/knowledge）三层模型；promote/demote 双向流转，TTL 衰减管理。

---

## 4. 分布式记忆共享（去中心化）

核心创新点。完整管理链路由 `foundation/sync/` 实现：

- **对等架构**：每台设备运行完整副本，AP + 最终一致
- **同步单元**：`sync_oplog` 中的 op，CRDT（LWW-Element-Set + 版本向量）合并
- **节点生命周期**：身份初始化 → 设备配对 → mDNS/Gossip 发现 → 首次全量对账 → 稳态增量推送 → 离线积累 → 重连对账 → 退出/解绑
- **双机制扩散**：Gossip 实时推送 + 反熵周期对账
- **TLS 1.3 + 设备密钥双向证书**加密
- **scope 准入**：私有 `user:*` 永不出端，仅 `shared:*` 入队
- **删除传播**：遗忘生成 tombstone op，gc 在全网确认后回收

### CRDT 与冲突仲裁的边界

| 维度 | Sync CRDT | engine/conflict |
|------|-----------|-----------------|
| 处理对象 | 同一条记忆的并发副本 | 不同记忆在语义上的矛盾 |
| 判定依据 | 版本向量 + LWW（机械、确定性） | 实体/字段级语义比对 |
| 结果 | 收敛到同一份数据 | 生成 ConflictRecord |

## 5. 存储层 Schema

详见 `backend/foundation/docs/ARCHITECTURE.md` 第 1.3 节。

核心表：`evidence`, `knowledge_items`, `knowledge_fts`（FTS5）, `knowledge_vec`（INT8）, `entities`, `relations`, `preferences`, `preference_history`, `conflict_records`, `sync_oplog`。

## 6. KylinSDK 适配总览

| 能力 | SDK | 用途 | 调用者 |
|------|-----|------|--------|
| 文本/图像向量化 | `coreai/embedding`（9.4.3） | ANN 通道、知识 embedding | engine/kylin |
| OCR | AI SDK 9.4.1 | 图片支出清单接入 | engine/ingest |
| 文本生成 | AI SDK 9.5.1 | 离线偏好/知识抽取 | engine/preference |
| 桌面通知 | `kysdk-notification`（8.2） | 记忆事件、冲突提醒 | frontend |
| 全局快捷键 | `kysdk-shortcut`（8.3） | 唤起聊天框 | frontend |
| 主题 | 8.5 Theme | 跟随 UKUI 明暗主题 | frontend |
| Qt 扩展控件 | 应用支撑 SDK 4.1.x | 聊天框 UI 组件 | frontend |

## 7. API 端点

详见 `docs/API.md`。核心端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/memory/write` | 写入记忆 |
| POST | `/memory/query` | 混合检索 |
| POST | `/forget` | 自然语言遗忘 |
| GET | `/conflicts` | 冲突审计 |
| POST | `/sync/pair` | 设备配对 |
| GET | `/sync/peers` | 节点列表 |
| GET | `/sync/status` | 同步状态 |
| POST | `/sync/peers/{id}/revoke` | 解绑设备 |
| WS | `/events` | 事件推送 |

## 8. 仓库结构

```
Project.PIXIU/
├── docs/                      # 项目根文档
├── backend/
│   ├── engine/                # Module B: 记忆业务引擎
│   ├── foundation/            # Module C: 后台基础设施
│   ├── scripts/               # 工具脚本
│   ├── tests/                 # 测试
│   └── docs/                  # 后端文档
└── frontend/                  # Module A: UKUI 桌面客户端
    └── docs/                  # 前端文档
```

详细架构见 `backend/engine/docs/ARCHITECTURE.md`、`backend/foundation/docs/ARCHITECTURE.md`、`frontend/docs/ARCHITECTURE.md`。
