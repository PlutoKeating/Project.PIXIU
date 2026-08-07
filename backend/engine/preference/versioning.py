"""Preference versioning helpers."""

from __future__ import annotations

import time
import uuid
from typing import Any

from engine.mocks.models import Preference


def build_preference_id(category: str, key: str, scope: str) -> str:
    """Stable id so repeated extracts bump version instead of duplicating rows."""
    material = f"{scope}|{category}|{key}"
    digest = uuid.uuid5(uuid.NAMESPACE_URL, material).hex[:16]
    return f"pref_{digest}"


def to_preference(
    *,
    category: str,
    key: str,
    value: dict[str, Any],
    confidence: float,
    scope: str,
) -> Preference:
    return Preference(
        id=build_preference_id(category, key, scope),
        category=category,  # type: ignore[arg-type]
        key=key,
        value=value,
        confidence=float(confidence),
        version=1,
        scope=scope,
        updated_at=int(time.time()),
    )
