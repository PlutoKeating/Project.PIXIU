# Project.PIXIU 总体架构设计

> **项目代号**：PIXIU（貔貅）
> **题目**：麒麟软件《OSAgent 记忆优化及高效应用研究》
> **定位**：面向居家/办公多用户协作环境的**去中心化分布式 Agent 记忆共享系统**

> [!CAUTION]
> 2026-09-03 赛题复核：当前实现是记忆子系统和记忆控制台，不是完整 OS Agent；
> portable 路径仍由 SQLite/INT8 扫描承担；strict 路径已接入系统 Vector Engine，
> 但最终候选的产品全链路尚未通过，仍不满足 PPT 硬门槛。团队已批准新增
> openKylin `kylin-agent`/`agent-runtime` 宿主与
> Module E MemoryProvider 适配层；这是一项团队工程决策，并非赛方指定技术栈。
> 完整差距、决策和验收状态见
> `OS_AGENT_INTEGRATION_ASSESSMENT.md` 与 `AcceptanceTestSpecification.md`。

---

## 1. 设计目标与约束

### 1.0 平台兼容边界

架构采用“麒麟能力优先、Debian 软件降级”的双路径：所有 KylinSDK 调用封装在
适配层，运行时先探测原生扩展与服务；不可用时，核心业务切换到明确标识的可移植
实现。`PIXIU_EMBEDDING=auto` 为默认，优先 `KylinTextEmbedding`，否则使用
`PortableTextEmbedding`；`kylin` 为严格验收模式，`portable` 为通用 Debian
验证模式。Qt/UKUI 同样以 `PIXIU_HAVE_KYSDK` 控制专有集成。降级路径保证可用性，
不承诺也不替代麒麟 SDK 的召回率、时延和桌面集成验收。

### 1.1 模块划分与 Agent 基座

PIXIU 后端按架构维度拆分为两个独立开发模块，物理上位于 `backend/` 下的不同目录树，通过 `foundation/core/` 中的抽象接口（ABC）解耦：

