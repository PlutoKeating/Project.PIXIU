# 模块 C · 后台基础设施（Backend Foundation）

> **目录**：`backend/foundation/`
> **技术栈**：Python 3.10 + SQLite + C++（pybind11）
> **开发人员**：1人（后端基础设施）
> **提供**：`core/` 中的共享数据模型和 Repository 接口

> [!CAUTION]
> 当前 Foundation 是记忆基础设施而非完整 Agent；SQLite/INT8 语义扫描只可作为
> 降级/对照，尚未满足系统 Vector Engine 硬门槛。
> 团队已批准 Module E 通过公共 API 接入；Foundation 不承载 Agent 循环。
> capability/runtime、evidence Agent provenance、短中期生命周期、持久化幂等与
> 审计式失败 receipt 恢复均已完成；Module E 适配已在独立目录实现，真实宿主证据
> 与长期化仍待补齐。

> **当前状态（2026-09-04）**：Phase 0~5 基础范围完成——retrieval、flow、sync（CRDT）、
> eval（评测框架+基准）、D-Bus 服务均已落地，当前 29 个 REST 端点真实实现（含
> Agent 预算化安全上下文、原子版本化记忆更新和六类生命周期 context）。
> 当前 Foundation 635 + Engine 154 项通过；WS `/events` 已注册并验证。剩余 P0 是
> 最终 V11 双 SDK 性能/服务拓扑、完整 Agent 生命周期和三台设备真实局域网互操作；
> 历史单机或 portable 通过数不得替代这些证据。

---

## 一句话

Foundation 是 PIXIU 的"骨架与血管"——它提供 API 网关让外部问进来，存储层把记忆存下去，检索引擎在 500ms 内找到答案，同步层让多台设备自动对齐记忆。

## 职责边界

| Foundation 做的事 | Foundation 不做的事 |
|------------------|-------------------|
| HTTP/WS/D-Bus API 路由 | 数据清洗和标准化 |
| SQLite 仓储实现（20 张基础表 + FTS5/向量索引，schema v12） | 偏好提取和版本化 |
| 混合检索（BM25/ANN/Graph→融合→重排→组装） | 知识冲突仲裁 |
| 共享数据模型和 Repository 接口定义 | 敏感信息检测 |
| CRDT 分布式同步 + Gossip 发现 + TLS | 忘记得执行逻辑 |
| 记忆流转（短/中/长期） | KylinSDK embedding 调用 |
| 评测框架 | — |

## 子包速览

| 子包 | 职责 | 核心类 |
|------|------|--------|
| `core/` | 共享契约：数据模型、Repository ABC、配置、日志 | `Evidence`, `KnowledgeItem`, `Preference`, `*Repository` |
| `api/` | API 网关：HTTP/WS/D-Bus 路由 + 依赖注入 | `HttpApp`, `WsHandler`, `DbusService`, `DI` |
| `storage/` | SQLite 仓储实现（20 张基础表 + WAL + FTS5/向量索引，schema v12） | `SqliteEvidenceRepo`, `SqliteKnowledgeRepo`, `SqliteFlowStore`, ... |
| `retrieval/` | 混合检索管线（路由→3通道→融合→重排→组装） | `RetrievalService`, `Router`, `BM25`, `ANN`, `GraphSearch`, `Fuser`, `Reranker`, `Assembler` |
| `flow/` | 记忆流转（promote/demote + TTL） | `FlowService`, `Promoter`, `TTLManager` |
| `sync/` | P2P CRDT 同步 | `SyncService`, `CRDT`, `Gossip`, `Discovery`, `Transport` |
| `eval/` | 评测框架 | `EvalService`, `Benchmark` |

## 数据流

```
[HTTP 请求] → api/（路由+参数校验）
                ↓
           [调用引擎 Service]（由 DI 注入）
                ↓
           [引擎] 通过 core/ 接口 → storage/（SQLite 实现）
                ↓
           [结果] → api/ → [HTTP 响应]

[写入管线] → 引擎 ingest → 落 evidence
                ↓
           同步写入三个索引（FTS5/向量/图）
                ↓
           sync/ CRDT 广播 → 其他设备
```

详细架构：`backend/foundation/docs/ARCHITECTURE.md`
开发任务：`backend/foundation/docs/DEV_TASKS.md`
Phase 1 报告：`backend/foundation/docs/PHASE1.md`
Phase 2 报告：`backend/foundation/docs/PHASE2.md`
