"""Connector base and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.engine.ingest.connectors.manual_config import ManualConfigConnector
from backend.engine.ingest.connectors.conversation import ConversationConnector
from backend.engine.ingest.connectors.ocr import OcrConnector
from backend.engine.ingest.connectors.tool_result import ToolResultConnector
from backend.engine.ingest.connectors.user_behavior import UserBehaviorConnector

SOURCE_TYPES = (
    "OCR",
    "TOOL_RESULT",
    "USER_BEHAVIOR",
    "MANUAL_CONFIG",
    "CONVERSATION",
)


class Connector(ABC):
    """Adapt a source-specific raw dict into a unified intermediate payload."""

    source_type: str

    @abstractmethod
    def connect(self, raw: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


_REGISTRY: dict[str, Connector] = {
    "TOOL_RESULT": ToolResultConnector(),
    "USER_BEHAVIOR": UserBehaviorConnector(),
    "MANUAL_CONFIG": ManualConfigConnector(),
    "OCR": OcrConnector(),
    "CONVERSATION": ConversationConnector(),
}


def get_connector(source_type: str) -> Connector:
    connector = _REGISTRY.get(source_type)
    if connector is None:
        raise ValueError(
            f"unsupported source_type: {source_type}; expected one of {SOURCE_TYPES}"
        )
    return connector
