# 后端架构总览

> 本文档从后端整体视角阐述系统设计，详细设计分别见 engine/ 和 foundation/ 的子架构文档。
> 这是两端开发者之间的"接口层"文档。
>
> **状态（2026-09-04）**：引擎核心管线 + foundation 赛题整改持续推进；27 个 REST 端点
> 与六类 WS 事件（memory_ready / conflict_detected / forget_confirmation / sync_event /
> capture_event / pair_request）真实实现；WS `/events` 注册已于 2026-08-20 修复；
> Embedding/Vector Engine 严格绑定已构建并取得 revision 8 产品链阶段性实证；同步网络
> （默认开启）与被动监控四批次（掌控层/目录监视/行为偏好/递送层）已全部落地。
> 最近组合回归 793 passed（Engine 150 + Foundation 626 + Module E 17），前端 ctest
> 38/38；这些数字仍不替代最终 V11/Agent/三设备验收。
> Agent 公共契约已含 provenance、schema v12 幂等/失败恢复与预算化安全上下文；
> 六类生命周期事件已有幂等短/中期 context 入口，Module E 适配已实现。真实宿主
> 触发与长期化策略仍待完成。
>
> 团队已批准由外部 Module E (`integrations/kylin_agent/`) 通过公共 HTTP/WS 契约
> 接入 openKylin Agent。本后端仍只负责记忆能力，不承载会话、规划或工具循环。

---

## 1. 后端全景

后端由两个模块构成，物理分离在 `engine/` 和 `foundation/` 两个独立目录树，以 ABCD 抽象接口解耦：

```
┌──────────────────────────────────────────────────────────────────┐
│  Module B: 记忆业务引擎 (engine/)                                  │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────┐ │
│  │ ingest │ │prefer. │ │knowl.  │ │conflict│ │security│ │kylin │ │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └──────┘ │
│  通过 Repository ABC 接口（core/）调用存储层                          │
└──────────────────────┬───────────────────────────────────────────┘
                       │
┌──────────────────────┴───────────────────────────────────────────┐
│  Module C: 后台基础设施 (foundation/)                              │
│  ┌──────┐ ┌─────────┐ ┌────────┐ ┌──────┐ ┌──────┐ ┌────────┐   │
│  │ core │ │  api    │ │storage │ │retr. │ │ flow │ │ sync   │   │
│  │ 契约  │ │ 网关    │ │ 存储层  │ │检索   │ │流转   │ │ 同步   │   │
│  └──────┘ └─────────┘ └────────┘ └──────┘ └──────┘ └────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## 2. 两条主路径

### 2.1 写入路径（引擎主导）

```
来源(Tool/Behavior/Config/OCR；vNext 增加 Conversation)
  → engine/security:detector 敏感预检
  → engine/ingest: Cleaner → Normalizer → Quality
  → 落 evidence（通过 Repository 接口）<50ms → ACK
  → 异步：
    engine/knowledge: Structurer → Graph → EmbedWriter
    engine/preference: Extractor（若含偏好信号）
    engine/conflict: Arbiter（与既有知识比对）
  → foundation/sync: CRDT 广播（✅ Phase 3 已实现，网络运行时默认开启）
```

### 2.2 检索路径（基础设施主导）

> ✅ **已实现**（foundation/retrieval，Phase 2，2026-08-10 合入 main）。
> 默认优先使用麒麟 embedding；无 SDK 的 Debian 环境使用可移植软件向量器。
> 麒麟性能验收必须启用严格 `PIXIU_EMBEDDING=kylin`。

```
query
  → foundation/api（路由）
  → foundation/retrieval:
      Router → BM25∥ANN∥Graph → Fuse → Rerank → Assembler
  → 返回 MemoryAtom（≤500ms）
```

## 3. 依赖关系

```
engine/             foundation/
  ingest ──→ EvidenceRepository (ABC) ←─── storage/
  preference ──→ PreferenceRepository (ABC) ←─── storage/
  knowledge ──→ KnowledgeRepository (ABC) ←─── storage/
  conflict ──→ ConflictRepository (ABC) ←─── storage/
  security ──→ KnowledgeRepository (ABC) ←─── storage/

foundation/
  api/ ──→ [import] engine/*/Service ←─── engine/（唯一跨模块 import）
```

## 4. 详细设计入口

| 领域 | 详细文档 |
|------|----------|
| 数据模型与 Repository 接口定义 | `foundation/core/models.py`、`foundation/core/repository.py` |
| 引擎业务逻辑 | `engine/docs/ARCHITECTURE.md` |
| API 网关 | `foundation/docs/ARCHITECTURE.md` 第 1.2 节 |
| 存储层 Schema | `foundation/docs/ARCHITECTURE.md` 第 1.3 节 |
| 混合检索 Pipeline | `foundation/docs/ARCHITECTURE.md` 第 1.4 节 |
| P2P CRDT 同步 | `foundation/docs/ARCHITECTURE.md` 第 1.6 节 |
