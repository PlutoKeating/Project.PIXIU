# Project.PIXIU 总体架构设计

> **项目代号**：PIXIU（貔貅）—— 寓意"聚财守忆"的记忆体系。
> **题目**：麒麟软件《OSAgent 记忆优化及高效应用研究》
> **定位**：面向居家/办公多用户协作环境的 **去中心化分布式 Agent 记忆共享系统**，依托麒麟桌面操作系统 OS Agent 基础架构与 KylinSDK 构建。
> **依据文件**：`README.md`、`docs/OriginProblemDescription.md`、`docs/AcceptanceTestSpecification.md`、`docs/kylin_sdk_docs/`。

---

## 1. 设计目标与约束

### 1.1 功能目标（映射赛题要求 (1)~(7)）

| 编号 | 赛题要求 | 系统模块 | 验收条目 |
|------|----------|----------|----------|
| (1) | 多源数据统一接入、清洗、标准化、质量校验 | M1 数据接入层 | F1-01~F1-07 |
| (2) | 偏好记忆动态捕捉、版本化、跨场景适配与回溯 | M2 偏好引擎 | F2-01~F2-07 |
| (3) | 知识结构化整合、冲突处理、关联检索 | M3 知识引擎 / M4 冲突仲裁 | F3-01~F3-05 |
| (4) | 端侧部署、调用麒麟 embeddingSDK、检索 ≤500ms | M5 检索引擎 + KylinEmbedding 适配层 | F4-01~F4-04 |
| (5) | 敏感信息识别过滤、自然语言精准遗忘 | M7 安全与遗忘 | F5-01~F5-05 |
| (6) | 短/中期记忆数据流转兼容 | M6 记忆流转总线 | F6-01~F6-03 |
| (7) | 量化评测机制与测试报告 | M8 评测框架 | F7-01~F7-05 |

### 1.2 创新点（去中心化分布式记忆共享，源自 README）

- **无中心节点的分布式记忆网络**：多设备间通过 P2P + CRDT 同步知识与偏好，无单点依赖。
- **多用户协作的偏好隔离与共享**：支持家庭/办公场景下的 per-user 偏好命名空间与可控的共享记忆域。
- **神经-符号混合检索**：BM25 + ANN(向量) + Graph(实体关系) 三通道融合（对应附录 A）。

### 1.3 关键约束

- **端侧轻量化**：x86 / ARM 麒麟机型，内存占用低，离线可用。
- **检索在线零 LLM**：检索路径仅用 embedding + 结构化字段 + 图遍历，保证 P95 ≤ 500ms。
- **国产化适配**：embedding 必须经麒麟 `coreai/embedding` C 接口；桌面交互必须基于 UKUI / Qt5 + KylinSDK。

---

## 2. 系统总体分层

```
┌──────────────────────────────────────────────────────────────────┐
│  前端层 (UKUI Desktop)  —— frontend/                                │
│  Qt5/C++ 桌面悬浮组件 + 聊天框                                       │
│  kysdk: 通知 / 全局快捷键 / 主题 / Qt 扩展控件                        │
└───────────────▲──────────────────────────────────────────────────┘
                │  本地 IPC (D-Bus / Unix Socket / localhost HTTP+WS)
┌───────────────┴──────────────────────────────────────────────────┐
│  记忆服务层 (Memory Daemon)  —— backend/                            │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐│
│  │M1 接入 │ │M2 偏好 │ │M3 知识 │ │M4 冲突 │ │M5 检索 │ │M7 安全 ││
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘│
│  ┌──────────────── M6 记忆流转总线 (短/中/长期) ─────────────────┐ │
│  ┌──────────────── M8 评测框架 (离线) ───────────────────────────┐ │
│  ┌──── KylinEmbedding 适配层 (C++ shim -> coreai/embedding) ─────┐ │
└───────────────▲──────────────────────────────────────────────────┘
                │
┌───────────────┴──────────────────────────────────────────────────┐
│  存储层 (轻量化端侧)                                                 │
│  SQLite (evidence / knowledge_items / preferences / versions)      │
│  FTS5 (BM25 全文)  +  向量索引 (HNSW/INT8)  +  graph 表 (实体关系)   │
└───────────────▲──────────────────────────────────────────────────┘
                │
┌───────────────┴──────────────────────────────────────────────────┐
│  分布式同步层 (P2P)  —— 无中心节点                                   │
│  CRDT 状态合并 + Gossip 发现 + 设备身份/加密通道                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心数据模型

统一记忆原子（与附录 A 对齐）：

```jsonc
// evidence：原始证据（可追溯源）
{ "id": "evd_...", "source_type": "OCR|TOOL_RESULT|USER_BEHAVIOR|MANUAL_CONFIG",
  "raw": {}, "quality_score": 0.94, "sensitivity": 0, "created_at": "..." }

