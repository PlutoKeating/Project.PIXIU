# PIXIU Evaluation Report

> 2026-09-06 复核：本文保留原日期对应的测试/审计快照，不将历史数量、环境或待办状态当作当前结论。现行 API 为 32 个 REST 端点、六类 WS 事件，schema v12；2026-09-06 CI（`fd1a6d7`）在 Python 3.12/3.13 各通过 823 项测试。默认 auto 可降级至 portable，严格 V11 则必须使用双 SDK。原生产品链、完整 Agent 场景和三物理设备验收分别取证，最新发布规则见 `docs/DELIVERY_PLAN.md`。

- Dataset: `pixiu-family-expense-v1`
- Dataset profile: `acceptance`
- Dataset SHA-256: `7b508cb9acd25a48877a8440e538702ac2b1c0702a487a7c80d39602eebe3c3c`
- Generated at (UTC Unix): `1787594615`
- Overall status: **PASS**

## Metrics

| Metric | Value | Target | Samples | Status |
|---|---:|---:|---:|---|
| `preference_accuracy` | 100.00% | >= 85.00% | 15 | PASS |
| `knowledge_recall_at_k` | 100.00% | >= 85.00% | 50 | PASS |
| `knowledge_recall@1` | 100.00% | >= 85.00% | 50 | PASS |
| `knowledge_recall@3` | 100.00% | >= 85.00% | 50 | PASS |
| `knowledge_recall@5` | 100.00% | >= 85.00% | 50 | PASS |
| `retrieval_p95_ms` | 115.151 ms | <= 500.000 ms | 1000 | PASS |
| `retrieval_p50_ms` | 96.738 ms | <= 500.000 ms | 1000 | PASS |
| `retrieval_p99_ms` | 135.826 ms | <= 500.000 ms | 1000 | PASS |
| `conflict_accuracy` | 96.00% | >= 88.00% | 25 | PASS |
| `aggregation_accuracy` | 100.00% | >= 100.00% | 50 | PASS |
| `evidence_trace_accuracy` | 100.00% | >= 100.00% | 50 | PASS |
| `scope_isolation_accuracy` | n/a | >= 100.00% | 0 | NOT_EVALUATED |

## Case errors

| Case | Task | Error |
|---|---|---|
| `conflict-01` | conflict | conflict result requires a valid resolution |
