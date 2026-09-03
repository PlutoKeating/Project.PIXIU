# Ingest P3 Improvement Report

> **范围**：`backend/engine/ingest/` + `backend/engine/tests/test_ingest.py`  
> **日期**：2026-08-19  
> **对照**：`INGEST_AUDIT_REPORT.md`（ING-E1 / ING-E2；ING-E3 评估后保持不动）  
> **约束**：未修改 `backend/foundation/`、schema、Evidence 模型、Repository 契约、Knowledge / Preference / Security

---

## 1. 修复的问题

### ING-E1 实体 alias 写死且只作用顶层字段

- `Normalizer` 支持构造注入：`Normalizer(aliases={...})`。
- 默认词典保留原 5 条（含 `国网` → `国家电网`），注入表与默认表合并，同名键由注入覆盖。
- 归一范围扩展到明确的 identity 字段：`body.items[].vendor`。
- 不扫描任意嵌套字段，不引入 NLP / 外部模型。
- `normalize()` / `ingest()` 对外语义不变。

### ING-E2 `_content_hash` 计算后丢失

- Cleaner 仍写入内部字段 `_content_hash`（哈希材料仍是清洗后、归一前的 title/body/entities/relations）。
- `IngestionService.ingest` 在 strip `_` 前缀字段之前，将指纹提升为 `raw["content_hash"]`。
- 不实现跨 Evidence 查询，不拒绝重复写入。

### ING-E3 Connector 双抽象

- 评估：`connectors/base.py` 的 `BaseConnector` 无引用；四个实现类为 duck type，注册表与运行时正常。
- **本阶段未修改 Connector**（收益仅死代码清理，避免为重构而重构）。

---

## 2. 修改文件

| 文件 | 变更 |
|------|------|
| `backend/engine/ingest/normalizer.py` | 可注入 aliases；`vendor` identity 归一；`normalize_entity` 改为实例方法 |
| `backend/engine/ingest/__init__.py` | persist 前把 `_content_hash` 写入 `content_hash` |
| `backend/engine/tests/test_ingest.py` | Fake EvidenceRepository + 6 项新测试 |
| `backend/engine/docs/INGEST_IMPROVEMENT_REPORT.md` | 本报告 |

未改：`cleaner.py`、`quality.py`、`connectors/*`、foundation 全部。

---

## 3. 新增测试

均不依赖 Knowledge / FTS；新增用例使用内存 Fake `EvidenceRepository`。

| 测试 | 覆盖 |
|------|------|
| `test_normalizer_accepts_injected_alias_without_code_edit` | `{"AAA":"BBB"}` 注入即可生效；默认 `国网` 仍有效 |
| `test_normalizer_alias_applies_to_item_vendor` | `vendor="国网"` → `"国家电网"`，与 entities 一致；`category` 不改 |
| `test_evidence_raw_keeps_content_hash` | ingest 后 `Evidence.raw` 含 64 位 `content_hash` |
| `test_duplicate_payload_still_saves_two_ids` | 相同内容两次 ingest → 两个不同 id（当前语义：不去重） |
| `test_ingest_rejects_non_dict_raw` | `raw` 非 dict → `TypeError` |
| `test_ingest_rejects_empty_scope` | `scope=""` → `ValueError` |

原有 8 项回归测试保留。

---

## 4. 测试结果

```text
PYTHONPATH 仓库根目录
.venv/bin/python -m pytest backend/engine/tests/test_ingest.py -v

14 passed in 0.15s
```

含原有 8 项 + 新增 6 项，全部通过。未跑全量 engine 套件（其中部分失败已知为 FTS5 trigram External Blocker，与本任务无关）。

---

## 5. 未解决问题

### 本阶段刻意不做

| 项 | 说明 |
|----|------|
| ING-E3 | Connector 双抽象 / 闲置 `base.py` |
| ING-E4 | Quality 权重与来源置信度硬编码 |
| ING-E5 | TOOL_RESULT `tool_name` 进入 title 后不再单独保留；ingest 仍由调用方传 sensitivity。2026-09-03：Foundation `/memory/write` 已完成前置 Security 调用 |
| 跨条去重 | 相同 payload 仍生成两个 Evidence id |
| 麒麟 OCR SDK | 当前仍是结构化文本适配器 |
| hash 时机 | 指纹仍在 Cleaner 之后、Normalizer 之前计算；归一后的 vendor 不进入指纹 |

### Foundation 协同事项

后续若要做跨 Evidence 去重或一等指纹字段，需 Module C 协同，**不能只在 ingest 内完成**：

1. **Evidence `content_hash` 字段**  
   当前指纹写在 `Evidence.raw["content_hash"]`。模型在 `foundation/core/models.py`，无一等字段。

2. **Repository 去重查询**  
   `EvidenceRepository` 仅有 `save` / `get` / `list_by_scope`。无 `get_by_hash` / `exists_hash`；`list_by_scope` 有 limit，不能保证全局去重。唯一约束 / 幂等键属仓储语义。

3. **OCR SDK**  
   麒麟 OCR SDK 9.4.1 接入依赖 kylin 绑定与运行环境，不在 ingest P3 范围。

---

## P3 完成标准核对

- [x] alias 从代码逻辑中解耦（可注入，默认表保留）
- [x] 嵌套 identity 字段统一归一（`body.items[].vendor`）
- [x] `content_hash` 不再计算后丢失
- [x] ingest 已有功能无回归（原 8 项通过）
- [x] 新增测试通过
- [x] 未修改 Foundation
