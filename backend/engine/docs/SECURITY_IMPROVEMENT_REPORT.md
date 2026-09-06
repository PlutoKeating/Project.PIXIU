# Security P5 Improvement Report

> **范围**：`backend/engine/security/` + `backend/engine/tests/test_security.py`（及 `test_sqlite_integration.py` 中 forget 调用签名）  
> **日期**：2026-08-19  
> **对照**：Security P5 Audit（SEC-E1/E2/E4/E6，FORGET-E1~E4）  
> **约束**：未修改 `backend/foundation/`、schema、Repository 契约、API、sync、tombstone、ingest、conflict

---

## 1. 修改目标

| ID | 目标 | 本阶段 |
|----|------|--------|
| FORGET-E1 | scope 隔离，禁止全库搜索 | 已做（`scope` 必填，空 scope 抛错） |
| FORGET-E2/E3 | 轻量 score、title 权重 > body、排序 | 已做 |
| FORGET-E4 | token 归一化、月份/停用词 | 已做 |
| FORGET-E7 语义 | cascade 仅为 preview | 已做（`cascade_preview` + 注释） |
| SEC-E1 | 身份证 checksum + 日期 | 已做 |
| SEC-E2 | 中文数字边界 | 已做（显式 `(?<![0-9Xx])` 边界） |
| SEC-E4/E5 | 银行卡 Luhn | 已做 |
| SEC-E6 | 结构化 DetectionResult | 已做（保留 `detect_sensitivity`） |

---

## 2. 修改文件

| 文件 | 变更 |
|------|------|
| `backend/engine/security/detector.py` | 校验型检测 + `DetectionResult` / `detect_detail` |
| `backend/engine/security/id_card.py` | **新增** GB11643 checksum + 出生日期 |
| `backend/engine/security/luhn.py` | **新增** Luhn 校验 |
| `backend/engine/security/forget.py` | scope、score 排序、token 归一、preview cascade |
| `backend/engine/security/models.py` | `cascade_preview`；`DetectionResult` 导出 |
| `backend/engine/security/__init__.py` | `detect()` 结构化接口；`forget(..., scope)` |
| `backend/engine/tests/test_security.py` | Fake 仓储 18 项单测 |
| `backend/engine/tests/test_sqlite_integration.py` | forget 调用补 `scope`（签名对齐） |
| `backend/engine/docs/SECURITY_IMPROVEMENT_REPORT.md` | 本报告 |

---

## 3. Detector 改进

### 身份证

- 候选：`(?<![0-9Xx])(\d{17}[\dXx])(?![0-9Xx])`
- 通过 **出生日期合法** + **GB11643 校验位** 才计为 `id_card`
- `123456789012345678` 不再误报

### 边界

- 弃用 `\b`；贴汉字如 `身份证号{ID}` 可检测

### 银行卡

- 16/19 位候选 + **Luhn** 通过才计为 `bank_card`
- 普通 16 位订单号（Luhn 失败）不误报

### 多命中结构化

```python
DetectionResult(score=3, types=["id_card", "phone"])
```

- `SecurityService.detect_sensitivity(raw)` **保持不变**（返回 int）
- 新增 `SecurityService.detect(raw) -> DetectionResult`
- `Detector.find_matches()` 仍返回中文标签列表（兼容）

### sensitivity 语义

- Engine 仍使用 **0~3**（身份证/银行卡=3，手机=2）
- Foundation `Evidence.sensitivity` 允许 0~10；Detector 输出仍为 0~3。2026-09-03
  Foundation/API 已完成写入前置检测与策略执行，ingest 继续只接收显式评分。

---

## 4. Forget 改进

### scope 隔离（P0）

```python
await security.forget(command, confirm=False, scope="user:alice")
```

- 仅 `item.scope == scope` 参与匹配
- `scope=""` → `ValueError`
- **不再**默认搜索全库

### score 排序

权重表 `_SCORE_WEIGHTS`：

| 项 | 分 |
|----|-----|
| title token 命中 | 3 |
| body token 命中 | 1 |
| title 完全包含于 command | 10 |

- 最低分 `_MIN_MATCH_SCORE = 3` 才入选
- targets 按 score 降序；含 `score`、`confidence`

### token 归一化

- 停用词表：请/帮我/清除/记录/一下 等
- 月份：`四月份` → `四月`；匹配时 `四月` ↔ `4月` 变体
- CJK 子切分（月份/双字词）；按「的」分句

### cascade 语义

- 字段 **`cascade_preview`**：`evidence_count` / `relation_count` 仅为 **确认前预览**
- 兼容别名 **`cascade`**（同值，文档标明非物理删除）
- confirm 后 **仅** `KnowledgeRepository.update_status(FORGOTTEN)`
- `forgotten_ids` 可含 evidence id，但 **Engine 不删除 Evidence**

