"""Normalizer — 格式标准化与实体规范化."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Optional

# Nested body fields treated as entity identity (not a generic walk).
_IDENTITY_ITEM_FIELDS = ("vendor",)

# Default alias dictionary for V0.1 entity normalization
_DEFAULT_ENTITY_ALIASES: dict[str, str] = {
    "国家电网公司": "国家电网",
    "国网": "国家电网",
    "市自来水": "市自来水公司",
    "自来水公司": "市自来水公司",
    "新奥": "新奥燃气",
}


class Normalizer:
    """Normalize payload shape and entity names."""

    def __init__(self, aliases: Optional[Mapping[str, str]] = None) -> None:
        merged = dict(_DEFAULT_ENTITY_ALIASES)
        if aliases:
            merged.update(aliases)
        self._aliases = merged

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = deepcopy(payload)

        title = str(data.get("title") or "").strip()
        data["title"] = title

        body = data.get("body") or {}
        if not isinstance(body, dict):
            body = {"text": str(body)}
        data["body"] = self._normalize_identity_fields(body)

        entities_raw = data.get("entities") or []
        entities: list[str] = []
        for e in entities_raw:
            name = e if isinstance(e, str) else str(e.get("name", e))
            entities.append(self.normalize_entity(name))
        data["entities"] = list(dict.fromkeys(entities))  # preserve order, unique

        relations_raw = data.get("relations") or []
        relations: list[dict[str, str]] = []
        for rel in relations_raw:
            if not isinstance(rel, dict):
                continue
            src = self.normalize_entity(str(rel.get("from") or rel.get("src") or ""))
            dst = self.normalize_entity(str(rel.get("to") or rel.get("dst") or ""))
            rtype = str(rel.get("type") or "BELONG_TO").upper()
            if not src or not dst:
                continue
            relations.append({"from": src, "to": dst, "type": rtype})
        data["relations"] = relations

        return data

    def normalize_entity(self, name: str) -> str:
        text = name.strip()
        if not text:
            return text
        return self._aliases.get(text, text)

    def _normalize_identity_fields(self, body: dict[str, Any]) -> dict[str, Any]:
        items = body.get("items")
        if not isinstance(items, list):
            return body
        for item in items:
            if not isinstance(item, dict):
                continue
            for field in _IDENTITY_ITEM_FIELDS:
                value = item.get(field)
                if isinstance(value, str):
                    item[field] = self.normalize_entity(value)
        return body