// knowledge_item：结构化知识条目
{ "id": "knw_...", "kind": "FACT|WORKFLOW|CASE|TEMPLATE", "title": "...",
  "body": {}, "entities": [], "relations": [],
  "embedding_ref": "vec_...", "status": "ACTIVE|SUPERSEDED|FORGOTTEN",
  "version": 3, "evidence_ids": ["evd_..."], "scope": "user:alice|shared:home" }

// preference：偏好记忆（版本化）
{ "id": "pref_...", "category": "OP_HABIT|OUTPUT_STYLE|SECURITY_POLICY",
  "key": "...", "value": {}, "confidence": 0.9, "version": 2,
  "scope": "user:alice", "history": [/* 旧版本快照 */] }

// conflict_record：冲突审计
{ "id": "cfl_...", "target_knowledge": "knw_...", "old": {}, "new": {},
  "resolution": "NEW_WINS|MERGE|MANUAL", "created_at": "..." }
```

---

## 4. 业务逻辑实现机制（核心）

本节回答"**系统的每项功能到底是怎么实现的**"。所有业务逻辑由后端 8 个模块（M1~M8）承载，可归纳为**两条主路径 + 四个横切机制**。

### 4.1 写入路径机制：把"零散信息"变成"结构化记忆"

写入是"重处理、可异步"的。核心机制：**同步落证据、异步重处理、可追溯到底**。

```
事件源(工具结果/用户行为/手动配置/OCR)
  │
  ▼  ① 敏感前置（M7.detector）：身份证/银行卡等正则识别 → sensitivity 评分
  ▼  ② 接入处理（M1）：Connector 归一 → Cleaner 去噪去重补缺 → Normalizer 标准化+实体规范化 → Quality 打分+Schema 校验
  ▼  ③ 同步落 evidence(<50ms) → 立即 ACK（不阻塞用户）
  ▼  ④ 投递 outbox，异步触发：
        M3.structurer  结构化为 FACT/WORKFLOW/CASE/TEMPLATE
        M3.graph       抽取实体 + 建 BELONG_TO 等关系（写 entities/relations）
        M3.embed_writer 麒麟 embedding 生成向量 → INT8 量化 → 写 knowledge_vec + knowledge_fts
        M2.extractor   若含偏好信号 → 提取 OP_HABIT/OUTPUT_STYLE/SECURITY_POLICY
        M4.arbiter     与既有知识比对，无冲突 → status=ACTIVE
  ▼  ⑤ 写 sync_oplog → Gossip 广播；WS 推送"记忆已沉淀"事件
```

**实现要点**：
- **三索引齐写**：一条知识同时进 FTS5（关键词）、向量库（语义）、图（实体关系），这是混合检索的前提。
- **质量门控**：`quality_score` 低于阈值的数据标记待审，不直接污染长期记忆（F1-07）。
- **证据锚定**：每条 knowledge 通过 `knowledge_evidence` 关联其 evidence，保证任何答案都能回溯原始来源。

### 4.2 在线检索路径机制：500ms 内给出可信答案

检索是"轻计算、强实时"的，**禁用 LLM 与网络**，靠神经-符号混合三通道（对应附录 A 步骤 2）：

```
query + context_hint
  │
  ▼ ① 路由(M5.router,~15ms)：意图分类(FACT_RETRIEVAL…) + 实体抽取 + 通道选择
  ▼ ② 三通道并行(asyncio.gather)：
        BM25(FTS5)   关键词/标题命中
        ANN(向量)    query embedding → INT8 近邻，捕获"水电煤""utilities"语义等价
        Graph        从命中实体沿 BELONG_TO 遍历，聚合同类目子实体
  ▼ ③ 融合(M5.fuse,~10ms)：RRF 排名融合 + context_hint(time_range 等)加权
  ▼ ④ 重排(M5.rerank,~150ms)：INT8 reranker 细粒度 relevance
  ▼ ⑤ 组装(M5.assembler,~30ms)：结构化字段过滤 + 聚合计算(如按 category 求和) + 附 evidence_ids
  ▼ 返回 MemoryAtom{answer, source_evidence, confidence, latency_ms}
