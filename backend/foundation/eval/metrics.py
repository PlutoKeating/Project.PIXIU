"""Metric definitions aligned with the competition acceptance specification."""

from __future__ import annotations

import math
from collections.abc import Iterable

from .models import (
    CaseKind,
    CaseOutcome,
    EvalDataset,
    MetricResult,
    MetricStatus,
    ReportStatus,
)


def nearest_rank_percentile(values: Iterable[float], percentile: float) -> float:
    """Return the deterministic nearest-rank percentile."""

    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("percentile requires at least one value")
    if not 0.0 < percentile <= 1.0:
        raise ValueError("percentile must be in (0, 1]")
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _ratio_metric(
    *,
    name: str,
    numerator: float,
    denominator: int,
    target: float,
    description: str,
) -> MetricResult:
    if denominator == 0:
        return MetricResult(
            name=name,
            value=None,
            target=target,
            comparison=">=",
            numerator=0.0,
            denominator=0,
            unit="ratio",
            status=MetricStatus.NOT_EVALUATED,
            description=description,
        )
    value = numerator / denominator
    return MetricResult(
        name=name,
        value=value,
        target=target,
        comparison=">=",
        numerator=numerator,
        denominator=denominator,
        unit="ratio",
        status=MetricStatus.PASS if value >= target else MetricStatus.FAIL,
        description=description,
    )


def _latency_metric(
    latencies: list[float],
    *,
    target: float,
    required_samples: int,
) -> MetricResult:
    if not latencies:
        return MetricResult(
            name="retrieval_p95_ms",
            value=None,
            target=target,
            comparison="<=",
            numerator=0.0,
            denominator=0,
            unit="ms",
            status=MetricStatus.NOT_EVALUATED,
            description="Nearest-rank P95 end-to-end retrieval latency.",
        )
    value = nearest_rank_percentile(latencies, 0.95)
    if len(latencies) != required_samples:
        status = MetricStatus.NOT_EVALUATED
    elif value <= target:
        status = MetricStatus.PASS
    else:
        status = MetricStatus.FAIL
    return MetricResult(
        name="retrieval_p95_ms",
        value=value,
        target=target,
        comparison="<=",
        numerator=value,
        denominator=len(latencies),
        unit="ms",
        status=status,
        description="Nearest-rank P95 latency; all declared repetitions are required.",
    )


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str) and item}
def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item and item not in result:
            result.append(item)
    return result


def compute_metrics(dataset: EvalDataset, outcomes: list[CaseOutcome]) -> list[MetricResult]:
    """Compute all six acceptance metrics from normalized case outcomes."""

    by_case = {outcome.case_id: outcome for outcome in outcomes}
    expected_ids = {case.id for case in dataset.cases}
    if len(by_case) != len(outcomes):
        raise ValueError("outcomes contain duplicate case IDs")
    if set(by_case) != expected_ids:
        raise ValueError("outcomes must match dataset case IDs exactly")
    thresholds = dataset.thresholds

    preference_cases = [case for case in dataset.cases if case.task is CaseKind.PREFERENCE]
    preference_correct = 0
    for case in preference_cases:
        outcome = by_case[case.id]
        actual = _string_set(outcome.prediction.get("labels"))
        expected = set(case.expected["labels"])
        if outcome.error is None and actual == expected:
            preference_correct += 1
    preference = _ratio_metric(
        name="preference_accuracy",
        numerator=float(preference_correct),
        denominator=len(preference_cases),
        target=thresholds.preference_accuracy,
        description="Exact-set accuracy of canonical category:key preference labels.",
    )

    retrieval_cases = [case for case in dataset.cases if case.task is CaseKind.RETRIEVAL]
    recall_sum = 0.0
    retrieval_latencies: list[float] = []
    for case in retrieval_cases:
        outcome = by_case[case.id]
        if outcome.error is not None:
            continue
        samples = outcome.latency_samples_ms or [outcome.latency_ms]
        if len(samples) == dataset.retrieval_repetitions:
            retrieval_latencies.extend(samples)
        top_k = int(case.expected.get("top_k", 1))
        actual = _string_list(outcome.prediction.get("knowledge_ids"))
        expected = set(case.expected["knowledge_ids"])
        recall_sum += len(set(actual[:top_k]) & expected) / len(expected)
    recall = _ratio_metric(
        name="knowledge_recall_at_k",
        numerator=recall_sum,
        denominator=len(retrieval_cases),
        target=thresholds.knowledge_recall_at_k,
        description="Mean relevant-item recall at each case's declared top_k.",
    )
    latency = _latency_metric(
        retrieval_latencies,
        target=thresholds.retrieval_p95_ms,
        required_samples=len(retrieval_cases) * dataset.retrieval_repetitions,
    )


    aggregation_cases = [
        case for case in retrieval_cases if "aggregate_amount" in case.expected
    ]
    aggregation_correct = 0
    for case in aggregation_cases:
        outcome = by_case[case.id]
        actual = outcome.prediction.get("aggregate_amount")
        expected = float(case.expected["aggregate_amount"])
        tolerance = float(case.expected.get("amount_tolerance", 0.01))
        if (
            outcome.error is None
            and not isinstance(actual, bool)
            and isinstance(actual, (int, float))
            and abs(float(actual) - expected) <= tolerance
        ):
            aggregation_correct += 1
    aggregation = _ratio_metric(
        name="aggregation_accuracy",
        numerator=float(aggregation_correct),
        denominator=len(aggregation_cases),
        target=thresholds.aggregation_accuracy,
        description="Exact numeric aggregation accuracy within the declared tolerance.",
    )

    evidence_cases = [case for case in retrieval_cases if "evidence_ids" in case.expected]
    evidence_correct = 0
    for case in evidence_cases:
        outcome = by_case[case.id]
        actual = _string_set(outcome.prediction.get("evidence_ids"))
        expected = set(case.expected["evidence_ids"])
        if outcome.error is None and expected.issubset(actual):
            evidence_correct += 1
    evidence = _ratio_metric(
        name="evidence_trace_accuracy",
        numerator=float(evidence_correct),
        denominator=len(evidence_cases),
        target=thresholds.evidence_trace_accuracy,
        description="Cases whose complete expected evidence set is traceable.",
    )

    conflict_cases = [case for case in dataset.cases if case.task is CaseKind.CONFLICT]
    conflict_correct = 0
    for case in conflict_cases:
        outcome = by_case[case.id]
        if (
            outcome.error is None
            and outcome.prediction.get("resolution") == case.expected["resolution"]
        ):
            conflict_correct += 1
    conflict = _ratio_metric(
        name="conflict_accuracy",
        numerator=float(conflict_correct),
        denominator=len(conflict_cases),
        target=thresholds.conflict_accuracy,
        description="Exact conflict resolution accuracy.",
    )

    return [preference, recall, latency, conflict, aggregation, evidence]


def overall_status(metrics: list[MetricResult]) -> ReportStatus:
    """Fail on any failed metric, otherwise require all six metrics."""

    if any(metric.status is MetricStatus.FAIL for metric in metrics):
        return ReportStatus.FAIL
    if any(metric.status is MetricStatus.NOT_EVALUATED for metric in metrics):
        return ReportStatus.INCOMPLETE
    return ReportStatus.PASS
