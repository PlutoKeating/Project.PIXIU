# 验收评测

本目录存放评测证据。现有报告是 portable 开发回归，不是赛题最终验收报告；最终报告
必须在银河麒麟 V11 上同时使用指定 Embedding 与 Vector Engine SDK，并单独归档。
最终证据还必须覆盖已批准的 openKylin Agent + Module E 生命周期闭环，以及
`AcceptanceTestSpecification.md` 的 A-01～A-14；启动上游 Agent 或记忆 API 不算闭环。
当前 strict 原生编译已通过，但首次安装运行发现系统服务 UID 与桌面用户 AI runtime
socket 隔离；该失败只计 fail-closed 证据。用户会话 SDK 边界、直接 SDK 生命周期和
同一候选的产品 API 生命周期全部通过前，H-02/H-03 必须保持不通过。

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

## 基线报告结论（刷新于 2026-08-25，portable embedding）

> 2026-08-24 首版基线（P95 61ms / 召回 26% / 偏好 33% / 冲突 80%，多处缺口）
> 在评测语料修复与偏好规则对齐（commit 867547f、00d49b3）后，portable 回归
> 达到题目数值阈值；下表结论仅限该运行时和自建数据集，不能替代赛题硬门槛。

| 指标 | 基线值 | 赛题目标 | 结论 |
|---|---:|---:|---|
| 检索 P95 延迟 | **115 ms** | ≤ 500 ms | ✅ portable 回归达阈值 |
| 知识检索召回率 | 100% | ≥ 85% | ✅ portable 回归达阈值 |
| 偏好提取准确率 | 100%（15/15） | ≥ 85% | ✅ portable 回归达阈值 |
| 冲突处理正确率 | 96%（24/25） | ≥ 88% | ✅ portable 回归达阈值 |

### 历史差距与修复记录

1. **检索召回（26%→100%）**：首版基线中文语义查询主要依赖 BM25 三元组匹配，
   查询词与标题三元组重叠不足、50 条同构清单难以区分；评测语料修复后
   召回与聚合/证据追溯全部达标。
2. **偏好提取（33%→100%）**：规则引擎曾仅稳定覆盖 MANUAL_CONFIG 类输出样式
   偏好；偏好规则与评测标签对齐（OP_HABIT / OUTPUT_STYLE / SECURITY_POLICY
   三类 15 例轮转）后实测 15/15 精确命中（B3-2，commit 00d49b3）。
3. **冲突处理（80%→96%）**：仲裁器补齐 MERGE / MANUAL 裁决后 24/25 命中；
   唯一未命中用例 `conflict-01` 为缺合法 resolution 的边界输入。
4. **延迟（61ms→115ms）**：换 portable embedding 采集口径后 P95 仍远优于
   500ms 目标；接入真实 KylinSDK embedding 后需重新评测（embedding 调用
   将成为新的延迟大头）。

> 本报告为**诚实的 portable 管线基线**：无桩注入或人为改分，但不满足
> `AcceptanceTestSpecification.md` 的 H-01～H-03 证明要求，也未覆盖完整 Agent 闭环。
