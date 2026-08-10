# 后端架构总览

> 本文档从后端整体视角阐述系统设计，详细设计分别见 engine/ 和 foundation/ 的子架构文档。
> 这是两端开发者之间的"接口层"文档。
>
> **状态（2026-08-11）**：引擎核心管线已完成并集成；foundation Phase 0~5 全部完成
> （retrieval/flow/sync/eval/D-Bus，12 个 REST 端点真实实现）；全量测试通过
> （麒麟 V11 真机 pytest 364 passed）。剩余：麒麟 SDK 绑定构建与真机性能验收、
> WS `/events` 路由注册修复。

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
来源(Tool/Behavior/Config/OCR)
  → engine/security:detector 敏感预检
  → engine/ingest: Cleaner → Normalizer → Quality
  → 落 evidence（通过 Repository 接口）<50ms → ACK
  → 异步：
    engine/knowledge: Structurer → Graph → EmbedWriter
    engine/preference: Extractor（若含偏好信号）
    engine/conflict: Arbiter（与既有知识比对）
  → foundation/sync: CRDT 广播（✅ Phase 3 已实现，网络运行时默认关闭）
```

### 2.2 检索路径（基础设施主导）

> ✅ **已实现**（foundation/retrieval，Phase 2，2026-08-10 合入 main）。
> 真实检索依赖麒麟 embedding：无 SDK 绑定环境返回 `KylinSDKUnavailableError`。

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
