"""USER_BEHAVIOR connector — adapt user action event sequences."""

from __future__ import annotations

from typing import Any


class UserBehaviorConnector:
    source_type = "USER_BEHAVIOR"

    def connect(self, raw: dict[str, Any]) -> dict[str, Any]:
        events = raw.get("events") or raw.get("actions") or []
        if not isinstance(events, list):
            events = [events]

        title = str(raw.get("title") or "user_behavior")
        body: dict[str, Any] = {
            "events": events,
            "summary": raw.get("summary"),
        }
        # Drop None summary
        if body["summary"] is None:
            del body["summary"]

        return {
            "title": title,
            "body": body,
            "entities": list(raw.get("entities") or []),
            "relations": list(raw.get("relations") or []),
        }