```
┌──────────────────────────────┐
│ openKylin Agent 宿主          │
│ 会话/规划/工具/审批/搜索       │
│ + 双主题/离线富消息表现层       │
└──────────────┬───────────────┘
               │ MemoryProvider
┌──────────────▼───────────────┐   ┌──────────────────────────────┐
│ Module E: Agent 集成适配层    │   │ Module A: PIXIU 记忆控制台   │
│ 生命周期/记忆工具/探测/审计   │   │ 查询/管理/配对/诊断           │
└──────────────┬───────────────┘   └──────────────┬───────────────┘
               │ HTTP REST · WS                   │ HTTP/WS/D-Bus
               └──────────────────┬────────────────┘
                                  ▼
┌──────────────────────────────────────────────────────────┐
│  后端 (backend/)                                           │
│                                                           │
│  Module B: 记忆业务引擎 (engine/)                          │  Python 3.10 + C++
│  多源接入 · 偏好捕捉 · 知识结构化 · 冲突仲裁 · 安全遗忘     │
│  行为采集 · 主动递送(insights/digest)                       │
│  ★ 通过 Repository ABC 接口消费存储层                      │
│                                                           │
│  Module C: 后台基础设施 (foundation/)                      │  Python 3.10 + SQLite
│  API 网关 · 存储层 · 混合检索 · 记忆流转 · P2P 同步 · 评测  │
│  监控引擎(目录监视/行为采集/配置热生效)                     │
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
| (4) | V11 端侧部署、调用麒麟 embeddingSDK 和系统向量数据库、检索 ≤500ms | B engine/kylin + C foundation/retrieval | H-01~H-03、F4-01~F4-05 |
| (5) | 敏感信息识别过滤、自然语言精准遗忘 | B engine/security | F5-01~F5-05 |
| (6) | 短/中期记忆数据流转兼容 | C foundation/flow | F6-01~F6-03 |
| (7) | 量化评测机制与测试报告 | C foundation/eval | F7-01~F7-05 |
| Agent 集成 | 多会话/多轮、规划与工具、记忆生命周期闭环 | E integrations/kylin_agent + openKylin 宿主 | A-01~A-10、F1-01、F1-02、F6-05 |
| Agent 宿主 UI | 默认浅色；Ant Design 风格科技蓝浅/暗主题与设置页即时切换；焦点/缩放、Enter 发送、即时 waiting、分段 LLM 消息；离线 Markdown/GFM 表格/KaTeX/Mermaid/emoji 渲染；工具、记忆、Shell、Web 搜索使用可持久化的默认折叠动态卡片；麒灵系统云模型优先及 GUI 直连凭据管理 | build/release/agent-host 下游补丁 + integrations/kylin_agent/message_renderer | A-10a/A-10b（团队质量门） |

### 1.3 关键约束

- **端侧轻量化**：x86/ARM 麒麟机型，内存占用低，离线可用
- **检索在线零 LLM**：仅用 embedding + 结构化字段 + 图遍历，保证 P95 ≤ 500ms
- **国产化硬门槛**：embedding 必须经麒麟 `coreai/embedding` C 接口；生产向量存储/检索必须经系统 Vector Engine SDK；最终软件必须在银河麒麟桌面操作系统 V11 验证
- **Agent 完整性**：项目工程上选择由 openKylin Agent 基座提供多轮会话、规划、工具、Shell/联网搜索和审批，PIXIU 通过原创记忆适配层接入；赛方材料未指定必须使用该基座，也未要求从零重写 Agent
- **推理接入**：V11 通过回环适配服务调用系统 Kylin GenAI PublicCloud 模型，Runtime 继续掌管工具与审批；通用 Debian 画像使用 GUI 配置的官方直连服务
- **消息渲染隔离**：模型文本只进入包内 `qrc:` 富文本页面；页面禁用任意 HTML、远端脚本、远端样式和网络读取。实际工具事件进入独立 UI 历史角色并在组装模型请求时过滤
- **集成隔离**：Module E 只能消费 `docs/API.md` 的公共契约；上游 submodule 默认只读，最小补丁须独立记录来源、理由、许可证和维护方式

---

## 2. 核心数据模型

```jsonc
// evidence：原始证据（可追溯源）；Agent 关联字段与正文分离存储
{ "id": "evd_...", "source_type": "OCR|TOOL_RESULT|USER_BEHAVIOR|MANUAL_CONFIG|CONVERSATION",
  "raw": {}, "quality_score": 0.94, "sensitivity": 0,
  "provenance": {"session_id": "...", "run_id": "...", "turn_id": "...",
                 "tool_call_id": null, "tool_name": null, "approved": null,
                 "occurred_at": 1788393600},
  "scope": "user:alice", "created_at": "..." }

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
      engine/knowledge:embed_writer → 麒麟 coreai/embedding（真实 SDK）→ INT8 量化 → 写 knowledge_vec + knowledge_fts
      engine/preference:extractor → 偏好提取
      engine/conflict:arbiter → 与既有知识比对仲裁
  → foundation/sync:CRDT 广播（✅ 已实现，Phase 3）
