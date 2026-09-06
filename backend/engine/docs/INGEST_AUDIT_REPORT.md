# Ingest P3 Audit Report

> 2026-09-06 复核：本文保留原日期对应的测试/审计快照，不将历史数量、环境或待办状态当作当前结论。现行 API 为 32 个 REST 端点、六类 WS 事件，schema v12；2026-09-06 CI（`fd1a6d7`）在 Python 3.12/3.13 各通过 823 项测试。默认 auto 可降级至 portable，严格 V11 则必须使用双 SDK。原生产品链、完整 Agent 场景和三物理设备验收分别取证，最新发布规则见 `docs/DELIVERY_PLAN.md`。

> **范围**：`backend/engine/ingest/`（只读）  
> **日期**：2026-08-19  
> **约束**：未修改 ingest / foundation / schema / 测试代码；本文件仅为审计产出  
> **对照**：`docs/ARCHITECTURE.md`、`docs/API.md`、`docs/AcceptanceTestSpecification.md`（F1-01~07、SC-07）、`backend/engine/docs/ARCHITECTURE.md`、`ENGINE_AUDIT_REPORT.md`、`foundation/core/models.py`、`foundation/core/repository.py`
>
> **后续状态说明（2026-09-03）**：本文是 2026-08-19 代码快照。麒麟 OCR、
> `CONVERSATION` Connector、evidence provenance 与 Foundation 完成态持久化幂等已在
> 后续实现；专用语义策略仍待完成。2026-09-03 已由 Foundation 写入入口
> 接通敏感检测及隔离策略，Module E 生命周期亦已实现。下文历史
> 状态只作审计快照，不是当前结论。

---

# 1. 当前模块架构

Ingest 是 Memory 写入最前端。统一入口 `IngestionService.ingest(source_type, raw, scope, sensitivity=0)`。

```
外部 raw dict + source_type + scope [+ optional sensitivity]
        │
        ▼
get_connector(source_type)          connectors/__init__.py 注册表
        │  统一中间形态：title / body / entities / relations
        ▼
Cleaner.clean                       去空、列表内去重、缺省字段、计算 _content_hash
        │
        ▼
Normalizer.normalize                形状整理 + 实体别名（仅 entities/relations）
        │
        ▼
Quality.score                       Schema 最低校验 + quality_score ∈ [0,1]
        │
        ▼
strip keys starting with "_"        _content_hash 在此丢弃
        │
        ▼
Evidence(id, source_type, raw, quality_score, sensitivity, scope, created_at)
        │
        ▼
EvidenceRepository.save             foundation 契约；ingest 不负责事务
```

下游只消费落库后的 `Evidence`：

| 下游 | 主要读取 |
|------|----------|
| Knowledge `Structurer` | `evidence.raw`（title/body/entities/relations） |
| Preference `Extractor` | `source_type`、`raw`、`scope`、`sensitivity` |
| Conflict | 不直接读 Evidence；读 Knowledge（间接受 ingest 的 entities/vendor） |
| Security detector | **不在 ingest 内调用**；`sensitivity` 由调用方传入，默认 0 |

ingest **不负责**：Preference、Knowledge 结构化、Conflict、Repository 事务。

---

# 2. 已实现功能

对照 F1 / I-01~I-07（I-08 OCR SDK 文档已标待实现，不算本阶段违约）。

| 项 | 状态 | 证据 |
|----|------|------|
| 四源接入 TOOL_RESULT / USER_BEHAVIOR / MANUAL_CONFIG / OCR | 已实现 | 四个 Connector + `get_connector` |
| 统一入口 `IngestionService` | 已实现 | `ingest/__init__.py` |
| Connector → Cleaner → Normalizer → Quality → Evidence | 已实现 | `ingest()` 顺序固定 |
| 清洗：空值删除、同条 payload 内列表去重、缺省 title/body/entities/relations | 已实现 | `cleaner.py` |
| 内容 hash 指纹计算 | 部分 | `Cleaner.content_hash` 有；见问题 5 |
| 格式标准化（title strip、body dict、relation type 大写） | 已实现 | `normalizer.py` |
| 实体别名规范化 | 部分 | 硬编码 5 条样例 alias |
| quality_score + 最低 schema | 已实现 | `quality.py`；空 title 不拒绝 |
| OCR 实体预提取 + vendor→category BELONG_TO | 已实现 | `connectors/ocr.py` |
| 麒麟 OCR SDK 9.4.1 | 未实现 | 文档 ⬜ 待接入；当前是结构化文本适配器 |
| 测试 | 8 项 ingest 测试，不依赖 FTS trigram | `test_ingest.py` |

