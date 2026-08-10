"""PIXIU quantitative evaluation framework."""

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
)
from .reference import build_reference_dataset

__all__ = [
    "CaseKind", "CaseOutcome", "EvalCase", "EvalConfigurationError",
    "EvalDataset", "EvalExecutionError", "EvalInputError", "EvalReport",
    "EvalService", "EvalThresholds", "MetricResult", "MetricStatus",
    "PredictionRecord", "ReportStatus", "build_reference_dataset", "compute_metrics", "dataset_sha256",
    "load_dataset", "load_predictions", "nearest_rank_percentile",
    "normalize_prediction", "render_markdown", "write_report",
]
