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

## 4. 关键端到端流程

### 4.1 写入路径（异步，对应附录 A 步骤1）
`前端/Agent 事件 → M1 校验+清洗+实体规范化+质量/敏感度评分 → 落 evidence(<50ms) → 异步触发 M2/M3：抽取实体关系图 + 生成 INT8 embedding → 写 knowledge_items / preferences`

### 4.2 在线检索路径（零 LLM，≤500ms，对应附录 A 步骤2）
`query → M5.r 查询路由(意图分类+实体抽取) → 并行 BM25 / ANN / Graph → RRF 融合 + context_hint 加权 → INT8 重排 → M5.a 组装(结构化聚合 + evidence 回溯) → 返回 MemoryAtom`

### 4.3 冲突与遗忘
- **冲突**：M4 检测新旧知识矛盾 → 生成 `ConflictRecord` → 新版本生效，旧版本置 `SUPERSEDED`。
- **遗忘**：M7 解析自然语言指令 → 匹配目标 → 级联清理 knowledge + evidence + 实体关系。

### 4.4 记忆流转（M6）
短期记忆(会话上下文) → 中期记忆(近期会话摘要) → 长期记忆(本系统 evidence/knowledge)，提供双向 promote/demote 接口与 TTL 衰减策略。

---

## 5. 分布式记忆共享（去中心化）

- **节点对等**：每台麒麟设备运行一个 Memory Daemon，本地完整存储。
- **同步单元**：knowledge_item / preference 以 CRDT（LWW-Element-Set + 版本向量）合并，天然解决并发冲突。
- **发现与传输**：局域网 mDNS/Gossip 发现节点，TLS + 设备密钥加密通道。
- **共享域**：`scope` 字段控制可见性（私有 `user:*` vs 共享 `shared:home`），敏感数据默认不出端。

---

## 6. KylinSDK 适配总览

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