相对 `ENGINE_AUDIT_REPORT.md` 中 ingest 成熟度 **A（管线基本达标）**：本轮复读代码后结论一致，但 P3 要单独把「别名词典」「Connector 双抽象」「hash 落库失败」「嵌套字段未归一」写清楚。

---

# 3. Engine-owned问题

下列均可在 `backend/engine/ingest/` 内处理，**不必改 foundation**。

## ING-E1 实体 alias 写死在源码，且只作用于顶层 lists

**位置**：`normalizer.py` 模块级 `_ENTITY_ALIASES`（国网→国家电网、新奥→新奥燃气等 5 条）；`normalize()` 只改 `entities` 与 `relations` 的 from/to。

**事实**：

1. 新增实体别名必须改 Python 常量。
2. 规则（strip、relation type 大写）和词典写在同一个类里，但词典本身没有独立注入点。
3. OCR `body.items[].vendor` **不会**走 alias。例如 vendor=`国网` 会被抽进 `entities` 后归一成 `国家电网`，但 `body` 里仍是 `国网`。Conflict/Graph 若用 vendor 做 identity，会与 `entities` 不一致。

**轻量改法（engine）**：`Normalizer(aliases=None)` 可注入 dict；默认仍内置当前表；可选从 `ingest/` 内一份静态映射文件加载。递归归一 `vendor` / `entity` 等 identity 字段。不要上 NLP。

## ING-E2 `_content_hash` 算完即删，Evidence 上没有指纹

**位置**：`cleaner.py` 写入 `data["_content_hash"]`；`IngestionService.ingest` 持久化前丢掉所有 `_` 前缀字段。

**事实**：`test_cleaner_drops_noise` 只断言 Cleaner 输出带 hash；落库 `Evidence.raw` 无 hash。跨条去重即使用 `list_by_scope` 也比不了指纹。

**Engine 可做**：把指纹写入非 `_` 字段（例如 `raw["content_hash"]`），不改 schema / Evidence 模型。跨条查询策略见第 4 节。

## ING-E3 Connector 双抽象，具体类未继承任一侧

**位置**：

- `connectors/__init__.py`：`class Connector(ABC)` + `get_connector` + `_REGISTRY`
- `connectors/base.py`：`class BaseConnector(ABC)`，**无引用**
- 四个实现类均为独立 duck type，不 `inherit` 上述 ABC

**判断**：运行时可用，不是功能 bug。P3 若动刀：删掉闲置 `base.py`，让四个类继承 `Connector`。不要为重构而拆注册表。

## ING-E4 Quality 权重与来源置信度硬编码

**位置**：`quality.py` `_SOURCE_CONFIDENCE`；completeness 固定 0.35/0.35/0.15/0.15；`0.7 * completeness + 0.3 * source_conf`。

**事实**：可解释（字段有无 + 来源先验），但扩展要改代码。`validate` 只要求存在 `title` 键和 dict `body`；空 title、空 body 仍给分不抛错（与 `ENGINE_AUDIT_REPORT` 一致）。

## ING-E5 部分源字段在统一 payload 中丢失

**TOOL_RESULT**：`tool_name` 用作 title 后，不再进入 `body`。Preference 若在 `Evidence.raw` 上找 `tool_name`，只能靠 title。  
**OCR**：`vendor` 原文留在 items，与归一后的 entities 可能不一致（同 ING-E1）。  
**sensitivity**：ingest 接受 kwargs，默认 0，且自身**不调用**
`SecurityService.detect_sensitivity`。2026-09-03 起 `/memory/write` 调用方已在写入前检测
并显式传入该值；保持这一依赖方向，不把 SecurityService 反向耦合进 ingest。

## ING-E6 测试未覆盖跨条去重、异常类型、Quality 边界

见第 6 节。属 engine 测试缺口。

---

# 4. Foundation依赖问题

**禁止在 P3 改这些来“修 ingest”。**

