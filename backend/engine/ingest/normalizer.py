"""Normalizer — 格式标准化与实体规范化."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


# Simple alias dictionary for V0.1 entity normalization
_ENTITY_ALIASES: dict[str, str] = {
    "国家电网公司": "国家电网",
    "国网": "国家电网",
    "市自来水": "市自来水公司",
    "自来水公司": "市自来水公司",
    "新奥": "新奥燃气",
}


class Normalizer:
    """Normalize payload shape and entity names."""

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = deepcopy(payload)

        title = str(data.get("title") or "").strip()
        data["title"] = title

        body = data.get("body") or {}
        if not isinstance(body, dict):
            body = {"text": str(body)}
        data["body"] = body

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

    @staticmethod
    def normalize_entity(name: str) -> str:
        text = name.strip()
        if not text:
            return text
        return _ENTITY_ALIASES.get(text, text)
