# PIXIU Eval Framework

`eval/` provides the reproducible quantitative evaluation mechanism required by F7-01 through F7-05. It does not call Module B directly. A caller supplies task runners or captured predictions, so the same metric definitions can be used with unit stubs, Windows development builds, and the real Kylin deployment.

## Metrics

| Metric | Definition | Threshold |
|---|---|---:|
| `preference_accuracy` | Exact-set accuracy of canonical `CATEGORY:key` labels | >= 85% |
| `knowledge_recall_at_k` | Mean relevant-item recall at each case's declared `top_k` | >= 85% |
| `retrieval_p95_ms` | Nearest-rank P95 over end-to-end retrieval calls | <= 500 ms |
| `conflict_accuracy` | Exact expected resolution accuracy | >= 88% |
| `aggregation_accuracy` | Numeric total within each case's tolerance | 100% |
| `evidence_trace_accuracy` | Complete expected evidence set returned | 100% |

Official thresholds can be made stricter in a dataset but cannot be weakened.

## Dataset profiles

- `development`: small deterministic regression datasets are allowed.
- `acceptance`: validation requires at least 50 retrieval cases, preference and conflict cases, aggregation and evidence expectations, and at least 1000 declared retrieval samples.

`build_reference_dataset()` returns the versioned `pixiu-family-expense-v1` acceptance corpus derived from the competition Appendix A:

- 50 independent structured household expense fixtures and semantic golden queries.
- 15 preference cases covering operation habits, output style, and security policy.
- 25 conflict cases covering `NEW_WINS`, `MERGE`, and `MANUAL`.
- 20 repetitions per retrieval case, yielding exactly 1000 P95 samples.

The corpus is synthetic and reproducible. It validates the framework and scenario contract; final Kylin performance claims still require execution against the real SDK and target device.

The final contest report must additionally bind these metrics to the approved openKylin Agent +
Module E flow and to a three-device synchronization run. A standalone retrieval runner or portable
dataset cannot satisfy H-01 through H-03, A-01 through A-14, or the release gates in
`docs/DELIVERY_PLAN.md`.

## Dataset schema

```json
{
  "schema_version": "1.0",
  "name": "dataset-name",
  "profile": "development",
  "retrieval_repetitions": 1,
  "fixtures": [],
  "cases": [
    {
      "id": "retrieval-1",
      "task": "retrieval",
      "input": {"text": "utilities", "context_hint": {"top_k": 1}},
      "expected": {
        "knowledge_ids": ["knw-april"],
        "evidence_ids": ["evd-april"],
        "aggregate_amount": 434.5,
        "amount_tolerance": 0.01,
        "top_k": 1
      },
      "tags": ["family-expense"]
    }
  ],
  "thresholds": {
    "preference_accuracy": 0.85,
    "knowledge_recall_at_k": 0.85,
    "retrieval_p95_ms": 500,
    "conflict_accuracy": 0.88,
    "aggregation_accuracy": 1.0,
    "evidence_trace_accuracy": 1.0
  },
  "metadata": {}
}
```

Input loaders require UTF-8 JSON, reject duplicate keys and unknown fields, limit file size and case count, and validate task-specific golden outputs.

## Live runner API

```python
from backend.foundation.eval import CaseKind, EvalService, build_reference_dataset

dataset = build_reference_dataset()

async def retrieval_runner(case):
    atom = await retrieval_service.query(
        case.input["text"],
        case.input.get("context_hint"),
    )
    return {
        "source_knowledge": atom.source_knowledge,
        "source_evidence": atom.source_evidence,
        "aggregate_amount": measured_total,
    }

report = await EvalService().run(
    dataset,
    {
        CaseKind.PREFERENCE: preference_runner,
        CaseKind.RETRIEVAL: retrieval_runner,
        CaseKind.CONFLICT: conflict_runner,
    },
)
```

Cases run sequentially to avoid benchmark self-contention. Retrieval runners are called exactly `retrieval_repetitions` times. The service measures wall-clock latency around each complete runner call; a runner exception fails the case without copying its message into the report.

Fixture seeding remains the caller's responsibility because real ingestion and Kylin embedding belong to Module B.

## Captured prediction CLI

Captured predictions support repeatable offline scoring:

```json
[
  {
    "case_id": "retrieval-1",
    "prediction": {
      "knowledge_ids": ["knw-april"],
      "evidence_ids": ["evd-april"],
      "aggregate_amount": 434.5
    },
    "latency_ms": 12,
    "latency_samples_ms": [12],
    "error": null
  }
]
```

Run:

```bash
conda activate pixiu
python -m backend.foundation.eval \
  --dataset reference-v1 \
  --predictions /path/to/predictions.json \
  --output-dir /path/to/reports
```

The command writes `eval-report.json` and `eval-report.md`. Existing reports are not overwritten unless `--overwrite` is explicitly supplied. Reports contain the dataset profile and canonical SHA-256 hash. Missing cases, insufficient/excess latency samples, unavailable metric families, or runner failures cannot produce a complete PASS.
