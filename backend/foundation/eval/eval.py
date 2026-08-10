"""Evaluation service: execute cases, normalize outputs, and build reports."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import tempfile
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .metrics import compute_metrics, overall_status
from .models import (
    CaseKind,
    CaseOutcome,
    EvalCase,
    EvalDataset,
    EvalReport,
    PredictionRecord,
)

Runner = Callable[[EvalCase], Any | Awaitable[Any]]


class EvalConfigurationError(ValueError):
    """Raised when a benchmark cannot be executed as configured."""


class EvalExecutionError(ValueError):
    """Raised when one runner returns an invalid result shape."""


def dataset_sha256(dataset: EvalDataset) -> str:
    """Hash the canonical validated dataset for report traceability."""

    payload = json.dumps(
        dataset.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return dict(value)
    result: dict[str, Any] = {}
    for key in (
        "labels",
        "extracted_preferences",
        "knowledge_ids",
        "source_knowledge",
        "evidence_ids",
        "source_evidence",
        "aggregate_amount",
        "resolution",
    ):
        if hasattr(value, key):
            result[key] = getattr(value, key)
    if not result:
        raise EvalExecutionError("runner result must be a mapping, Pydantic model, or supported object")
    return result


def _unique_strings(value: Any, *, field: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value] if value else []
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        raise EvalExecutionError(f"{field} must be a string list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise EvalExecutionError(f"{field} must contain only non-empty strings")
        if item not in result:
            result.append(item)
    return result


def _preference_labels(payload: dict[str, Any]) -> list[str]:
    if "labels" in payload:
        return _unique_strings(payload["labels"], field="labels")
    extracted = payload.get("extracted_preferences")
    if not isinstance(extracted, Sequence) or isinstance(extracted, (str, bytes, bytearray)):
        raise EvalExecutionError("preference result requires labels or extracted_preferences")
    labels: list[str] = []
    for item in extracted:
        if isinstance(item, str):
            label = item
        else:
            row = _as_mapping(item)
            label = row.get("label")
            if not label:
                category = row.get("category")
                key = row.get("key")
                if not isinstance(category, str) or not isinstance(key, str):
                    raise EvalExecutionError("preference entries require label or category and key")
                label = f"{category}:{key}"
        if not isinstance(label, str) or not label:
            raise EvalExecutionError("preference labels must be non-empty strings")
        if label not in labels:
            labels.append(label)
    return labels


def normalize_prediction(case: EvalCase, value: Any) -> dict[str, Any]:
    """Convert service-specific outputs into the stable evaluation schema."""

    payload = _as_mapping(value)
    if case.task is CaseKind.PREFERENCE:
        return {"labels": _preference_labels(payload)}
    if case.task is CaseKind.CONFLICT:
        resolution = payload.get("resolution")
        if hasattr(resolution, "value"):
            resolution = resolution.value
        if resolution not in {"NEW_WINS", "MERGE", "MANUAL"}:
            raise EvalExecutionError("conflict result requires a valid resolution")
        return {"resolution": resolution}

    knowledge = payload.get("knowledge_ids")
    if knowledge is None:
        knowledge = payload.get("source_knowledge")
    evidence = payload.get("evidence_ids")
    if evidence is None:
        evidence = payload.get("source_evidence")
    result = {
        "knowledge_ids": _unique_strings(knowledge, field="knowledge_ids"),
        "evidence_ids": _unique_strings(evidence, field="evidence_ids"),
    }
    scopes = payload.get("knowledge_scopes")
    if scopes is not None:
        if not isinstance(scopes, Mapping):
            raise EvalExecutionError("knowledge_scopes must be a mapping")
        normalized_scopes: dict[str, str] = {}
        for key, value in scopes.items():
            if not isinstance(key, str) or not isinstance(value, str) or not value:
                raise EvalExecutionError("knowledge_scopes must map string ids to non-empty scope strings")
            normalized_scopes[key] = value
        result["knowledge_scopes"] = normalized_scopes
    if "aggregate_amount" in payload:
        amount = payload["aggregate_amount"]
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise EvalExecutionError("aggregate_amount must be numeric")
        result["aggregate_amount"] = float(amount)
    return result


class EvalService:
    """Run benchmark cases sequentially so latency samples do not contend."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.perf_counter,
        timestamp: Callable[[], float] = time.time,
    ) -> None:
        self._clock = clock
        self._timestamp = timestamp

    async def run(
        self,
        dataset: EvalDataset,
        runners: Mapping[CaseKind | str, Runner],
    ) -> EvalReport:
        """Execute every case with a task-specific runner."""

        normalized_runners: dict[CaseKind, Runner] = {}
        for key, runner in runners.items():
            try:
                kind = key if isinstance(key, CaseKind) else CaseKind(key)
            except ValueError as exc:
                raise EvalConfigurationError(f"unsupported runner task: {key}") from exc
            if not callable(runner):
                raise EvalConfigurationError(f"runner for {kind.value} is not callable")
            normalized_runners[kind] = runner

        required = {case.task for case in dataset.cases}
        missing = sorted(kind.value for kind in required - set(normalized_runners))
        if missing:
            raise EvalConfigurationError(f"missing runners for tasks: {missing}")

        outcomes: list[CaseOutcome] = []
        for case in dataset.cases:
            repetitions = (
                dataset.retrieval_repetitions
                if case.task is CaseKind.RETRIEVAL
                else 1
            )
            prediction: dict[str, Any] = {}
            error: str | None = None
            latency_samples: list[float] = []
            for _ in range(repetitions):
                started = self._clock()
                try:
                    value = normalized_runners[case.task](case)
                    if inspect.isawaitable(value):
                        value = await value
                    normalized = normalize_prediction(case, value)
                    if not prediction:
                        prediction = normalized
                except Exception as exc:
                    if error is None:
                        if isinstance(exc, EvalExecutionError):
                            error = str(exc)
                        else:
                            error = f"{type(exc).__name__}: runner failed"
                latency_samples.append(max(0.0, (self._clock() - started) * 1000.0))
            outcomes.append(
                CaseOutcome(
                    case_id=case.id,
                    task=case.task,
                    prediction=prediction,
                    latency_ms=latency_samples[0],
                    latency_samples_ms=latency_samples,
                    error=error,
                )
            )
        return self._build_report(dataset, outcomes)

    def evaluate_predictions(
        self,
        dataset: EvalDataset,
        predictions: Sequence[PredictionRecord],
    ) -> EvalReport:
        """Score captured predictions without calling live services."""

        records: dict[str, PredictionRecord] = {}
        known = {case.id for case in dataset.cases}
        for record in predictions:
            if record.case_id in records:
                raise EvalConfigurationError(f"duplicate prediction for {record.case_id}")
            if record.case_id not in known:
                raise EvalConfigurationError(f"prediction references unknown case {record.case_id}")
            records[record.case_id] = record

        outcomes: list[CaseOutcome] = []
        for case in dataset.cases:
            record = records.get(case.id)
            if record is None:
                outcomes.append(
                    CaseOutcome(
                        case_id=case.id,
                        task=case.task,
                        latency_ms=0.0,
                        error="missing prediction",
                    )
                )
                continue
            error = record.error
            prediction: dict[str, Any] = {}
            if error is None:
                try:
                    prediction = normalize_prediction(case, record.prediction)
                except EvalExecutionError as exc:
                    error = str(exc)
            outcomes.append(
                CaseOutcome(
                    case_id=case.id,
                    task=case.task,
                    prediction=prediction,
                    latency_ms=record.latency_ms,
                    latency_samples_ms=record.latency_samples_ms,
                    error=error,
                )
            )
        return self._build_report(dataset, outcomes)

    def _build_report(
        self,
        dataset: EvalDataset,
        outcomes: list[CaseOutcome],
    ) -> EvalReport:
        metrics = compute_metrics(dataset, outcomes)
        return EvalReport(
            dataset_name=dataset.name,
            dataset_profile=dataset.profile,
            dataset_sha256=dataset_sha256(dataset),
            generated_at=int(self._timestamp()),
            overall_status=overall_status(metrics),
            metrics=metrics,
            outcomes=outcomes,
        )


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render_markdown(report: EvalReport) -> str:
    """Render a human-readable companion to the JSON report."""

    lines = [
        "# PIXIU Evaluation Report",
        "",
        f"- Dataset: `{_markdown_cell(report.dataset_name)}`",
        f"- Dataset profile: `{report.dataset_profile}`",
        f"- Dataset SHA-256: `{report.dataset_sha256}`",
        f"- Generated at (UTC Unix): `{report.generated_at}`",
        f"- Overall status: **{report.overall_status.value}**",
        "",
        "## Metrics",
        "",
        "| Metric | Value | Target | Samples | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for metric in report.metrics:
        if metric.value is None:
            value = "n/a"
        elif metric.unit == "ratio":
            value = f"{metric.value * 100:.2f}%"
        else:
            value = f"{metric.value:.3f} ms"
        if metric.unit == "ratio":
            target = f"{metric.comparison} {metric.target * 100:.2f}%"
        else:
            target = f"{metric.comparison} {metric.target:.3f} ms"
        lines.append(
            f"| `{metric.name}` | {value} | {target} | "
            f"{metric.denominator} | {metric.status.value} |"
        )

    failed = [outcome for outcome in report.outcomes if outcome.error]
    if failed:
        lines.extend(
            [
                "",
                "## Case errors",
                "",
                "| Case | Task | Error |",
                "|---|---|---|",
            ]
        )
        for outcome in failed:
            lines.append(
                f"| `{_markdown_cell(outcome.case_id)}` | "
                f"{outcome.task.value} | {_markdown_cell(outcome.error)} |"
            )
    lines.append("")
    return "\n".join(lines)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_report(
    report: EvalReport,
    output_dir: str | Path,
    *,
    stem: str = "eval-report",
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """Atomically write JSON and Markdown reports to an explicit directory."""

    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", stem):
        raise EvalConfigurationError("report stem contains unsupported characters")
    target = Path(output_dir)
    json_path = target / f"{stem}.json"
    markdown_path = target / f"{stem}.md"
    if not overwrite:
        existing = [path for path in (json_path, markdown_path) if path.exists()]
        if existing:
            raise FileExistsError(f"refusing to overwrite report: {existing[0]}")

    json_text = json.dumps(
        report.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    _atomic_write(json_path, json_text)
    _atomic_write(markdown_path, render_markdown(report))
    return json_path, markdown_path
