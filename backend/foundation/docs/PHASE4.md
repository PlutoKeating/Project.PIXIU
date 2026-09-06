# Module C · Phase 4 评测框架实现报告

> 2026-09-06 复核：本文保留原日期对应的测试/审计快照，不将历史数量、环境或待办状态当作当前结论。现行 API 为 32 个 REST 端点、六类 WS 事件，schema v12；2026-09-06 CI（`fd1a6d7`）在 Python 3.12/3.13 各通过 823 项测试。默认 auto 可降级至 portable，严格 V11 则必须使用双 SDK。原生产品链、完整 Agent 场景和三物理设备验收分别取证，最新发布规则见 `docs/DELIVERY_PLAN.md`。

> 日期：2026-08-10 ｜ 分支：feat/foundation ｜ 状态：✅ 已交付并合入 main
> 对应规格：`docs/compose/spec/foundation-eval-phase5.md`（Phase 5 扩展）

## 1. 交付范围

Phase 4 完成 Module C 的量化评测框架（`backend/foundation/eval/`），满足
验收条目 F7-01 ~ F7-05：

- 数据集：`dataset.py` 提供版本化参考数据集（`pixiu-family-expense-v1`，
  源自赛题附录 A 家庭支出场景）与 `development` / `acceptance` 两种 profile。
- 评测引擎：`eval.py` 加载数据集 → 调用外部 runner（或捕获的 prediction）→
  逐指标计算 → 输出 `EvalReport`（JSON + Markdown，含 SHA-256 校验）。
- 指标：6 项核心验收指标（preference_accuracy、knowledge_recall_at_k、
  retrieval_p95_ms、conflict_accuracy、aggregation_accuracy、
  evidence_trace_accuracy），官方阈值只能收紧不能放宽。
- CLI：`python -m backend.foundation.eval`（Module C 自带入口，可传
  `--profile` / `--overwrite` / runner 等参数）。
- 隔离设计：eval 不直接依赖 Module B，调用方提供 runner 或 prediction，
  同一套指标定义可用于单元桩、开发机与真实麒麟部署。

## 2. 参考数据集（acceptance profile）

`build_reference_dataset()` 生成的 `pixiu-family-expense-v1`：

| 类型 | 数量 | 说明 |
|------|------|------|
| 检索用例 | 50 | 独立结构化家庭支出 fixture + 语义黄金查询 |
| 偏好用例 | 15 | 覆盖 OP_HABIT / OUTPUT_STYLE / SECURITY_POLICY |
| 冲突用例 | 25 | 覆盖 NEW_WINS / MERGE / MANUAL |
| P95 样本 | 1000 | 每个检索用例重复 20 次（50 × 20） |

## 3. 指标与判定

| 指标 | 定义 | 门槛 |
|------|------|------:|
| 偏好准确率 | `CATEGORY:key` 精确集合准确率 | ≥ 85% |
| 检索召回率 | 每个 case 声明 top_k 下的相关项召回均值 | ≥ 85% |
| 检索 P95 | 端到端检索 nearest-rank P95 | ≤ 500ms |
| 冲突正确率 | 期望裁决（NEW_WINS/MERGE/MANUAL）精确匹配 | ≥ 88% |
| 聚合正确率 | 数值合计落在容差内 | 100% |
| 证据追溯率 | 返回完整期望 evidence 集合 | 100% |

指标结果统一为 `PASS` / `FAIL` / `INCOMPLETE` / `NOT_EVALUATED`，不虚报。

## 4. 运行

```bash
# 开发机（无麒麟 SDK）：用测试桩 runner 校验框架正确性
python -m pytest backend/foundation/tests/test_eval.py -q

# 评测（stub runner）
python -m backend.foundation.eval --profile development
```

真实麒麟性能验收需在目标机以真实 SDK runner 执行 acceptance profile，并将
报告归档为正式验收附件（Phase 5 的 BenchmarkService 另覆盖同步收敛与资源基准）。

## 5. 备注

- 本轮无新增后端运行时依赖（评测框架零第三方依赖）；CLI 输出采用原子写
  （JSON + Markdown + SHA-256）。
- Phase 5（`docs/compose/spec/foundation-eval-phase5.md`）在此基础上扩展
  recall@1/3/5、P50/P95/P99、scope 隔离与基准框架。