| 问题 | 为何不是 ingest 可单独完成 |
|------|------------------------------|
| `Evidence` 无 `content_hash` 一等字段 | 模型在 `core/models.py` |
| `EvidenceRepository` 无 `get_by_hash` / `exists_hash` | ABC 只有 `save` / `get` / `list_by_scope` |
| 用 `list_by_scope(scope, limit)` 扫重复 | 有 limit，不能保证全局去重；且当前 raw 里没有可比较的 hash |
| `Evidence.sensitivity` 允许 0~10，ingest 夹紧 0~3 | 契约与架构 0~3 不完全一致；改模型属 C |
| 跨 Evidence 去重策略（拒绝 / 合并 / 仍保存） | 产品 + 仓储语义；save 契约没有幂等键 |
| 麒麟 OCR SDK | kylin 绑定 + 环境，DEV_TASKS 已标待实现 |
| HTTP `/memory/write` 是否先 detect 再 ingest | `foundation/api/http_app.py` 组装，不是 ingest 包 |

**跨条 content_hash 去重**：指纹计算与写入 `raw` 是 **engine**；按 hash 查询/唯一约束是 **Foundation**。P3 不要新增 repository 方法。

---

# 5. 修改建议

无 **P0**（ingest 可运行；`test_ingest.py` 不依赖 FTS trigram）。

## P1（建议本阶段 engine 做）

1. **Normalizer 词典与逻辑分离**  
   可注入 aliases；默认保留现有 5 条以免验收样例回退。新增实体不必先改 `normalize()` 控制流。

2. **别名应用到嵌套 identity 字段**  
   至少 `body.items[].vendor`（以及与 entities 同源的名称），避免 `entities=国家电网` 而 `vendor=国网`。

3. **指纹保留在 Evidence.raw**  
   停止只靠 `_content_hash` 再 strip。例如持久化 `content_hash`。  
   **不要**在未约定时拒绝重复写入（会改变现有「每次 ingest 新 id」行为）。跨条拒绝/合并等 Foundation。

## P2（可延期）

4. 删除或合并闲置 `connectors/base.py`，实现类继承 `Connector`。  
5. Quality 权重/来源表可注入，与 `score()` 循环分离；空 title 是否视为校验失败需产品确认。  
6. TOOL_RESULT 把 `tool_name` 写入 body 或保留顶层非 `_` 字段，方便 Preference。  
7. `sensitivity=0` 与 detector 的衔接：在 ingest 内调用 vs 由 API 传入——需负责人裁定，**不要擅自绑 SecurityService**（跨子包耦合）。

## 明确不做（本阶段）

- 改 EvidenceRepository / schema  
- 上 NLP / 新依赖  
- 整包重写 Connector  
- 实现麒麟 OCR SDK  
- 为测过去改 foundation

---

# 6. 测试建议

现有 `test_ingest.py`：

| 场景 | 有无 |
|------|------|
| USER_BEHAVIOR | 有（含同条 events 去重） |
| TOOL_RESULT | 有（title/body.hits） |
| MANUAL_CONFIG | 有 |
| OCR + alias + BELONG_TO | 有 |
| 未知 source_type | 有 |
| Cleaner 噪声 / 列表去重 / `_content_hash` 在 **clean 输出** | 有 |
| Normalizer 国网 alias | 有 |
| Quality 缺 body 抛错 | 有 |
| **两次 ingest 相同内容是否两套 Evidence id** | **无** |
| **落库 raw 是否仍有 content_hash** | **无** |
| **vendor 与 entities 别名一致** | **无** |
| Quality 空 title 仍打分 / 分数公式 | **无** |
| `raw` 非 dict / 空 scope | **无**（代码有 TypeError/ValueError） |
| Connector 基类闲置 | 不必为重构单测 |

建议新增（Fake `EvidenceRepository` 即可，不必 Knowledge/FTS）：

1. `test_normalizer_alias_applies_to_item_vendor`（P1 实现后）  
2. `test_normalizer_accepts_injected_alias_without_code_edit`  
3. `test_evidence_raw_keeps_content_hash`（若决定持久化指纹）  
4. `test_duplicate_payload_still_saves_two_ids`（记录当前语义，直到 Foundation 去重）  
5. `test_quality_empty_title_does_not_raise` 或改为拒绝（与产品一致）  
6. `test_ingest_rejects_non_dict_raw` / `test_ingest_rejects_empty_scope`  
7. `test_tool_result_preserves_tool_name`（若 P2 保留该字段）

---

## 本阶段结论

Ingest 管线完整，四源与 F1 主路径可用，**不阻塞运行**。  
P3 应聚焦 engine 内：**别名可配置 + 嵌套字段归一 + hash 不要算完就扔**。  
**跨 Evidence 去重查询**标为 Foundation 协同，本阶段不改契约。

等待人工确认后再改代码。
