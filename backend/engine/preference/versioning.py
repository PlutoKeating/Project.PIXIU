"""Preference versioning helpers."""

from __future__ import annotations

import time
from typing import Any

from backend.foundation.core.idgen import gen_pref_id
from backend.foundation.core.models import Preference


def to_preference(
    *,
    category: str,
    key: str,
    value: dict[str, Any],
    confidence: float,
    scope: str,
) -> Preference:
    now = int(time.time())
    return Preference(
        id=gen_pref_id(),
        category=category,  # type: ignore[arg-type]
        key=key,
        value=value,
        confidence=float(confidence),
        version=1,
        scope=scope,
        created_at=now,
        updated_at=now,
    )
