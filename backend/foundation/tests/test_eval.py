"""Tests for the Phase 4 quantitative evaluation framework."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.foundation.core.models import MemoryAtom
from backend.foundation.eval import (
    CaseKind,
    EvalCase,
    EvalConfigurationError,
    EvalDataset,
    EvalInputError,
    EvalService,
    EvalThresholds,
    MetricStatus,
    PredictionRecord,
    ReportStatus,
    dataset_sha256,
    build_reference_dataset,
    load_dataset,
    load_predictions,
    nearest_rank_percentile,
    normalize_prediction,
    render_markdown,
    write_report,
)


def _dataset() -> EvalDataset:
    return EvalDataset(
        schema_version="1.0",
        name="phase4-test",
        description="complete six-metric fixture",
        cases=[
            EvalCase(
                id="pref-1",
                task=CaseKind.PREFERENCE,
                input={"evidence_ids": ["evd-a"]},
                expected={"labels": ["OUTPUT_STYLE:output_style.compact"]},
            ),
            EvalCase(
                id="retrieval-1",
                task=CaseKind.RETRIEVAL,
                input={"text": "utilities", "context_hint": {"top_k": 1}},
                expected={
                    "knowledge_ids": ["knw-april"],
                    "evidence_ids": ["evd-april"],
                    "aggregate_amount": 434.5,
                    "amount_tolerance": 0.01,
                    "top_k": 1,
                },
            ),
            EvalCase(
                id="conflict-1",
                task=CaseKind.CONFLICT,
                input={"old": 156, "new": 186},
                expected={"resolution": "NEW_WINS"},
            ),
        ],
    )


def _predictions() -> list[PredictionRecord]:
    return [
        PredictionRecord(
            case_id="pref-1",
            prediction={"labels": ["OUTPUT_STYLE:output_style.compact"]},
            latency_ms=3,
        ),
        PredictionRecord(
            case_id="retrieval-1",
            prediction={
                "knowledge_ids": ["knw-april"],
                "evidence_ids": ["evd-april"],
                "aggregate_amount": 434.5,
            },
            latency_ms=12,
        ),
        PredictionRecord(
            case_id="conflict-1",
            prediction={"resolution": "NEW_WINS"},
            latency_ms=2,
        ),
    ]


def test_thresholds_cannot_weaken_official_values():
    with pytest.raises(ValidationError):
        EvalThresholds(preference_accuracy=0.84)
    with pytest.raises(ValidationError):
        EvalThresholds(retrieval_p95_ms=501)
    assert EvalThresholds(preference_accuracy=0.9).preference_accuracy == 0.9


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        (CaseKind.PREFERENCE, {"labels": []}),
        (CaseKind.RETRIEVAL, {"knowledge_ids": [], "top_k": 1}),
        (CaseKind.RETRIEVAL, {"knowledge_ids": ["knw"], "amount_tolerance": 0.1}),
        (CaseKind.CONFLICT, {"resolution": "UNKNOWN"}),
    ],
)
def test_case_contracts_reject_invalid_expectations(task, expected):
    with pytest.raises(ValidationError):
        EvalCase(id="bad", task=task, expected=expected)


def test_dataset_requires_unique_case_ids():
    case = EvalCase(
        id="duplicate",
        task=CaseKind.PREFERENCE,
        expected={"labels": ["OUTPUT_STYLE:key"]},
    )
    with pytest.raises(ValidationError):
        EvalDataset(schema_version="1.0", name="duplicates", cases=[case, case])


def test_load_dataset_rejects_duplicate_json_keys(tmp_path: Path):
    source = tmp_path / "duplicate.json"
    source.write_text(
        '{"schema_version":"1.0","name":"a","name":"b","cases":[]}',
        encoding="utf-8",
    )
    with pytest.raises(EvalInputError, match="duplicate JSON key"):
        load_dataset(source)


def test_load_predictions_accepts_wrapper_and_rejects_duplicates(tmp_path: Path):
    source = tmp_path / "predictions.json"
    payload = {"predictions": [record.model_dump(mode="json") for record in _predictions()]}
    source.write_text(json.dumps(payload), encoding="utf-8")
    assert len(load_predictions(source)) == 3

    payload["predictions"].append(payload["predictions"][0])
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EvalInputError, match="unique"):
        load_predictions(source)


def test_nearest_rank_percentile_is_deterministic():
    assert nearest_rank_percentile([1, 2, 3, 4], 0.95) == 4
    assert nearest_rank_percentile([4, 1, 3, 2], 0.5) == 2
    with pytest.raises(ValueError):
        nearest_rank_percentile([], 0.95)


def test_offline_predictions_pass_all_six_metrics():
    report = EvalService(timestamp=lambda: 123).evaluate_predictions(_dataset(), _predictions())

    assert report.generated_at == 123
    assert report.overall_status is ReportStatus.PASS
    assert {metric.name for metric in report.metrics} == {
        "preference_accuracy",
        "knowledge_recall_at_k",
        "knowledge_recall@1",
        "knowledge_recall@3",
        "knowledge_recall@5",
        "retrieval_p50_ms",
        "retrieval_p95_ms",
        "retrieval_p99_ms",
        "conflict_accuracy",
        "aggregation_accuracy",
        "evidence_trace_accuracy",
        "scope_isolation_accuracy",
    }
    # 全部指标无 FAIL；scope 隔离无样本时为 NOT_EVALUATED（数据未声明 scope）
    assert not any(metric.status is MetricStatus.FAIL for metric in report.metrics)
    assert next(metric for metric in report.metrics if metric.name == "retrieval_p95_ms").value == 12


def test_failures_are_counted_and_make_report_fail():
    predictions = _predictions()
    predictions[1] = PredictionRecord(
        case_id="retrieval-1",
        prediction={
            "knowledge_ids": ["knw-wrong"],
            "evidence_ids": [],
            "aggregate_amount": 999,
        },
        latency_ms=700,
    )
    report = EvalService().evaluate_predictions(_dataset(), predictions)
    metrics = {metric.name: metric for metric in report.metrics}

    assert report.overall_status is ReportStatus.FAIL
    assert metrics["knowledge_recall_at_k"].status is MetricStatus.FAIL
    assert metrics["retrieval_p95_ms"].status is MetricStatus.FAIL
    assert metrics["aggregation_accuracy"].status is MetricStatus.FAIL
    assert metrics["evidence_trace_accuracy"].status is MetricStatus.FAIL


def test_subset_dataset_is_reported_incomplete():
    dataset = EvalDataset(
        schema_version="1.0",
        name="preference-only",
        cases=[
            EvalCase(
                id="pref-only",
                task=CaseKind.PREFERENCE,
                expected={"labels": ["OP_HABIT:key"]},
            )
        ],
    )
    report = EvalService().evaluate_predictions(
        dataset,
        [
            PredictionRecord(
                case_id="pref-only",
                prediction={"labels": ["OP_HABIT:key"]},
                latency_ms=1,
            )
        ],
    )
    assert report.overall_status is ReportStatus.INCOMPLETE
    assert any(metric.status is MetricStatus.NOT_EVALUATED for metric in report.metrics)


def test_missing_and_unknown_predictions_are_handled_strictly():
    report = EvalService().evaluate_predictions(_dataset(), _predictions()[:-1])
    conflict = next(outcome for outcome in report.outcomes if outcome.case_id == "conflict-1")
    assert conflict.error == "missing prediction"
    assert report.overall_status is ReportStatus.FAIL

    with pytest.raises(EvalConfigurationError, match="unknown case"):
        EvalService().evaluate_predictions(
            _dataset(),
            [PredictionRecord(case_id="unknown", prediction={}, latency_ms=0)],
        )


def test_recall_at_k_preserves_prediction_order():
    predictions = _predictions()
    predictions[1] = PredictionRecord(
        case_id="retrieval-1",
        prediction={
            "knowledge_ids": ["knw-wrong", "knw-april"],
            "evidence_ids": ["evd-april"],
            "aggregate_amount": 434.5,
        },
        latency_ms=5,
    )
    report = EvalService().evaluate_predictions(_dataset(), predictions)
    recall = next(metric for metric in report.metrics if metric.name == "knowledge_recall_at_k")
    assert recall.value == 0
    assert recall.status is MetricStatus.FAIL


def test_normalize_prediction_accepts_memory_atom():
    case = next(case for case in _dataset().cases if case.task is CaseKind.RETRIEVAL)
    atom = MemoryAtom(
        answer="result",
        source_evidence=["evd-april"],
        source_knowledge="knw-april",
        confidence=0.9,
        latency_ms=10,
    )
    assert normalize_prediction(case, atom) == {
        "knowledge_ids": ["knw-april"],
        "evidence_ids": ["evd-april"],
    }


@pytest.mark.asyncio
async def test_live_service_normalizes_outputs_and_measures_latency():
    ticks = iter([0.0, 0.002, 0.002, 0.014, 0.014, 0.017])
    service = EvalService(clock=lambda: next(ticks), timestamp=lambda: 456)

    async def preference_runner(_case):
        return {
            "extracted_preferences": [
                {"category": "OUTPUT_STYLE", "key": "output_style.compact"}
            ]
        }

    async def retrieval_runner(_case):
        return {
            "source_knowledge": "knw-april",
            "source_evidence": ["evd-april"],
            "aggregate_amount": 434.5,
        }

    def conflict_runner(_case):
        return {"resolution": "NEW_WINS"}

    report = await service.run(
        _dataset(),
        {
            "preference": preference_runner,
            CaseKind.RETRIEVAL: retrieval_runner,
            "conflict": conflict_runner,
        },
    )
    assert report.generated_at == 456
    assert report.overall_status is ReportStatus.PASS
    latencies = [outcome.latency_ms for outcome in report.outcomes]
    assert latencies == pytest.approx([2, 12, 3])


@pytest.mark.asyncio
async def test_live_service_requires_all_runners():
    with pytest.raises(EvalConfigurationError, match="missing runners"):
        await EvalService().run(_dataset(), {"preference": lambda _case: {"labels": []}})


@pytest.mark.asyncio
async def test_runner_exception_does_not_leak_message():
    secret = "secret-value"

    def failing_runner(_case):
        raise RuntimeError(secret)

    runners = {
        "preference": failing_runner,
        "retrieval": lambda _case: {
            "knowledge_ids": ["knw-april"],
            "evidence_ids": ["evd-april"],
            "aggregate_amount": 434.5,
        },
        "conflict": lambda _case: {"resolution": "NEW_WINS"},
    }
    report = await EvalService().run(_dataset(), runners)
    outcome = next(item for item in report.outcomes if item.case_id == "pref-1")
    assert "RuntimeError" in outcome.error
    assert secret not in outcome.error
    assert report.overall_status is ReportStatus.FAIL


def test_report_render_and_atomic_write(tmp_path: Path):
    report = EvalService(timestamp=lambda: 123).evaluate_predictions(_dataset(), _predictions())
    markdown = render_markdown(report)
    assert "# PIXIU Evaluation Report" in markdown
    assert "knowledge_recall_at_k" in markdown
    assert "**PASS**" in markdown

    json_path, markdown_path = write_report(report, tmp_path, stem="phase4")
    assert json.loads(json_path.read_text(encoding="utf-8"))["overall_status"] == "PASS"
    assert markdown_path.read_text(encoding="utf-8") == markdown
    with pytest.raises(FileExistsError):
        write_report(report, tmp_path, stem="phase4")
    with pytest.raises(EvalConfigurationError):
        write_report(report, tmp_path, stem="../escape")


def test_dataset_hash_is_canonical_and_sensitive_to_content():
    dataset = _dataset()
    clone = EvalDataset.model_validate(dataset.model_dump(mode="json"))
    assert dataset_sha256(dataset) == dataset_sha256(clone)

    changed = clone.model_copy(update={"name": "changed"})
    assert dataset_sha256(dataset) != dataset_sha256(changed)


def test_acceptance_profile_enforces_dataset_and_sample_sizes():
    base = _dataset().model_dump(mode="json")
    base["profile"] = "acceptance"
    with pytest.raises(ValidationError, match="50 retrieval"):
        EvalDataset.model_validate(base)


def test_reference_dataset_covers_official_case_and_latency_counts():
    dataset = build_reference_dataset()
    retrieval = [case for case in dataset.cases if case.task is CaseKind.RETRIEVAL]
    preference = [case for case in dataset.cases if case.task is CaseKind.PREFERENCE]
    conflict = [case for case in dataset.cases if case.task is CaseKind.CONFLICT]

    assert dataset.profile == "acceptance"
    assert len(dataset.fixtures) == 50
    assert len(retrieval) == 50
    assert len(preference) == 15
    assert len(conflict) == 25
    assert len(retrieval) * dataset.retrieval_repetitions == 1000
    assert all("aggregate_amount" in case.expected for case in retrieval)
    assert all("evidence_ids" in case.expected for case in retrieval)


def test_latency_metric_requires_all_declared_samples():
    payload = _dataset().model_dump(mode="json")
    payload["retrieval_repetitions"] = 2
    dataset = EvalDataset.model_validate(payload)

    report = EvalService().evaluate_predictions(dataset, _predictions())
    latency = next(metric for metric in report.metrics if metric.name == "retrieval_p95_ms")
    assert latency.status is MetricStatus.NOT_EVALUATED
    assert report.overall_status is ReportStatus.INCOMPLETE

    predictions = _predictions()
    predictions[1] = predictions[1].model_copy(
        update={"latency_samples_ms": [12.0, 14.0]}
    )
    complete = EvalService().evaluate_predictions(dataset, predictions)
    latency = next(metric for metric in complete.metrics if metric.name == "retrieval_p95_ms")
    assert latency.value == 14
    assert latency.status is MetricStatus.PASS
    assert complete.overall_status is ReportStatus.PASS


def test_cli_scores_prediction_file(tmp_path: Path, capsys):
    from backend.foundation.eval.__main__ import main

    dataset_path = tmp_path / "dataset.json"
    predictions_path = tmp_path / "predictions.json"
    output_dir = tmp_path / "reports"
    dataset_path.write_text(
        json.dumps(_dataset().model_dump(mode="json"), ensure_ascii=False),
        encoding="utf-8",
    )
    predictions_path.write_text(
        json.dumps([item.model_dump(mode="json") for item in _predictions()]),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--dataset",
            str(dataset_path),
            "--predictions",
            str(predictions_path),
            "--output-dir",
            str(output_dir),
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "PASS"
    assert (output_dir / "eval-report.json").exists()
    assert (output_dir / "eval-report.md").exists()


def test_reference_dataset_scores_complete_1000_sample_capture():
    dataset = build_reference_dataset()
    predictions: list[PredictionRecord] = []
    for case in dataset.cases:
        if case.task is CaseKind.PREFERENCE:
            prediction = {"labels": case.expected["labels"]}
            samples: list[float] = []
        elif case.task is CaseKind.CONFLICT:
            prediction = {"resolution": case.expected["resolution"]}
            samples = []
        else:
            prediction = {
                "knowledge_ids": case.expected["knowledge_ids"],
                "evidence_ids": case.expected["evidence_ids"],
                "aggregate_amount": case.expected["aggregate_amount"],
            }
            samples = [25.0] * dataset.retrieval_repetitions
        predictions.append(
            PredictionRecord(
                case_id=case.id,
                prediction=prediction,
                latency_ms=25,
                latency_samples_ms=samples,
            )
        )

    report = EvalService().evaluate_predictions(dataset, predictions)
    latency = next(metric for metric in report.metrics if metric.name == "retrieval_p95_ms")
    assert report.dataset_profile == "acceptance"
    assert report.overall_status is ReportStatus.PASS
    assert latency.denominator == 1000
    assert latency.value == 25


# ═══════════════════════════════════════════════════════
# Phase 5: scope isolation + fixed-k recall + p50/p99
# ═══════════════════════════════════════════════════════

def _scope_dataset() -> EvalDataset:
    return EvalDataset(
        schema_version="1.0",
        name="scope-test",
        profile="development",
        cases=[
            EvalCase(
                id="ret-scope-ok",
                task=CaseKind.RETRIEVAL,
                input={},
                expected={"knowledge_ids": ["knw-a"], "scope": "shared:home"},
            ),
            EvalCase(
                id="ret-scope-bad",
                task=CaseKind.RETRIEVAL,
                input={},
                expected={"knowledge_ids": ["knw-b"], "scope": "shared:home"},
            ),
        ],
    )


def test_scope_isolation_passes_when_all_in_scope():
    report = EvalService().evaluate_predictions(
        _scope_dataset(),
        [
            PredictionRecord(
                case_id="ret-scope-ok",
                prediction={
                    "knowledge_ids": ["knw-a"],
                    "knowledge_scopes": {"knw-a": "shared:home"},
                },
                latency_ms=5,
            ),
            PredictionRecord(
                case_id="ret-scope-bad",
                prediction={
                    "knowledge_ids": ["knw-b"],
                    "knowledge_scopes": {"knw-b": "shared:home"},
                },
                latency_ms=5,
            ),
        ],
    )
    metric = next(m for m in report.metrics if m.name == "scope_isolation_accuracy")
    assert metric.status is MetricStatus.PASS
    assert metric.value == 1.0


def test_scope_isolation_fails_on_violation():
    report = EvalService().evaluate_predictions(
        _scope_dataset(),
        [
            PredictionRecord(
                case_id="ret-scope-ok",
                prediction={
                    "knowledge_ids": ["knw-a"],
                    "knowledge_scopes": {"knw-a": "shared:home"},
                },
                latency_ms=5,
            ),
            PredictionRecord(
                case_id="ret-scope-bad",
                prediction={
                    "knowledge_ids": ["knw-b"],
                    "knowledge_scopes": {"knw-b": "user:private"},
                },
                latency_ms=5,
            ),
        ],
    )
    metric = next(m for m in report.metrics if m.name == "scope_isolation_accuracy")
    assert metric.status is MetricStatus.FAIL
    assert metric.value == 0.5
    assert report.overall_status is ReportStatus.FAIL


def test_scope_isolation_not_evaluated_without_scope_field():
    report = EvalService().evaluate_predictions(_dataset(), _predictions())
    metric = next(m for m in report.metrics if m.name == "scope_isolation_accuracy")
    assert metric.status is MetricStatus.NOT_EVALUATED
    assert report.overall_status is ReportStatus.PASS


def test_scope_isolation_fails_when_scopes_missing():
    """Declared scope but prediction lacks knowledge_scopes -> cannot prove isolation."""
    report = EvalService().evaluate_predictions(
        _scope_dataset(),
        [
            PredictionRecord(
                case_id="ret-scope-ok",
                prediction={"knowledge_ids": ["knw-a"]},
                latency_ms=5,
            ),
            PredictionRecord(
                case_id="ret-scope-bad",
                prediction={"knowledge_ids": ["knw-b"]},
                latency_ms=5,
            ),
        ],
    )
    metric = next(m for m in report.metrics if m.name == "scope_isolation_accuracy")
    assert metric.status is MetricStatus.FAIL


def test_recall_fixed_buckets_values():
    """Recall@1/@3/@5 reflect each fixed k."""
    dataset = EvalDataset(
        schema_version="1.0",
        name="bucket-test",
        profile="development",
        cases=[
            EvalCase(
                id="ret-bucket",
                task=CaseKind.RETRIEVAL,
                input={},
                expected={"knowledge_ids": ["knw-target"], "top_k": 1},
            ),
        ],
    )
    report = EvalService().evaluate_predictions(
        dataset,
        [
            PredictionRecord(
                case_id="ret-bucket",
                prediction={"knowledge_ids": ["knw-x", "knw-target"]},
                latency_ms=5,
            ),
        ],
    )
    values = {m.name: m.value for m in report.metrics}
    assert values["knowledge_recall@1"] == 0.0
    assert values["knowledge_recall@3"] == 1.0
    assert values["knowledge_recall@5"] == 1.0


def test_p50_p99_latency_metrics_present():
    report = EvalService().evaluate_predictions(_dataset(), _predictions())
    names = {m.name for m in report.metrics}
    assert "retrieval_p50_ms" in names
    assert "retrieval_p99_ms" in names
    p50 = next(m for m in report.metrics if m.name == "retrieval_p50_ms")
    p99 = next(m for m in report.metrics if m.name == "retrieval_p99_ms")
    assert p50.value is not None
    assert p99.value is not None