---

## 5. 测试结果

命令：`.venv/bin/python -m pytest backend/engine/tests/test_security.py -v`

| 测试 | 结果 |
|------|------|
| test_detect_id_card_high | PASSED |
| test_detector_valid_id | PASSED |
| test_detector_invalid_id_checksum | PASSED |
| test_detector_id_adjacent_cjk_boundary | PASSED |
| test_detect_phone_mid | PASSED |
| test_detector_bank_card_false_positive_order_number | PASSED |
| test_detector_multiple_hits | PASSED |
| test_detect_clean | PASSED |
| test_forget_respects_scope_isolation | PASSED |
| test_forget_rejects_empty_scope | PASSED |
| test_forget_multiple_candidates_sorted | PASSED |
| test_forget_title_match_higher_than_body | PASSED |
| test_forget_month_normalization | PASSED |
| test_forget_no_match_returns_empty_targets | PASSED |
| test_forget_pending_then_confirm_only_updates_knowledge | PASSED |
| test_forget_does_not_claim_delete_evidence | PASSED |
| test_forget_repeat_confirm_returns_no_active_targets | PASSED |
| test_legacy_find_matches_labels | PASSED |

**18 passed**（Fake 仓储，无 SQLite FTS）

Engine 全量：`pytest backend/engine/tests` → **68 passed, 5 failed**

失败均为 **Foundation/环境既有问题**（非本次 Security 逻辑回归）：

| 失败用例 | 原因 |
|----------|------|
| test_conflict.py ×2 | SQLite FTS trigram |
| test_knowledge.py ×2 | SQLite FTS trigram |
| test_sqlite_integration.py | SQLite FTS trigram（forget 签名已对齐 scope） |

Foundation/API 侧 `forget` 仍调用旧签名（无 scope）——属 **Module C 依赖**，本阶段未改。

---

## 6. 未解决问题

### Engine 仍可后续做

- 更细粒度分词 / source_type 过滤（赛题附录 title+OCR）
- 歧义指令（「刚才那个」）与对话上下文
- sensitivity≥2 写入时脱敏/阻断（需调用方配合）

### Foundation / Module C dependency

| 项 | 说明 |
|----|------|
| Evidence 物理删除 | Repository 无 delete |
| Entity / Relation 删除 | 无级联 delete API |
| Vector / FTS 删除 | 不在 Engine |
| tombstone / Sync | `http_app` 在 shared forget 后调 sync；Engine 不实现 |
| API `POST /forget` | 需增加 **scope** 并传入 `SecurityService.forget` |
| API `POST /memory/write` | 2026-09-03 已调用 `detect_sensitivity`；用户域标敏隔离，共享域敏感写入拒绝，检测故障 fail closed |
| FTS trigram 环境 | 阻塞部分 sqlite 集成测 |

**不要把「目标识别 + Knowledge 软删」描述为「彻底遗忘」。**

---

## 7. Security 当前状态

2026-09-06 对照当前实现补充：本报告前六节保留 2026-08-19 阶段记录。
当前 `SecurityService.forget(..., scope=None)` 的 scope 已改为可选；显式传空串
仍拒绝，省略时匹配当前数据库全部 ACTIVE 条目。公共 `/forget` 不传 scope，
所以不能继续宣称该 HTTP 入口强制作用域隔离。确认后标记 FORGOTTEN，并调用
注入的 VectorStore 删除向量；evidence、实体/关系和 FTS 原始载荷没有物理级联删除。
共享条目由 Foundation 记录删除操作及墓碑。API 写入前敏感检测已完成。

### Detector（Engine 可交付）

- 身份证：regex + 日期 + checksum
- 手机：显式数字边界 11 位
- 银行卡：16/19 位 + Luhn
- 多类型结构化 `DetectionResult`；legacy int API 保留

### Forget（Engine 可交付 — 目标识别层）

- **显式 scope 过滤**；省略 scope 时搜索当前用户服务数据库中的全部 ACTIVE 条目
- score 排序 + title/body 权重 + token 归一
- pending / confirm 两段式
- confirm 后 **Knowledge FORGOTTEN + VectorStore 删除**，不物理删除原始证据/关系
- cascade_preview 仅为关联数量**预估**

### 模块职责（明确）

| Engine 负责 | Engine 不负责 |
|-------------|---------------|
| 敏感检测与评分 | Evidence/Entity/Relation 物理删除 |
| 解析忘记命令、排序候选 | Vector / FTS 清理 |
| Knowledge 软删除 | tombstone / Sync 传播 |
| 返回 preview 级联计数 | API scope 注入（待 Module C） |

**成熟度**：Detector **B+**；Forget 匹配 **B**（scope + score 后 Engine-only 可交付；完整合规 F5-04 仍依赖 Foundation 级联与 API 接线）。综合 **B**。
