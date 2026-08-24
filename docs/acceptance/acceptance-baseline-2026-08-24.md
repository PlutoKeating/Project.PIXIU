# PIXIU Evaluation Report

- Dataset: `pixiu-family-expense-v1`
- Dataset profile: `acceptance`
- Dataset SHA-256: `946f1132af8f743338af8dc586ebf832775312fd472b32b38627d75dc66a361b`
- Generated at (UTC Unix): `1787575067`
- Overall status: **FAIL**

## Metrics

| Metric | Value | Target | Samples | Status |
|---|---:|---:|---:|---|
| `preference_accuracy` | 33.33% | >= 85.00% | 15 | FAIL |
| `knowledge_recall_at_k` | 26.00% | >= 85.00% | 50 | FAIL |
| `knowledge_recall@1` | 26.00% | >= 85.00% | 50 | FAIL |
| `knowledge_recall@3` | 26.00% | >= 85.00% | 50 | FAIL |
| `knowledge_recall@5` | 26.00% | >= 85.00% | 50 | FAIL |
| `retrieval_p95_ms` | 61.166 ms | <= 500.000 ms | 1000 | PASS |
| `retrieval_p50_ms` | 39.729 ms | <= 500.000 ms | 1000 | PASS |
| `retrieval_p99_ms` | 76.264 ms | <= 500.000 ms | 1000 | PASS |
| `conflict_accuracy` | 80.00% | >= 88.00% | 25 | FAIL |
| `aggregation_accuracy` | 26.00% | >= 100.00% | 50 | FAIL |
| `evidence_trace_accuracy` | 26.00% | >= 100.00% | 50 | FAIL |
| `scope_isolation_accuracy` | n/a | >= 100.00% | 0 | NOT_EVALUATED |
