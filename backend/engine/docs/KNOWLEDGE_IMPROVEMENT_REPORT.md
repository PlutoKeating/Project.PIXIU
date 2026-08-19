# Knowledge P4 Improvement Report

> **范围**：`backend/engine/knowledge/` + `backend/engine/tests/test_knowledge.py`  
> **日期**：2026-08-19  
> **对照**：Knowledge P4 Audit（KN-E1 / KN-E2 / KN-E4 / KN-E6）  
> **约束**：未修改 `backend/foundation/`、schema、Repository 契约、Conflict、Preference、Ingest 源码

---

## 1. 修改目标

| ID | 目标 | 本阶段处理 |
|----|------|------------|
| KN-E1 | 四类 Knowledge 轻量结构化（规则表 + 优先级 + 最小校验） | 已做 |
| KN-E2 | `body.items[].vendor` 并入 entities，别名去重 | 已做 |
| KN-E4 | graph 成功但 save 失败时明确失败位置 | 已做（日志 + 再抛出，无事务/补偿） |
| KN-E6 | Fake 仓储单测覆盖 CASE/TEMPLATE/Graph/空输入/重复 | 已做 |

未宣称模块完成。未做 NLP、未改 Foundation、Knowledge 不 import Conflict。

---

## 2. 修改文件

| 文件 | 变更 |
|------|------|
| `backend/engine/knowledge/structurer.py` | `KIND_RULES`；显式 kind 优先；结构字段优先于 OCR+items；最小结构校验；vendor identity 同步 |
| `backend/engine/knowledge/graph.py` | 跳过空实体名；relation type `strip().upper()`，空则 `BELONG_TO` |
| `backend/engine/knowledge/__init__.py` | `structure` 分步 `step=` 日志，失败再抛出 |
| `backend/engine/tests/test_knowledge.py` | Fake repo 单测 |
| `backend/engine/docs/KNOWLEDGE_IMPROVEMENT_REPORT.md` | 本报告 |

未改：`embed_writer.py`、foundation、conflict、preference、ingest 文件。Identity 别名复用 `ingest.normalizer.Normalizer`（只读导入，未改 ingest）。

---

## 3. 关键改进

### kind 规则化（KN-E1）

优先级：

1. 显式 `raw.kind` / `body.kind` ∈ {FACT, WORKFLOW, CASE, TEMPLATE}
2. `KIND_RULES` 中 `source_type is None` 的结构字段：`steps`/`workflow` → WORKFLOW，`case` → CASE，`template` → TEMPLATE
3. 来源默认：OCR + `items` → FACT
4. 否则 FACT

OCR 同时有 `items` 与 `steps` 时为 WORKFLOW（`test_workflow_priority_over_items`）。

最小校验（不改 KnowledgeItem 模型、不抛新异常）：

- WORKFLOW：`steps` 为 list，或存在 `workflow`
- TEMPLATE：存在 `template`
- CASE：存在 `case`

推断不满足则 **降级 FACT** 并 warning。显式 kind 不满足则 **保留该 kind** 并 warning。

四类仍共享同一 `KnowledgeItem` 形状（拷贝 body）；增强的是 kind 判定与校验，不是分型 schema。

### identity 同步（KN-E2）

- 只处理 `body.items[].vendor`
- 写入 KnowledgeItem 前用 ingest 默认 alias 归一（`国网` → `国家电网`）
- 并入 `entities` 后去重
- 已有 `国家电网` 再出现 `国网` 只保留一个实体名

不做全文抽取。

### graph 增强（KN-E2 小幅）

- 仍主要消费已有 relations，未重写 Graph
- 空名称跳过
- type 规范化为大写，缺省 `BELONG_TO`
- 同名 `find_entity_by_name` 复用（原逻辑 + 单测）

### failure handling（KN-E4）

步骤标记：`graph` → `embed` → `knowledge_save` → `vector_save`。  
失败 `logging.warning(..., step=...)` 后 **raise**。不吞异常，不补偿删除，不新增 repository。

---

## 4. 测试结果

命令：`.venv/bin/python -m pytest backend/engine/tests/test_knowledge.py -v`

| 测试 | 结果 | 说明 |
|------|------|------|
| `test_structure_ocr_to_fact` | FAILED | SQLite FTS trigram（Foundation/环境） |
| `test_structure_workflow_kind` | FAILED | 同上 |
| `test_stub_embedder_deterministic` | PASSED | |
| `test_explicit_kind_overrides_heuristics` | PASSED | |
| `test_workflow_priority_over_items` | PASSED | |
| `test_infer_kind_template_from_template_field` | PASSED | |
| `test_infer_kind_case_from_case_field` | PASSED | |
| `test_structure_ocr_items_is_fact_without_sqlite` | PASSED | Fake 覆盖原 FACT 路径 |
| `test_structure_steps_is_workflow_without_sqlite` | PASSED | Fake 覆盖原 WORKFLOW 路径 |
| `test_workflow_invalid_steps_falls_back_to_fact` | PASSED | |
| `test_vendor_identity_matches_entities` | PASSED | vendor=国网 → 实体国家电网 |
| `test_vendor_alias_does_not_create_duplicate_entity` | PASSED | |
| `test_graph_reuses_entity_by_name` | PASSED | |
| `test_graph_skips_empty_entity_names` | PASSED | |
| `test_graph_normalizes_relation_type` | PASSED | |
| `test_structure_empty_evidence_defaults_to_fact` | PASSED | untitled + FACT |
| `test_structure_same_evidence_twice_two_ids` | PASSED | 不去重 |
| `test_structure_logs_knowledge_save_failure` | PASSED | `step=knowledge_save` |

Engine 全量：`pytest backend/engine/tests` → **51 passed, 6 failed**。

6 个失败均为 `sqlite3.OperationalError: no such tokenizer: trigram`：

- `test_knowledge.py` 2（sqlite 集成）
- `test_conflict.py` 2
- `test_security.py::test_forget_pending_then_confirm` 1
- `test_sqlite_integration.py::test_full_write_pipeline_on_sqlite` 1

**不是本次 Knowledge 逻辑回归**；与 ENGINE_AUDIT External Blocker 一致。禁止为全绿改 Foundation。

排除上述 2 个 sqlite 用例后 knowledge：**16 passed**。

---

## 5. 未解决问题

### Engine 仍可后续做

- KN-E3：实体 type 关键词 hard-code（`_guess_type`）未改
- Graph 仍不从 items 推理 BELONG_TO（推理仍在 Ingest OCR）
- 同一 Evidence 两次 structure 仍两个 id（已用测试固定，未做幂等）
- 四类仍无独立 body schema，只有 kind + 最小字段校验

### Foundation / 跨模块依赖问题

- **跨仓储事务**：`save_entity` / `save` / `save_vector` 各自 commit；engine 无补偿
- **FTS5 trigram**：本机 `.venv` SQLite 无 tokenizer，sqlite 集成测失败
- **retrieval**：WORKFLOW/CASE/TEMPLATE 的「调用/检索」不在 Knowledge
- **`get()` 不还原 relations / embedding_ref**：图在 `relations` 表
- **OCR SDK / 真 embedding 服务**：环境 + kylin

不要声称 Knowledge 模块已完成。P4 只完成审计范围内的 engine 有限优化。
