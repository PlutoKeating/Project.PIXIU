"""PIXIU quantitative evaluation framework."""

from .benchmark import SyncBenchmark, SystemBenchmark
from .dataset import EvalInputError, load_dataset, load_predictions
from .eval import (
    EvalConfigurationError,
    EvalExecutionError,
    EvalService,
    dataset_sha256,
    normalize_prediction,
    render_markdown,
    write_report,
)
from .metrics import compute_metrics, nearest_rank_percentile
from .models import (
    BenchmarkMetric,
    BenchmarkReport,
    CaseKind,
    CaseOutcome,
    EvalCase,
    EvalDataset,
    EvalReport,
    EvalThresholds,
    MetricResult,
    MetricStatus,
    PredictionRecord,
    ReportStatus,
    SyncRound,
)
from .reference import build_reference_dataset
from .report import render_benchmark_markdown, write_benchmark_report
from .service import BenchmarkService

__all__ = [
    # benchmark
    "BenchmarkService",
    "SyncBenchmark",
    "SystemBenchmark",
    # dataset / reference
    "EvalInputError",
    "build_reference_dataset",
    "load_dataset",
    "load_predictions",
    # eval service
    "EvalConfigurationError",
    "EvalExecutionError",
    "EvalService",
    "dataset_sha256",
    "normalize_prediction",
    "render_markdown",
    "write_report",
    # metrics
    "compute_metrics",
    "nearest_rank_percentile",
    # models
    "BenchmarkMetric",
    "BenchmarkReport",
    "CaseKind",
    "CaseOutcome",
    "EvalCase",
    "EvalDataset",
    "EvalReport",
    "EvalThresholds",
    "MetricResult",
    "MetricStatus",
    "PredictionRecord",
    "ReportStatus",
    "SyncRound",
    # report
    "render_benchmark_markdown",
    "write_benchmark_report",
]
