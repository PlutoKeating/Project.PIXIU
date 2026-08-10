"""Strict UTF-8 JSON loaders for evaluation inputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import EvalDataset, PredictionRecord

MAX_DATASET_BYTES = 8 * 1024 * 1024
MAX_PREDICTIONS_BYTES = 16 * 1024 * 1024


class EvalInputError(ValueError):
    """Raised when a benchmark input is unsafe or malformed."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvalInputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: str | Path, *, max_bytes: int) -> Any:
    source = Path(path)
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise EvalInputError(f"unable to inspect input file: {source}") from exc
    if size > max_bytes:
        raise EvalInputError(f"input file exceeds {max_bytes} bytes: {source}")
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise EvalInputError(f"unable to read UTF-8 input file: {source}") from exc
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise EvalInputError(f"invalid JSON in {source}: {exc.msg}") from exc


def load_dataset(path: str | Path) -> EvalDataset:
    """Load and validate a versioned evaluation dataset."""

    payload = _load_json(path, max_bytes=MAX_DATASET_BYTES)
    try:
        return EvalDataset.model_validate(payload)
    except ValidationError as exc:
        raise EvalInputError(f"invalid evaluation dataset: {exc}") from exc


def load_predictions(path: str | Path) -> list[PredictionRecord]:
    """Load captured predictions from a JSON list or wrapper object."""

    payload = _load_json(path, max_bytes=MAX_PREDICTIONS_BYTES)
    if isinstance(payload, dict):
        if set(payload) != {"predictions"}:
            raise EvalInputError("prediction wrapper must contain only 'predictions'")
        payload = payload["predictions"]
    if not isinstance(payload, list):
        raise EvalInputError("predictions must be a JSON list")
    if len(payload) > 10_000:
        raise EvalInputError("predictions contain more than 10,000 records")
    try:
        records = [PredictionRecord.model_validate(item) for item in payload]
    except ValidationError as exc:
        raise EvalInputError(f"invalid prediction record: {exc}") from exc
    ids = [record.case_id for record in records]
    if len(ids) != len(set(ids)):
        raise EvalInputError("prediction case IDs must be unique")
    return records
