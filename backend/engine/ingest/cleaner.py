"""Cleaner — 去噪、去重、缺失补齐."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


class Cleaner:
    """Cleans connector output into a usable payload."""

    def clean(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = deepcopy(payload)

        # Drop null / empty-string leaves
        data = self._drop_noise(data)

        # Deduplicate list fields by JSON fingerprint (top-level + body)
        for key in ("entities", "relations", "items", "events"):
            if isinstance(data.get(key), list):
                data[key] = self._dedupe_list(data[key])

        # Missing field defaults
        data.setdefault("title", "")
        data.setdefault("body", {})
        data.setdefault("entities", [])
        data.setdefault("relations", [])

        if not isinstance(data["body"], dict):
            data["body"] = {"text": str(data["body"])}
        else:
            for key in ("items", "events", "actions"):
                if isinstance(data["body"].get(key), list):
                    data["body"][key] = self._dedupe_list(data["body"][key])

        data["_content_hash"] = self.content_hash(data)
        return data

    @staticmethod
    def content_hash(payload: dict[str, Any]) -> str:
        material = {
            "title": payload.get("title", ""),
            "body": payload.get("body", {}),
            "entities": payload.get("entities", []),
            "relations": payload.get("relations", []),
        }
        blob = json.dumps(material, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _drop_noise(self, value: Any) -> Any:
        if isinstance(value, dict):
            cleaned: dict[str, Any] = {}
            for k, v in value.items():
                nv = self._drop_noise(v)
                if nv is None or nv == "":
                    continue
                cleaned[k] = nv
            return cleaned
        if isinstance(value, list):
            return [self._drop_noise(v) for v in value if v is not None and v != ""]
        return value

    @staticmethod
    def _dedupe_list(items: list[Any]) -> list[Any]:
        seen: set[str] = set()
        result: list[Any] = []
        for item in items:
            key = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result