```

> 现状（2026-08-11）：`POST /memory/write` 在请求内同步执行
> ingest → knowledge → preference → conflict 整条管线；`shared:*` 写入会追加
> 签名 SyncOp 进入 `sync_oplog` 供 CRDT 广播（网络运行时默认开启，SN-4）。
> 2026-09-03 补齐写入前置安全门：先检测、后占用幂等 receipt；`user:*` 敏感
> evidence 本地标记并从 Agent 上下文隔离，敏感内容拒绝进入 `shared:*`；检测故障
> fail closed，因而不会以 sensitivity=0 静默绕过或进入同步链路。
> `POST /memory/update` 保持 `knowledge_id` 不变，以存储层原子 compare-and-swap
> 校验版本，追加更新 evidence、重建图/向量并为 `shared:*` 生成同一实体的同步操作；
> 两个离线节点由同一基线产生的并发版本继续交由 CRDT 与确定性冲突仲裁收敛。

**三索引齐写**：一条知识同时进 FTS5（关键词）、向量表（语义）、图（实体关系），这是混合检索的前提。
当前 FTS 写入、INT8 向量写入与图（`knowledge_entities`/`relations`）均已实现；
ANN/图召回由 retrieval 阶段（Phase 2）消费。

### 3.2 在线检索路径：500ms 内给出可信答案

> ✅ 该路径已由 foundation/retrieval 实现（Phase 2 交付，2026-08-10 合入 main），
> `/memory/query` 为真实链路。当前机制：规则路由；FTS5 trigram（含 CJK 回退）；
> INT8 向量线性扫描；持久化图召回；三通道 `asyncio.gather` 并发；scope/time_range
> 硬过滤；RRF 融合；词法重排；查询类别聚合与证据回溯。
> `/agent/context` 在相同召回之上组装多候选上下文，强制 scope 和敏感 evidence
> fail-closed，并输出字符预算、freshness、冲突状态及 knowledge/evidence 引用；
> Module E 负责继续按上游 MemoryProvider 的不可信上下文边界转义后注入。
> 开发基线（50 条记录、1000 次查询、stub embedding）为 P50=11.4ms、P95=13.3ms，
> 真实麒麟 embedding + 正式数据集的召回率/P95 验收留待麒麟环境。

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

✅ 已实现：`/preference/extract`、`/preference/{id}/history`。

- 提取三类偏好：操作习惯 / 输出风格 / 安全策略
- 版本化：每次更新写 preference_history 快照，主表 version+1
- 回溯与适配：`/preference/{id}/history` 回溯历史版本；偏好带 `scope` 与场景标签

### 3.4 冲突仲裁（engine/conflict）

✅ 已实现：`GET /conflicts` 审计列表。

- 检测：同实体同字段新旧值做矛盾判定
- 裁决：默认 NEW_WINS，旧版 SUPERSEDED（保留而非删除），可配 MERGE/MANUAL
- 本地 shared 写入：仲裁完成后从知识仓储重新读取最终持久化条目，再生成 CRDT 操作；
  同步载荷不得使用仲裁前输入，确保 MERGE 的正文与 version 和本地业务视图一致
- 同步物化：远端不同 ID 知识同样进入语义仲裁；同步来源按
  `updated_at`、`created_at`、`id` 全序选胜者，消除两端反向到达造成的业务视图分歧
- 审计：生成 ConflictRecord，全程留痕

### 3.5 安全识别与精准遗忘（engine/security）

✅ 已实现：`POST /forget`（confirm 两段式）。

- 敏感识别：写入入口前置 detector（正则 + 规则识别身份证/银行卡等），sensitivity 评分
- 自然语言遗忘：解析指令 → 构造匹配条件 → 级联清理 knowledge + evidence + 实体关系

### 3.6 记忆流转（foundation/flow）

✅ **已实现**（Phase 2 交付，2026-08-10 合入 main）：`POST /memory/flow/promote`
为真实链路，复用引擎 ingest→knowledge 管线；短/中期上下文 SQLite 持久化、
批量预校验与幂等 promote、长期知识 demote、分层 TTL 与到期清理均已落地。

### 3.7 被动监控（目录监视 + 行为采集）

✅ **已实现**（批次①掌控层 2026-08-26 / 批次②目录监视 2026-08-26 / 批次③行为采集
2026-08-29，均合入 main）：

- **掌控层**：前端 MonitorController + 监控中心双 Tab 面板、托盘/悬浮球/设置三处
  暂停入口与 ⏸ 徽标；`/monitor/config` 读写 + `/monitor/log` 分页 + `capture_event`
  WS 广播；配置持久化并热生效（GET/PUT 全量提交）。
- **目录监视**：后端常驻 monitor daemon（Module C，独立于前端生命周期）；
  watchdog 防抖 + 稳定性检查 → 图片走麒麟 OCR 管线、文本走 ingest 管线入库；
  敏感条目按 detector 结果以 `sensitive_quarantined` 广播，不入 `shared:*`。
- **行为采集**：BehaviorCollector 轮询窗口焦点 + 应用活跃时长，产出 USER_BEHAVIOR
  evidence（`{"app","title","focus_seconds","hour_bucket","day_type"}`），敏感标题
  fail-closed 丢弃；无 X 环境降级不采集。
- **默认状态**：`PIXIU_MONITOR_ENABLED` 代码默认关，随包 `pixiu.env` 置 1（产品
  默认开）；`config.enabled` 为独立门控。

### 3.8 主动递送（洞察流 / 定时简报 / 相关性提醒）

✅ **已实现**（批次④，2026-08-29 合入 main）：

- **洞察流**：`GET /delivery/insights`——最近 24h 高质量记忆按 quality 降序，
  敏感过滤 + MANUAL 冲突抑制，欢迎页动态建议卡（`kind:"recent"`；偏好类洞察
  `kind:"preference"` 为发布后增强项）。
- **定时简报**：`GET /delivery/digest`——按日聚合当日记忆沉淀（ingested 分组
  计数 + sensitive 单列），服务端生成中文文案，空日返回「当日无新记忆」。
- **相关性提醒**：前端在既有 captureEvent/偏好事件路径上做 token 交集相关性
  判断 + 每日上限 3 条；偏好学习即时通知。

---

## 4. 分布式记忆共享（去中心化）

核心创新点。完整管理链路由 `foundation/sync/` 实现：

> ✅ **Phase 3 已实现**（2026-08-10 合入 main）：Ed25519 身份、QR/PIN 配对、
> LWW-Element-Set + 版本向量、签名 oplog、Gossip + 反熵对账、墓碑回收、
> mDNS 信任过滤、TLS 1.3 mTLS、CRDT 胜者物化；`/sync/*` 端点已真实接入。
> 物化不直接绕过业务索引层：快进和自动仲裁结果均复用 `KnowledgeService`，重新生成
> 图关系及 embedding/VectorStore 数据；墓碑同时隐藏知识并删除生产向量。
> shared 本地写入也不广播仲裁前对象：API 在冲突服务完成持久化后重读最终条目，
> 再将实际 MERGE/NEW_WINS 正文与版本追加到 oplog。
> knowledge 早于 evidence 到达时以 `sync_meta` 持久登记待补引用，后续 evidence
> 物化会补链并清理记录，避免跨批次乱序造成永久无来源知识。
> SN-4（2026-08-29）起**网络运行时默认开启**（`PIXIU_SYNC_NETWORK_ENABLED` 缺省 true），
> 缺 advertise/TLS 证书自动降级不阻塞 API；显式 `false` 或运行时 `enabled=false`
> 停止广播与监听（安全边界见 `backend/foundation/docs/ARCHITECTURE.md` §1.6）。

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

基础表 16 张（由 `storage/schema.py` 创建）：记忆/流转类（`evidence`,
`knowledge_items`, `knowledge_evidence`, `knowledge_entities`, `preferences`,
`preference_history`, `entities`, `relations`, `conflict_records`,
`memory_contexts`）+ 同步类（`sync_identity`, `sync_peers`, `sync_state`,
`sync_peer_acks`, `sync_meta`, `sync_oplog`）。
`knowledge_fts`（FTS5 trigram）与 `knowledge_vec`（INT8）由仓储首次使用时惰性创建。
建表/迁移统一走 `storage/migrations.py` 的版本化迁移。

## 6. KylinSDK 适配总览

| 能力 | SDK | 用途 | 调用者 | 状态 |
|------|-----|------|--------|------|
| 文本向量化 | `coreai/embedding`（9.4.3，`libkysdk-coreai-embedding`） | ANN 通道、知识 embedding | engine/kylin（pybind11 绑定） | ✅ 本机构建成功（麒麟运行时验收待真机） |
| 向量数据库 | `libkysdk-vector-engine-client` | ANN 检索存储 | engine/kylin 适配 + foundation `VectorStore` seam | 🟡 生产选择/严格失败已接线；V11 真 SDK 全链路证据未完成，H-02 仍未通过 |
| OCR | AI SDK 9.4.1 | 图片支出清单接入 | engine/ingest | ✅ 已接入（2026-08-24，`POST /memory/ocr`） |
| 文本生成 | AI SDK 9.5.1 | 离线偏好/知识抽取 | engine/preference | ⬜ 待接入 |
| 桌面通知 | `kysdk-notification`（8.2） | 记忆事件、冲突提醒 | frontend | 🟡 前端已实现（KYSDK=ON 路径），KYSDK=OFF 降级为系统托盘通知 |
| 全局快捷键 | `kysdk-shortcut`（8.3） | 唤起聊天框 | frontend | 🟡 前端已实现（KYSDK=ON 路径），KYSDK=OFF 降级为 QShortcut |
| 主题 | 8.5 Theme | 跟随 UKUI 明暗主题 | frontend | ✅ 已实现（含运行时换肤修复） |
| Agent 宿主主题 | Qt 调色板 + UKUI/GNOME/KDE 主题探测 | KylinAgent 双主题语义令牌与状态可读性 | build/release/agent-host | 🟡 代码与对比度门已实现，最终 V11 视觉矩阵待复核 |
| Agent 产品身份 | 同包 `SOUL.md` + 宿主启动写入 | PIXIU 本地 Working Agent、工具工作流与分布式记忆工作台 | integrations/kylin_agent + build/release/agent-host | 启动前事务部署并由 Gateway 读取 |
| Qt 扩展控件 | 应用支撑 SDK 4.1.x | 聊天框 UI 组件 | frontend | 🟡 代码已兼容，降级路径使用标准 QWidget |

> 官方 SDK 仓库以 submodule 纳入 `third_party/`（openkylin/nile-sp2），绑定构建见
> `backend/engine/kylin/cpp/README.md`。

## 7. API 端点

详见 `docs/API.md`。核心端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/memory/write` | 写入记忆（✅ 已实现） |
| POST | `/memory/query` | 混合检索（✅ 已实现） |
| POST | `/agent/context` | Agent 预算化安全上下文（✅ 已实现） |
| POST | `/agent/lifecycle` | Agent 生命周期短/中期 context（🟡 基础事件接入） |
| GET | `/evidence/{id}` | 证据详情（✅ 已实现，2026-08-24） |
| POST | `/memory/ocr` | 图片 OCR 识别（✅ 已实现，2026-08-24） |
| POST | `/preference/extract` | 偏好提取（✅ 已实现） |
| GET | `/preferences` | 偏好列表（✅ 已实现，2026-08-24） |
| GET | `/preference/{id}/history` | 偏好回溯（✅ 已实现） |
| POST | `/forget` | 自然语言遗忘（✅ 已实现） |
| GET | `/conflicts` | 冲突审计（✅ 已实现） |
| POST | `/memory/flow/promote` | 记忆流转（✅ 已实现） |
| POST | `/sync/token` | 生成配对令牌（QR/PIN）（✅ 已实现，2026-08-24） |
| POST | `/sync/pair` | 设备配对（QR/PIN + 签名令牌）（✅ 已实现） |
| GET | `/sync/peers` | 节点列表（✅ 已实现） |
| GET | `/sync/discover` | 发现局域网设备（含未配对）（✅ 已实现，2026-08-29） |
| POST | `/sync/pair/request` | 发起确认式配对（含 6 位 PIN）（✅ 已实现，2026-08-29） |
| POST | `/sync/pair/confirm` | 确认/拒绝配对请求（✅ 已实现，2026-08-29） |
| GET | `/sync/status` | 同步状态（enabled/paused）（✅ 已实现） |
| PUT | `/sync/settings` | 更新同步开关（✅ 已实现，2026-08-29） |
| POST | `/sync/peers/{id}/revoke` | 解绑设备（✅ 已实现） |
| GET/PUT | `/monitor/config` | 监控配置读写（✅ 已实现，2026-08-26） |
| GET | `/monitor/log` | 监控活动日志（✅ 已实现，2026-08-26） |
| GET | `/delivery/insights` | 洞察流（✅ 已实现，2026-08-29） |
| GET | `/delivery/digest` | 定时简报（✅ 已实现，2026-08-29） |
| WS | `/events` | 事件推送（✅ 已实现，2026-08-20 修复注册；六类事件广播） |

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
├── frontend/                  # Module A: PIXIU 记忆控制台
│   └── docs/                  # 前端文档
├── integrations/
│   └── kylin_agent/           # Module E: Agent/MemoryProvider 适配与契约测试
└── third_party/
    ├── kylin-agent/           # 官方桌面 Agent
    ├── kylin-agent-runtime/   # 官方 Agent 运行时/记忆扩展点
    ├── kylin-coreai-embedding/
    └── libkysdk-vector-engine-client/
```

详细架构见 `backend/engine/docs/ARCHITECTURE.md`、`backend/foundation/docs/ARCHITECTURE.md`、
`frontend/docs/ARCHITECTURE.md` 和 `decisions/0001-use-openkylin-agent-host.md`。
