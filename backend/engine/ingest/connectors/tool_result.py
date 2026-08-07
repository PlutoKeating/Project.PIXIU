"""TOOL_RESULT connector — adapt OS Agent tool output."""

from __future__ import annotations

from typing import Any


class ToolResultConnector:
    source_type = "TOOL_RESULT"

    def connect(self, raw: dict[str, Any]) -> dict[str, Any]:
        title = str(raw.get("title") or raw.get("tool_name") or "tool_result")
        body = raw.get("body")
        if body is None:
            body = {
                k: v
                for k, v in raw.items()
                if k not in {"title", "tool_name", "entities", "relations"}
            }
        if not isinstance(body, dict):
            body = {"result": body}

        return {
            "title": title,
            "body": body,
            "entities": list(raw.get("entities") or []),
            "relations": list(raw.get("relations") or []),
        }
