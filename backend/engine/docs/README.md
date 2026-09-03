# 模块 B · 记忆业务引擎（Memory Engine）

> **目录**：`backend/engine/`
> **技术栈**：Python 3.10 + C++17（pybind11，KylinSDK 封装）
> **开发人员**：1人（后端业务逻辑）
> **依赖**：`backend/foundation/core/` 中的 Repository 接口和数据模型

> 已批准的 Agent 路线要求 Module B 在 vNext 增加合法的 `CONVERSATION` 接入，
> 并完善 `TOOL_RESULT` 的 session/run/turn/tool-call 来源信息。Module E 只通过
> 公共 API 提交这些数据；当前四类 Connector 未扩展前，不得宣称多轮对话已接入。

---

## 一句话

引擎是 PIXIU 的"大脑"——它接收各种来源的零散信息，清洗成规整的结构化记忆，捕捉用户的偏好习惯，检测知识之间的冲突，保护敏感数据，并支持用自然语言"忘记"某条记忆。

## 职责边界

| 引擎做的事 | 引擎不做的事 |
|------------|-------------|
| 清洗/标准化多源数据 | HTTP 路由和请求解析 |
| 提取用户偏好并版本化管理 | SQLite 存储实现 |
| 结构化知识（事实/工作流/案例/模板）+ 建实体关系图 | 检索引擎（BM25/ANN/Graph）|
| 检测并仲裁新旧知识冲突 | 分布式 P2P 同步（CRDT/Gossip）|
| 敏感信息识别与过滤 | 评测脚本和压测 |
| 自然语言精准遗忘 | — |
| 封装 KylinSDK embedding C 接口 | — |

## 子包速览

| 子包 | 职责 | 核心类 |
|------|------|--------|
| `ingest/` | 多源数据接入、清洗、标准化、质量评分 | `IngestionService`, `Cleaner`, `Normalizer`, `Quality` |
| `preference/` | 偏好提取、版本化、跨场景适配 | `PreferenceService`, `Extractor`, `Versioning`, `Adapter` |
| `knowledge/` | 知识结构化、实体关系图、向量写入 | `KnowledgeService`, `Structurer`, `GraphBuilder`, `EmbedWriter` |
| `conflict/` | 矛盾检测、裁决、审计 | `ConflictService`, `Arbiter` |
| `security/` | 敏感识别、自然语言遗忘 | `SecurityService`, `Detector`, `ForgetEngine` |
| `kylin/` | KylinSDK embedding C++ 封装（真实 coreai/embedding 调用） | `KylinTextEmbedding` |

## 数据流

```
[外部输入] → ingest/（清洗标准化+质量分）
                ↓
           [evidence 写入 → 通过 Repository 接口]
                ↓
           knowledge/（结构化→建图→向量化）
           preference/（偏好提取）
           conflict/（与新知识比对）
                ↓
           security/（敏感标记/遗忘指令）
                ↓
           全部通过 ABC 接口写入 storage/（由 Module C 实现）
```

详细架构：`backend/engine/docs/ARCHITECTURE.md`
开发任务：`backend/engine/docs/DEV_TASKS.md`
