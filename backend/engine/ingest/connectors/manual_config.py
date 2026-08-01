"""MANUAL_CONFIG connector — adapt key-value user configuration."""

from __future__ import annotations

from typing import Any


class ManualConfigConnector:
    source_type = "MANUAL_CONFIG"

    def connect(self, raw: dict[str, Any]) -> dict[str, Any]:
        title = str(raw.get("title") or raw.get("key") or "manual_config")
        if "body" in raw and isinstance(raw["body"], dict):
            body = dict(raw["body"])
        else:
            body = {
                k: v
                for k, v in raw.items()
                if k not in {"title", "entities", "relations"}
            }

        return {
            "title": title,
            "body": body,
            "entities": list(raw.get("entities") or []),
            "relations": list(raw.get("relations") or []),
        }