```

**实现要点**：
- **神经-符号混合**：ANN 解决"模糊语义"，结构化字段 + 图遍历解决"精确过滤与聚合"，二者互补（附录 A.5）。
- **延迟预算**：P50≈200ms / P95≈380ms，满足 ≤500ms 硬指标（F4-04 / SC-06）。
- **答案即计算**：assembler 不只是"找到知识"，还负责"算出答案"（金额合计 100% 正确，SC-K3）。

### 4.3 横切机制一：偏好动态捕捉与版本化（M2，要求 2）

- **提取**：从多源融合证据中识别三类偏好（操作习惯 / 输出风格 / 安全策略），规则信号 + 离线文本生成抽取键值对。
- **版本化**：每次更新写 `preference_history` 快照，主表 `version+1`，旧值永不丢失（F2-05）。
- **回溯与适配**：`/preference/{id}/history` 回溯历史版本（F2-07）；偏好带 `scope` 与场景标签，调用时按当前上下文解析生效版本，实现跨场景复用（F2-06）。

### 4.4 横切机制二：冲突智能仲裁（M4，要求 3）

- **检测**：对同实体、同字段的新旧值做矛盾判定（数值/枚举直接比较，文本经语义相似度判反义）。
- **裁决**：默认 `NEW_WINS`，旧版本置 `SUPERSEDED`（保留而非删除），可配 `MERGE`/`MANUAL`。
- **审计**：生成 `ConflictRecord{old,new,resolution}`，全程留痕（目标正确率 ≥88%，F3-01）。

### 4.5 横切机制三：安全识别与精准遗忘（M7，要求 5）

- **敏感识别**：写入入口前置 `detector`，正则 + 规则识别敏感字段并打分，高敏内容过滤/脱敏、默认不出端（F5-01/02/05）。
- **自然语言遗忘**：解析指令意图 → 构造匹配条件（如 `title~"4月" AND source_type=OCR`）→ 定位目标 → 级联清理 knowledge + evidence + 实体关系，生成 tombstone 同步删除，不误删（F5-03/04）。

### 4.6 横切机制四：记忆流转（M6，要求 6）

短期（会话上下文）→ 中期（近期会话摘要）→ 长期（evidence/knowledge）三层模型；`promote`/`demote` 双向流转，TTL 衰减管理短/中期生命周期；promote 复用 M1→M3 写入管线，保证沉淀内容同样结构化可检索（F6 / D-05）。

---

## 5. 业务全链路流程（端到端剧本）

把上面的机制串成完整剧本，对应 README 故事与附录 A 场景。

### 5.1 全链路：从"拍照记账"到"模糊提问得到答案"

```
T0 写入：林太太微信发来支出清单图片
  OS Agent OCR → /memory/write(OCR)
  → M7 敏感预检(无敏感→sensitivity=0)
  → M1 清洗/标准化/实体规范化(国家电网…)/质量评分(0.94)
  → 落 evidence + ACK
  → 异步：M3 结构化(FACT) + 建图(国家电网─BELONG_TO→水电燃气) + INT8 向量
  → sync 广播 → 客厅一体机/笔记本同步到同一条记忆
  → 前端通知"记忆已沉淀"

T1 提问：客厅大屏"我们在水电燃气方面花了多少钱？"
  快捷键唤起聊天框 → /memory/query(context_hint={time_range:last_month})
  → M5 路由 → BM25∥ANN∥Graph 并行 → RRF 融合 → INT8 重排
  → assembler 过滤 category==水电燃气 → 210+68.5+156=434.50
  → 返回 answer + EvidenceCard(置信度0.93, 210ms)
  → 前端展示答案，可点"查看原文"追溯 OCR evidence

