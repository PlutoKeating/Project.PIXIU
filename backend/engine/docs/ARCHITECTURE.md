# 模块 B · 记忆业务引擎架构设计

> **角色**：常驻记忆服务中的业务逻辑层，处理所有"记忆写入→结构化→应用"的流程。
> **与模块 C 的边界**：引擎**消费** `foundation/core/` 中的 Repository 接口（ABC）和数据模型，**不依赖** `foundation/` 中的任何实现代码。
>
> **已批准 vNext 边界**：Module E 通过 Module C 公共 API 提交 Agent 生命周期
> 数据；Module B 已增加 `CONVERSATION` Connector，`Evidence.provenance` 为对话与
> `TOOL_RESULT` 保留 session/run/turn/tool-call、时间和审批来源。幂等与完整生命周期
> 尚未实现，不得据此宣称完整 Agent 已接入。

> [!CAUTION]
> “SDK 适配/封装存在”不等于赛题硬门槛已通过。最终 V11 生产路径必须真实调用
> `kylin-coreai-embedding`，且系统 Vector Engine 必须实际承担向量存储与检索；
> 当前 SQLite/INT8 检索不能作为向量数据库 SDK 验收证据。

> **状态（2026-08-11）**：全部子包已实现并通过 SQLite 全链路集成测试（麒麟 V11
> 真机全量 pytest 364 passed）；kylin 为真实麒麟 SDK 适配，pybind11 绑定源码
> 就绪，待麒麟环境构建验证。默认 `auto` 模式优先使用该 SDK；缺少原生能力的
> Debian 系统切换到可移植特征哈希向量器，保持核心写入和检索可用。

---

## 1. 设计原则

- **写入可慢，但要稳**：接入、清洗、抽取、向量化都在异步管线里完成，但每条记忆必须能回溯到原始证据。
- **数据默认不出端**：`scope` 字段控制可见性，`sensitivity` 字段控制是否参与同步。
- **模块内高内聚**：每个子包对外只暴露一个 Service 类，内部细节不对外可见。

## 2. 子包详解

### 2.1 ingest/ —— 多源数据接入

**入口**：`IngestionService`

管线流程：

```
Connector（5类来源适配）
  → Cleaner（去噪·去重·缺失补齐）
    → Normalizer（格式标准化·实体规范化）
      → Quality（Schema 校验·quality_score）
        → 落 evidence（通过 EvidenceRepository 接口）
```

**Connector 支持的五类来源**：

| source_type | 输入格式 | 示例 |
|-------------|----------|------|
| `TOOL_RESULT` | JSON（工具输出） | OS Agent 文件搜索返回 |
| `USER_BEHAVIOR` | 事件序列 | 用户操作日志 |
| `MANUAL_CONFIG` | 键值对 | 用户配置内容 |
| `OCR` | 结构化文本 | OCR 识别的清单数据 |
| `CONVERSATION` | 单轮 user/assistant 文本 | OS Agent 已完成的一轮对话 |

**Output**：`Evidence` 对象（通过 `EvidenceRepository.save()` 写入）

```python
class Evidence(BaseModel):
    id: str
    source_type: Literal["OCR", "TOOL_RESULT", "USER_BEHAVIOR", "MANUAL_CONFIG", "CONVERSATION"]
    raw: dict
    quality_score: float  # 0~1, 由 Quality 模块计算
    sensitivity: int      # 0~3, 由 Detector 计算（0=无敏感）
    provenance: AgentProvenance | None  # session/run/turn/tool-call/time/approval
    scope: str            # "user:alice" | "shared:home"
    created_at: int
```

### 2.2 preference/ —— 偏好动态捕捉

**入口**：`PreferenceService`

**三类偏好**：

| 类别 | 说明 | 提取信号 |
|------|------|----------|
| `OP_HABIT` | 操作习惯（如优先使用快捷键） | 行为频率分析 |
| `OUTPUT_STYLE` | 输出风格（如简洁/详细） | 对话模式分析 |
| `SECURITY_POLICY` | 安全策略（如财务数据不外传） | 用户配置+行为 |

**版本化机制**：

```
用户行为触发 → extractor 提取键值对
  → versioning 写入 preference 表（version+1）
  → 旧快照写入 preference_history
  → /preference/{id}/history 返回回溯
```

### 2.3 knowledge/ —— 知识结构化整合

**入口**：`KnowledgeService`

**四类知识**：

| kind | 说明 | 示例 |
|------|------|------|
| `FACT` | 事实性知识 | "2026年4月国家电网电费210元" |
| `WORKFLOW` | 工作流程 | "处理报销的步骤" |
| `CASE` | 历史案例 | "上次的设计稿修改过程" |
| `TEMPLATE` | 可复用模板 | "报销单填写模板" |

**三索引齐写机制**：

```
evidence → structurer（结构化）
  → graph（抽取实体+关系→写 entities/relations 表）
  → embed_writer（调 KylinEmbedding 生成原始 float 向量→VectorStore.upsert）
  → 同步写 knowledge_fts（FTS5 全文索引）
```

### 2.4 conflict/ —— 冲突仲裁

**入口**：`ConflictService`

**仲裁流程**：

```
新知识与既有知识比对
  → 同实体同字段矛盾判定
    → 数值/枚举：直接比较
    → 文本：语义相似度判断反义
  → 裁决：默认 NEW_WINS（旧版 SUPERSEDED）
  → 生成 ConflictRecord{old, new, resolution}
```

