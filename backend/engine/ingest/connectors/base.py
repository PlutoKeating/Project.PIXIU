"""Connector base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """Adapt a source-specific raw dict into a unified payload shape."""

    source_type: str

    @abstractmethod
    def connect(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Return unified payload: title, body, entities, relations."""
