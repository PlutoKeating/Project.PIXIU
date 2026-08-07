"""Structurer — Evidence → KnowledgeItem by kind."""

from __future__ import annotations

import time
from typing import Any

from backend.foundation.core.idgen import gen_knowledge_id
from backend.foundation.core.models import Evidence, KnowledgeItem


class Structurer:
    def structure(self, evidence: Evidence) -> KnowledgeItem:
        raw = evidence.raw or {}
        title = str(raw.get("title") or "untitled")
        body = raw.get("body") if isinstance(raw.get("body"), dict) else {"text": str(raw)}
        entities = [str(e) for e in (raw.get("entities") or [])]
        relations = list(raw.get("relations") or [])
        kind = self._infer_kind(evidence, body)
        now = int(time.time())

        return KnowledgeItem(
            id=gen_knowledge_id(),
            kind=kind,
            title=title,
            body=dict(body),
            entities=entities,
            relations=[r if isinstance(r, dict) else {} for r in relations],
            status="ACTIVE",
            version=1,
            evidence_ids=[evidence.id],
            scope=evidence.scope,
            created_at=now,
            updated_at=now,
        )

    def _infer_kind(self, evidence: Evidence, body: dict[str, Any]) -> str:
        explicit = body.get("kind") or (evidence.raw or {}).get("kind")
        if explicit in {"FACT", "WORKFLOW", "CASE", "TEMPLATE"}:
            return str(explicit)

        if evidence.source_type == "OCR" and isinstance(body.get("items"), list):
            return "FACT"
        if evidence.source_type == "MANUAL_CONFIG" and body.get("template"):
            return "TEMPLATE"
        if evidence.source_type == "TOOL_RESULT" and (
            body.get("steps") or body.get("workflow")
        ):
            return "WORKFLOW"
        if evidence.source_type == "USER_BEHAVIOR" and body.get("case"):
            return "CASE"
        if body.get("steps"):
            return "WORKFLOW"
        if body.get("template"):
            return "TEMPLATE"
        return "FACT"
