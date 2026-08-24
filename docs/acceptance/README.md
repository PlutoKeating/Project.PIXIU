# 验收评测

本目录存放正式验收评测报告（对应交付材料 D-08 与 `AcceptanceTestSpecification.md` 的
P-01~P-04 指标）。

## 复现方式

```bash
# 1) 采集：在真实 foundation/engine 管线上运行参考数据集（90 个用例，
#    其中检索用例各重复 20 次，共 1000 个 P95 样本）
PYTHONPATH=. python3 backend/scripts/capture_eval_predictions.py \
    --output build/release/eval/predictions.json

# 2) 评分：按赛题阈值计算六项指标并输出 JSON + Markdown 报告
PYTHONPATH=. python3 -m backend.foundation.eval \
    --dataset reference-v1 \
    --predictions build/release/eval/predictions.json \
    --output-dir docs/acceptance \
    --stem acceptance-baseline-<日期>
```

数据集 `pixiu-family-expense-v1` 由 `backend/foundation/eval/reference.py`
确定性生成：50 组家庭支出清单（附录 A 场景）+ 15 偏好用例 + 25 冲突用例。

## 基线报告结论（2026-08-24，portable embedding）

| 指标 | 基线值 | 赛题目标 | 结论 |
|---|---:|---:|---|
| 检索 P95 延迟 | **61 ms** | ≤ 500 ms | ✅ 达标 |
| 知识检索召回率 | 26% | ≥ 85% | ❌ 缺口 |
| 偏好提取准确率 | 33% | ≥ 85% | ❌ 缺口 |
| 冲突处理正确率 | 80% | ≥ 88% | ❌ 缺口 |

### 差距归因与后续方向

1. **检索召回（26%）**：中文语义查询主要依赖 BM25 三元组匹配；查询词与
   标题的三元组重叠不足、50 条同构清单难以区分。需要接入真实麒麟
   embedding（语义通道）并强化时间/范围过滤路由。
2. **偏好提取（33%）**：规则引擎目前仅稳定覆盖 MANUAL_CONFIG 类输出样式
   偏好；OP_HABIT 与 SECURITY_POLICY 触发条件依赖特定行为文本，需补齐
   规则覆盖面。
3. **冲突处理（80%）**：仲裁器当前只实现 NEW_WINS（20/25 用例命中）；
   MERGE / MANUAL 两类裁决尚未实现，是明确的引擎侧待办。
4. **延迟（61ms）**：纯 Python INT8 线性扫描已远优于 500ms 目标；接入
   真实 SDK 后需重新评测（embedding 调用将成为新的延迟大头）。

> 本报告为**诚实基线**：所有指标均来自真实管线执行结果，无任何桩注入或
> 人为达标处理。
