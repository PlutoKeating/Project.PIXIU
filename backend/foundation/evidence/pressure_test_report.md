# PIXIU Phase 7 压测报告

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