### 2.5 security/ —— 安全与遗忘

**入口**：`SecurityService`

**敏感识别**（挂在写入入口前置）：

```python
# detector 的正则+规则识别
patterns = {
    "身份证": r"\d{18}|\d{17}X",
    "银行卡": r"\d{16}|\d{19}",
    "手机号": r"1[3-9]\d{9}",
}
# 匹配 → sensitivity 评分 (0=无, 1=低, 2=中, 3=高)
# sensitivity>=2 的内容默认过滤/脱敏，不出端
```

**自然语言遗忘**：

```
forget("忘记那张4月支出清单")
  → 解析意图 + 构造匹配条件（title~"4月" AND source_type=OCR）
  → 定位目标 knowledge + evidence + entities/relations
  → 级联清理（标记 FORGOTTEN + VectorStore 删除；其余物理清理由基础设施处理）
  → 生成 tombstone → Sync CRDT 传播（由 Module C 执行）
```

### 2.6 kylin/ —— KylinSDK 适配

**核心类**：`KylinTextEmbedding`

封装麒麟 C 接口 `coreai/embedding`：

```python
class KylinTextEmbedding:
    def __init__(self):
        # text_embedding_create_session + text_embedding_init_session
        ...
    def embed(self, text: str) -> list[float]:
        # 调用 C API 生成向量
        ...
```

底层为 C 接口 SDK `libkysdk-coreai-embedding`（官方仓库以 submodule 纳入
`third_party/kylin-coreai-embedding`），经 pybind11 绑定
`_kylin_text_embedding` 暴露给 Python。`get_embedder("auto")` 优先实例化真实
SDK，SDK/运行时不可用时切换到 `PortableTextEmbedding`；后者是确定性的字符
特征哈希软件实现，不是 SDK mock。麒麟验收使用 `get_embedder("kylin")`，缺少
原生能力时明确抛出 `KylinSDKUnavailableError`，避免降级结果混入验收数据。
原生 wrapper 对 session 采用异常安全销毁，模型维度必须来自 SDK 模型列表且每次
结果长度必须一致；共享 session 的同步调用由互斥锁串行化，阻塞 SDK 调用期间释放
Python GIL。上述是代码/编译级保证，最终服务线程行为仍须在 V11 实测取证。

向量数据库使用 `libkysdk-vector-engine-client`（Milvus 式 gRPC 客户端，
submodule 位于 `third_party/libkysdk-vector-engine-client`），
由 `kylin/vector.py` 封装。适配器已提供集合存在/创建/装载/删除，以及向量
insert/upsert/delete/search 生命周期；删除接口只接受整数主键列表，不向业务调用方
暴露可注入的 SDK 过滤表达式。生产默认严格采用官方 demo 的 `ConnectParam(appId)`
本地连接；SDK 注明 host/port 重载仅用于测试，只有调用方显式同时传入两项时才使用。
`KylinVectorStore` 进一步封装集合惰性创建/装载、
维度约束、字符串 ID 映射和受影响行数校验。Module C 已提供
`auto|kylin|portable` 后端选择并注入生产写入、检索和遗忘链；仍不能仅凭适配器
测试判定 H-02 通过，最终须有 V11 真服务证据。

---

## 3. 对外 Service 接口

引擎每个子包暴露一个 Service 类，供 `foundation/api/di.py` 注入：

```python
class IngestionService:
    def __init__(self, evidence_repo: EvidenceRepository, ...): ...
    async def ingest(self, source_type: str, raw: dict, scope: str) -> Evidence: ...

class PreferenceService:
    def __init__(self, pref_repo: PreferenceRepository): ...
    async def extract(self, evidence: Evidence) -> list[Preference]: ...
    async def get_history(self, pref_id: str) -> list[PreferenceSnapshot]: ...

class KnowledgeService:
    def __init__(self, knw_repo: KnowledgeRepository, entity_repo: EntityRepository,
                 embedder, vector_store: VectorStore): ...
    async def structure(self, evidence: Evidence) -> KnowledgeItem: ...

class ConflictService:
    def __init__(self, knw_repo: KnowledgeRepository, conflict_repo: ConflictRepository): ...
    async def arbitrate(self, new_item: KnowledgeItem) -> Optional[ConflictRecord]: ...

class SecurityService:
    def __init__(self, knw_repo: KnowledgeRepository, entity_repo: EntityRepository,
                 vector_store: VectorStore): ...
    async def detect_sensitivity(self, raw: dict) -> int: ...
    async def forget(self, command: str, confirm: bool) -> ForgetResult: ...
```

---

## 4. 参考文档

| 内容 | 路径 |
|------|------|
| 开发任务书 | `backend/engine/docs/DEV_TASKS.md` |
| 快速启动 | `backend/engine/docs/QUICK_START.md` |
| 共享数据模型 | `backend/foundation/core/models.py`（代码）|
| Repository 接口 | `backend/foundation/core/repository.py`（代码）|
| KylinSDK embedding | `docs/kylin_sdk_docs/9_AI_SDK/9.4.3_Vectorization.md` |
| KylinSDK OCR | `docs/kylin_sdk_docs/9_AI_SDK/9.4.1_OCR.md` |
| KylinSDK 文本生成 | `docs/kylin_sdk_docs/9_AI_SDK/9.5.1_Text_Generation.md` |
