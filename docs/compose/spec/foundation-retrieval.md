---
feature: foundation-retrieval
status: delivered
updated: 2026-08-07
branch: feat/foundation
commits: 748636b..6de438d
---

# Phase 2 — 混合检索管线 (retrieval/)

> 2026-09-06 代码复核：当前 ANN 由 DI 注入 VectorStore：严格画像使用系统 Vector Engine，portable 使用 SQLite INT8；图关联、scope/time_range 硬过滤已实现，重排为词面与年月规则。历史延迟不作为当前 V11 数据。
> 下文实施步骤、旧接口草图和测试数字保留作阶段历史，不作为当前操作手册；当前契约见 docs/API.md，发布见 docs/DELIVERY_PLAN.md。

## Report

**What was built** — 七步混合检索管线全部实现并接通 `/memory/query`：router（规则意图分类 + 实体抽取）→ bm25（FTS5 trigram + 长句滑动窗口回退）∥ ann（INT8 线性扫描，`asyncio.to_thread` 防阻塞）∥ graph（文本子串匹配 + BELONG_TO 加权）→ fuse（RRF + scope 加权）→ rerank（词面重叠微调）→ assembler（items.amount 聚合 + 证据回溯）→ `MemoryAtom`。新增契约 `KnowledgeRepository.list_vectors()`（含 SQLite 实现与 Fake 补全）。FORGOTTEN/SUPERSEDED 不参与检索。

**Verification** — 全量 243 项测试通过（foundation 222 + engine 21；新增 14 项 retrieval 测试）。延迟粗测（50 条家庭支出知识 + 1000 次 query）：**P50=11.4ms，P95=13.3ms**，远低于 500ms 硬指标。

**Journey log**
- **trigram 长句陷阱**：FTS5 对长查询串按 AND 语义匹配全部 trigram，整句查询必然 0 命中（"家庭支出清单花了多少钱" 命中 0、短词命中 1）。解决：BM25 通道滑动窗口回退（4 字窗口步长 2）。
- **knowledge↔entity 关联缺口**：schema 无关联表，`KnowledgeItem.entities` 读回为空。graph 通道改用文本子串匹配 + BELONG_TO 加权（诚实方案），建议团队后续补关联表。
- **rerank 中文分词**：CJK 连续匹配会把整句当一个 token 导致词面重叠恒为 0，改按字分词。
- 队友的 `test_unimplemented_endpoints_keep_placeholder` 断言 `/memory/query` 仍为占位——随本次实现移除该断言（其余占位端点断言保留）。

## [S1] Problem

`/memory/query` 仍返回 `not_implemented`（`api/http_app.py:110`）。赛题硬指标：检索响应 P95 ≤ 500ms、召回率 ≥85%、在线零 LLM。需实现七步混合检索管线：router → bm25 → ann → graph_search → fuse → rerank → assembler，产出 `MemoryAtom`。

## [S2] Design

### S2.1 总体结构

```
retrieval/
├── __init__.py        # 导出 RetrievalService
├── router.py          # 意图分类 + 实体抽取 + 通道选择
├── bm25.py            # FTS5 全文检索通道
├── ann.py             # 向量近邻通道（INT8 余弦）
├── graph_search.py    # 实体关系图遍历通道
├── fuse.py            # RRF 融合 + context_hint 加权
├── rerank.py          # 轻量重排（非 LLM）
└── assembler.py       # 结构化过滤 + 聚合计算 + evidence 回溯
```

**RetrievalService 注入**（与 `api/di.py` 模式一致）：
```python
class RetrievalService:
    def __init__(self, knw_repo, entity_repo, evidence_repo, embedder):
        ...
    async def query(self, text: str, context_hint: dict | None = None) -> MemoryAtom
```

### S2.2 router.py — 意图分类 + 通道选择

- **无 LLM**：基于关键词规则的意图分类
  - `FACT_RETRIEVAL`（默认，含金额/时间词）
  - `WORKFLOW_LOOKUP`（含"步骤/流程/怎么"）
  - `TEMPLATE_LOOKUP`（含"模板/格式"）
- 实体抽取：与 `entities.norm_name` 匹配查询词中的已知实体（调 `EntityRepository.find_entity_by_name` 不适用全文场景，改为**加载实体名集合做子串匹配**——实体数少，内存加载可接受）
- 通道选择：FACT 三通道全开；WORKFLOW/TEMPLATE 优先 BM25

### S2.3 bm25.py — FTS5 全文通道

直接调用已实现的 `KnowledgeRepository.search_fts(query, limit)`。
- 结果转换为 `(knowledge_id, score)` 候选集，score 用 FTS rank 归一化。
- **状态过滤**：`list_active` 语义——`search_fts` 存储层不过滤，本通道按 `KnowledgeItem.status == ACTIVE` 过滤（遗忘/被取代知识不出现在检索结果，与 engine 语义对齐；此决策已在上一轮报告中标注待确认，此处采用"仅 ACTIVE 参与检索"）。

### S2.4 ann.py — 向量近邻通道

