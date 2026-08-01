"""OCR connector — adapt OCR structured text (e.g. expense lists)."""

from __future__ import annotations

from typing import Any


class OcrConnector:
    source_type = "OCR"

    def connect(self, raw: dict[str, Any]) -> dict[str, Any]:
        title = str(raw.get("title") or "ocr_document")
        body = raw.get("body")
        if body is None:
            text = raw.get("text") or raw.get("ocr_text") or ""
            items = raw.get("items") or []
            body = {"text": text, "items": items} if items else {"text": text}
        if not isinstance(body, dict):
            body = {"text": str(body)}

        # Pre-extract entities from items vendors / explicit entities
        entities = list(raw.get("entities") or [])
        items = body.get("items") or []
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                vendor = item.get("vendor")
                if vendor and vendor not in entities:
                    entities.append(str(vendor))
                category = item.get("category")
                if category and category not in entities:
                    entities.append(str(category))

        relations = list(raw.get("relations") or [])
        # Auto BELONG_TO from vendor → category when both present
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                vendor = item.get("vendor")
                category = item.get("category")
                if vendor and category:
                    rel = {"from": str(vendor), "to": str(category), "type": "BELONG_TO"}
                    if rel not in relations:
                        relations.append(rel)

        return {
            "title": title,
            "body": body,
            "entities": entities,
            "relations": relations,
        }
