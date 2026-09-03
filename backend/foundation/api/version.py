"""Machine-readable PIXIU component and compatibility versions."""

from __future__ import annotations

import os
import re

from ..storage.schema import SCHEMA_VERSION

API_VERSION = "0.4.0"
AGENT_MEMORY_API_VERSION = 1
COMPONENT_NAME = "pixiu-memory-backend"

_PRODUCT_VERSION = re.compile(
    r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$"
)


def product_version() -> str:
    """Return the release-injected product version without guessing in source trees."""
    value = os.environ.get("PIXIU_PRODUCT_VERSION", "").strip()
    if not value:
        return "development"
    if not _PRODUCT_VERSION.fullmatch(value):
        return "invalid"
    return value


def version_report() -> dict[str, str | int]:
    return {
        "product_version": product_version(),
        "component": COMPONENT_NAME,
        "api_version": API_VERSION,
        "agent_memory_api": AGENT_MEMORY_API_VERSION,
        "schema_version": SCHEMA_VERSION,
    }
