"""Typed contracts for PIXIU's reproducible evaluation framework."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


LatencyMs = Annotated[float, Field(ge=0.0)]


class CaseKind(str, Enum):
    """Supported benchmark case families."""

    PREFERENCE = "preference"
    RETRIEVAL = "retrieval"
    CONFLICT = "conflict"


class MetricStatus(str, Enum):
    """Threshold result for one metric."""

    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


class ReportStatus(str, Enum):
    """Overall benchmark result."""

    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"


class EvalThresholds(BaseModel):
    """Competition thresholds that callers may tighten but not weaken."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    preference_accuracy: float = Field(default=0.85, ge=0.85, le=1.0)
    knowledge_recall_at_k: float = Field(default=0.85, ge=0.85, le=1.0)
    retrieval_p95_ms: float = Field(default=500.0, gt=0.0, le=500.0)
    conflict_accuracy: float = Field(default=0.88, ge=0.88, le=1.0)
    aggregation_accuracy: Literal[1.0] = 1.0
    evidence_trace_accuracy: Literal[1.0] = 1.0


class EvalCase(BaseModel):
    """One task input and its golden expectation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    task: CaseKind
    input: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any]
    tags: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("tags")
    @classmethod
    def _unique_tags(cls, tags: list[str]) -> list[str]:
        if any(not tag or len(tag) > 64 for tag in tags):
            raise ValueError("tags must be non-empty strings no longer than 64 characters")
        if len(set(tags)) != len(tags):
            raise ValueError("tags must be unique")
        return tags

    @model_validator(mode="after")
    def _validate_expected_contract(self) -> "EvalCase":
        if self.task is CaseKind.PREFERENCE:
            self._validate_keys(required={"labels"}, allowed={"labels"})
            self._validate_string_list("labels", required=True)
        elif self.task is CaseKind.RETRIEVAL:
            self._validate_keys(
                required={"knowledge_ids"},
                allowed={
                    "knowledge_ids", "evidence_ids", "aggregate_amount",
                    "amount_tolerance", "top_k",
                },
            )
            self._validate_string_list("knowledge_ids", required=True)
            self._validate_string_list("evidence_ids", required=True)
            top_k = self.expected.get("top_k", 1)
            if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
                raise ValueError("retrieval expected.top_k must be an integer from 1 to 100")
            if "aggregate_amount" in self.expected:
                self._validate_number("aggregate_amount")
                tolerance = self.expected.get("amount_tolerance", 0.01)
                if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
                    raise ValueError("amount_tolerance must be numeric")
                if not 0.0 <= float(tolerance) <= 1.0:
                    raise ValueError("amount_tolerance must be between 0 and 1")
            elif "amount_tolerance" in self.expected:
                raise ValueError("amount_tolerance requires aggregate_amount")
        else:
            self._validate_keys(required={"resolution"}, allowed={"resolution"})
            if self.expected["resolution"] not in {"NEW_WINS", "MERGE", "MANUAL"}:
                raise ValueError("conflict expected.resolution is invalid")
        return self

    def _validate_keys(self, *, required: set[str], allowed: set[str]) -> None:
        keys = set(self.expected)
        missing = required - keys
        extra = keys - allowed
        if missing:
            raise ValueError(f"expected is missing keys: {sorted(missing)}")
        if extra:
            raise ValueError(f"expected contains unsupported keys: {sorted(extra)}")

    def _validate_string_list(self, key: str, *, required: bool) -> None:
        if key not in self.expected:
            return
        value = self.expected[key]
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise ValueError(f"expected.{key} must be a list of non-empty strings")
        if required and not value:
            raise ValueError(f"expected.{key} must not be empty")
        if len(value) != len(set(value)):
            raise ValueError(f"expected.{key} must not contain duplicates")

    def _validate_number(self, key: str) -> None:
        value = self.expected[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"expected.{key} must be numeric")


class EvalDataset(BaseModel):
    """Versioned, self-describing benchmark dataset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)
    profile: Literal["development", "acceptance"] = "development"
    retrieval_repetitions: int = Field(default=1, ge=1, le=1000)
    fixtures: list[dict[str, Any]] = Field(default_factory=list, max_length=10_000)
    cases: list[EvalCase] = Field(min_length=1, max_length=10_000)
    thresholds: EvalThresholds = Field(default_factory=EvalThresholds)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_dataset(self) -> "EvalDataset":
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("dataset case IDs must be unique")
        if self.profile == "acceptance":
            retrieval = [case for case in self.cases if case.task is CaseKind.RETRIEVAL]
            tasks = {case.task for case in self.cases}
            if len(retrieval) < 50:
                raise ValueError("acceptance profile requires at least 50 retrieval cases")
            if len(retrieval) * self.retrieval_repetitions < 1000:
                raise ValueError("acceptance profile requires at least 1000 retrieval samples")
            if not {CaseKind.PREFERENCE, CaseKind.CONFLICT}.issubset(tasks):
                raise ValueError("acceptance profile requires preference and conflict cases")
            if not any("aggregate_amount" in case.expected for case in retrieval):
                raise ValueError("acceptance profile requires aggregation expectations")
            if not any("evidence_ids" in case.expected for case in retrieval):
                raise ValueError("acceptance profile requires evidence trace expectations")
        return self


class PredictionRecord(BaseModel):
    """A captured prediction for offline/replay evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1, max_length=128)
    prediction: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = Field(ge=0.0)
    latency_samples_ms: list[LatencyMs] = Field(default_factory=list, max_length=1000)
    error: str | None = Field(default=None, max_length=1000)


class CaseOutcome(BaseModel):
    """Normalized result retained in the report for auditability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    task: CaseKind
    prediction: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = Field(ge=0.0)
    latency_samples_ms: list[LatencyMs] = Field(default_factory=list, max_length=1000)
    error: str | None = None


class MetricResult(BaseModel):
    """One computed score and its acceptance decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    value: float | None
    target: float
    comparison: Literal[">=", "<="]
    numerator: float
    denominator: int = Field(ge=0)
    unit: Literal["ratio", "ms"]
    status: MetricStatus
    description: str


class EvalReport(BaseModel):
    """Complete machine-readable evaluation result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    dataset_name: str
    dataset_profile: Literal["development", "acceptance"]
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: int
    overall_status: ReportStatus
    metrics: list[MetricResult]
    outcomes: list[CaseOutcome]
