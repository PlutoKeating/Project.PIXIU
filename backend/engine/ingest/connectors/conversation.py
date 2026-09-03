"""CONVERSATION connector for one completed OS Agent turn."""

from __future__ import annotations

from typing import Any


class ConversationConnector:
    source_type = "CONVERSATION"

    def connect(self, raw: dict[str, Any]) -> dict[str, Any]:
        user = str(raw.get("user") or "").strip()
        assistant = str(raw.get("assistant") or "").strip()
        if not user or not assistant:
            raise ValueError("conversation requires non-empty user and assistant text")
        title = str(raw.get("title") or user[:80]).strip()
        return {
            "title": title,
            "body": {"user": user, "assistant": assistant},
            "entities": list(raw.get("entities") or []),
            "relations": list(raw.get("relations") or []),
        }
