# PIXIU Phase 7 压测报告

> 2026-09-06 复核：本文保留原日期对应的测试/审计快照，不将历史数量、环境或待办状态当作当前结论。现行 API 为 32 个 REST 端点、六类 WS 事件，schema v12；2026-09-06 CI（`fd1a6d7`）在 Python 3.12/3.13 各通过 823 项测试。默认 auto 可降级至 portable，严格 V11 则必须使用双 SDK。原生产品链、完整 Agent 场景和三物理设备验收分别取证，最新发布规则见 `docs/DELIVERY_PLAN.md`。

- Benchmark: `phase7-1000-query-pressure`
- Runtime: `stub`（stub embedding，回归/CI；麒麟真实 SDK 需验收机）
- Samples: 1000，Errors: 0（错误率 0.00%）
- 吞吐: 58.6 QPS

## 延迟

| P50 | P95 | P99 | Max | Mean |
|---|---:|---:|---:|---:|
| 16.99 ms | 19.18 ms | 20.73 ms | 22.99 ms | 17.07 ms |

## 验收门槛

- P95 ≤ 500ms：**PASS** （实测 19.18 ms）
- 查询命中率：100.00%

> 证据文件：pressure_report.json / pressure_latencies.csv