- **实现**：纯 Python 线性扫描（无新依赖）。`embedder.embed(text)`（同步 → `asyncio.to_thread`）→ INT8 量化 → 与 `knowledge_vec` 全部条目算余弦相似度 → Top-K。
- 数据加载：新增轻量 `load_all_vectors() -> list[(knw_id, dim, vec)]`（在 retrieval 模块内直接查询 `knowledge_vec`，或经 `KnowledgeRepository` 扩展——**选择在 ann.py 内通过注入的 db 访问？否**，遵守仓储边界：给 `KnowledgeRepository` 加 `list_vectors()` 方法（改 core/repository.py + storage/repository.py）。
- **为什么线性扫描**：评测集 50 组清单、端侧数据量小（<1 万条向量 × 768 维 ≈ 7.7M 浮点乘加，纯 Python ~50ms）；hnswlib 需编译/依赖，麒麟端不可靠。封装 `VectorIndex` 抽象，后续数据量大再替换。
- **性能兜底**：`asyncio.to_thread` 跑 embed 和扫描，不阻塞事件循环。

### S2.5 graph_search.py — 实体关系图通道

- `EntityRepository.list_relations()` 全量关系（关系少）→ 邻接表内存构建。
- 命中实体（router 抽出的）→ 沿 `BELONG_TO` 边找关联实体 → 查 `knowledge_items`（按 id，用 `list_active` 过滤）→ 命中知识的 `entities` 字段交集计分。

### S2.6 fuse.py — RRF 融合

- RRF：`score = Σ 1/(60 + rank_i)`，三通道合并。
- `context_hint.scope` 加权：候选 scope 命中 `shared:home` → ×1.5；`time_range` 无字段可过滤（body 内日期需解析，第一版忽略，仅 top_k 生效）。
- 输出 `list[(KnowledgeItem, fused_score)]` Top-K。

### S2.7 rerank.py — 轻量重排（非 LLM）

- 赛题"在线零 LLM"：不做 INT8 reranker 神经网络。
- 用标题/正文与 query 的**词面重叠率**微调融合分数（`overlap = |tokens(q) ∩ tokens(title+desc)|`），同分时优先 higher overlap。
- 明确文档标注：真实 INT8 reranker 留作后续增强（不阻塞 500ms 目标）。

### S2.8 assembler.py — 组装 MemoryAtom

- 取 top-1 知识 → `evidence_ids` 回溯（`EvidenceRepository.get` 逐条，数据量小）→ `source_evidence`。
- **聚合计算**：识别 body 中 `items[].amount` 列表（家庭支出场景），query 含金额/花费意图时求和，生成 `answer` 模板：
  `"2026年4月，你们在水电燃气方面共支出 434.50 元..."` —— 无聚合数据时 answer 用知识 title。
- `confidence` = fused_score 归一化到 0~1；`latency_ms` 计时。

### S2.9 接线

- `api/http_app.py`：`/memory/query` 接 `RetrievalService`（新 `get_retrieval_service` DI 工厂，注入 knw/entity/evidence repo + `get_embedder()`）。
- 请求模型 `MemoryQueryRequest{text, context_hint}`，响应按 `docs/API.md` §3.2 的 MemoryAtom JSON。

### S2.10 测试（tests/test_retrieval.py）

遵循 engine 测试模式：真实 SQLite + `StubTextEmbedder`（从 `engine/tests/fakes.py` 复用或本目录复制，保持 tests 独立）。

用例：
1. BM25 中文检索通道（"家庭支出" 命中）
2. ANN 通道（语义相近文本命中）
3. Graph 通道（BELONG_TO 关系命中）
4. RRF 融合排序正确
5. rerank 词面重叠加分
6. assembler 聚合（3 条 items amount 求和）
7. FORGOTTEN 状态不参与检索
8. `RetrievalService.query` 端到端返回 MemoryAtom 且 `latency_ms >= 0`
9. context_hint.scope 加权生效
10. `/memory/query` API 端点（TestClient）返回 200 与正确结构

## [S3] Out of Scope

- 真实 INT8 reranker 神经网络（在线零 LLM 约束；轻量词面重排替代）
- hnswlib/sqlite-vec ANN 索引（数据量小，线性扫描足够；预留 `VectorIndex` 抽象）
- time_range 时间过滤（body 内日期解析留待评测阶段）
- D-Bus 服务
- 检索日志链路（request_id 已由 logger 支持，检索内部不新增）

## Tasks

- [x] T1: core/repository.py + storage/repository.py — `KnowledgeRepository.list_vectors()` 契约与 SQLite 实现 (covers: S2.4)
- [x] T2: retrieval/router.py — 意图分类 + 实体抽取 + 通道选择 (covers: S2.2)
- [x] T3: retrieval/bm25.py — FTS5 通道 + ACTIVE 过滤 (covers: S2.3)
- [x] T4: retrieval/ann.py — INT8 线性扫描通道 (covers: S2.4)
- [x] T5: retrieval/graph_search.py — 关系图遍历通道 (covers: S2.5)
- [x] T6: retrieval/fuse.py — RRF + scope 加权 (covers: S2.6)
- [x] T7: retrieval/rerank.py — 词面重叠重排 (covers: S2.7)
- [x] T8: retrieval/assembler.py — 聚合 + MemoryAtom 组装 (covers: S2.8)
- [x] T9: retrieval/__init__.py — RetrievalService (covers: S2.1; depends: T2-T8)
- [x] T10: api/di.py + api/http_app.py — DI 工厂 + /memory/query 接线 (covers: S2.9; depends: T9)
- [x] T11: tests/test_retrieval.py — 10 组测试 (covers: S2.10; depends: T9, T10)
- [x] T12: 全量测试 + 延迟粗测（1000 次 query P95） (covers: S2.1-S2.9; depends: T11)
