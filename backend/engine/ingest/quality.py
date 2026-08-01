"""Quality — Schema 校验与 quality_score 计算."""

from __future__ import annotations

from typing import Any


_SOURCE_CONFIDENCE: dict[str, float] = {
    "MANUAL_CONFIG": 0.95,
    "TOOL_RESULT": 0.90,
    "OCR": 0.80,
    "USER_BEHAVIOR": 0.75,
}


class QualityError(ValueError):
    """Raised when payload fails schema validation."""


class Quality:
    """Validate schema and compute quality_score in [0, 1]."""

    def validate(self, payload: dict[str, Any], source_type: str) -> None:
        if not isinstance(payload, dict):
            raise QualityError("payload must be a dict")
        if "title" not in payload:
            raise QualityError("missing required field: title")
        if "body" not in payload or not isinstance(payload["body"], dict):
            raise QualityError("missing or invalid field: body")
        if source_type not in _SOURCE_CONFIDENCE:
            raise QualityError(f"unsupported source_type: {source_type}")

    def score(self, payload: dict[str, Any], source_type: str) -> float:
        self.validate(payload, source_type)

        completeness = 0.0
        # title
        if str(payload.get("title") or "").strip():
            completeness += 0.35
        # body non-empty
        body = payload.get("body") or {}
        if body:
            completeness += 0.35
        # entities
        if payload.get("entities"):
            completeness += 0.15
        # relations
        if payload.get("relations"):
            completeness += 0.15

        source_conf = _SOURCE_CONFIDENCE.get(source_type, 0.7)
        # Weighted blend: completeness dominates, source confidence modulates
        raw = 0.7 * completeness + 0.3 * source_conf
        return round(min(1.0, max(0.0, raw)), 4)