T2 修正："燃气费不是156，是186"
  → M1→M3 候选新知识 → M4 检测字段级矛盾
  → ConflictRecord(NEW_WINS) 旧版 SUPERSEDED，新版 ACTIVE
  → sync 版本向量合并 → 前端冲突 Tab 可审计

T3 遗忘："忘记那张4月支出清单"
  → /forget → M7 解析 → 匹配 title~4月 & OCR
  → 返回级联影响范围 → 前端 ForgetDialog 二次确认
  → 级联清理 knowledge+evidence+关系 → tombstone 同步 → 通知"已遗忘"
```

### 5.2 全链路角色协作图

```
[前端 UKUI]  唤起/展示/确认/通知
     │  D-Bus / HTTP+WS
[API 接入层]  协议适配 · 事件推送
     │
[M7]→[M1]→[M3/M2]→[M4]   写入链（异步）
[M5]                       检索链（在线 ≤500ms）
[M6]                       记忆流转（短/中/长期）
     │
[存储层]  evidence/knowledge/preference + FTS5/向量/图/审计
     │
[同步层]  CRDT + Gossip + TLS（多设备对等，去中心化）
```

### 5.3 关键业务规则与边界定义

| 规则 | 定义 | 依据 |
|------|------|------|
| 写入可异步、检索须实时 | evidence 同步落库即 ACK；检索 P95≤500ms | F4-04 / SC-06 |
| 检索路径零 LLM、零网络 | 仅 embedding + SQL + 图遍历 | SC-06 |
| 冲突以新为准且留痕 | 旧版 SUPERSEDED 不删除，生成 ConflictRecord | F3-01 |
| 遗忘须级联且精准 | 清理 knowledge+evidence+关系，不误删他项 | F5-04 |
| 敏感数据默认不出端 | sensitivity 高的不参与跨设备同步 | F5-05 |
| 共享可见性受控 | `scope` 区分 `user:*` 私有 / `shared:home` 共享 | 创新点 |
| 偏好低置信不生效 | 低于阈值标记候选，不污染长期记忆 | F2 |

---

## 6. 分布式记忆共享（去中心化）

- **节点对等**：每台麒麟设备运行一个 Memory Daemon，本地完整存储。
- **同步单元**：knowledge_item / preference 以 CRDT（LWW-Element-Set + 版本向量）合并，天然解决并发冲突。
- **发现与传输**：局域网 mDNS/Gossip 发现节点，TLS + 设备密钥加密通道。
- **共享域**：`scope` 字段控制可见性（私有 `user:*` vs 共享 `shared:home`），敏感数据默认不出端。
- **删除传播**：遗忘生成 tombstone，经 oplog 同步，多设备一致删除。

---

## 7. KylinSDK 适配总览

| 能力 | SDK | 用途 |
|------|-----|------|
| 文本/图像向量化 | `coreai/embedding`（9.4.3） | M5 ANN 通道、M3 知识 embedding |
| OCR | AI SDK 9.4.1 | M1 图片支出清单接入（附录 A） |
| 文本生成 | AI SDK 9.5.1 | 离线偏好/知识抽取（仅写入路径，非检索路径） |
| 桌面通知 | `kysdk-notification`（8.2） | 记忆事件、冲突提醒 |
| 全局快捷键 | `kysdk-shortcut`（8.3） | 唤起聊天框 |
| 主题 | 8.5 Theme | 跟随 UKUI 明暗主题 |
| Qt 扩展控件 | 应用支撑 SDK 4.1.x | 聊天框 UI 组件 |
| 统一配置 | 5.7 Unified_Configuration | 端侧配置持久化 |

---

## 7. 仓库结构

```
Project.PIXIU/
├── backend/      # 记忆服务守护进程（详见 backend/docs/ARCHITECTURE.md）
├── frontend/     # UKUI 桌面组件/聊天框（详见 frontend/docs/ARCHITECTURE.md）
├── docs/         # 题目、SDK 文档、验收规范、架构设计
└── scripts/      # 部署/评测脚本
```

详细设计见 `backend/docs/ARCHITECTURE.md` 与 `frontend/docs/ARCHITECTURE.md`。
