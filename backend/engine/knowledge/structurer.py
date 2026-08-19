"""Structurer — Evidence → KnowledgeItem by kind."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from backend.engine.ingest.normalizer import Normalizer
from backend.foundation.core.idgen import gen_knowledge_id
from backend.foundation.core.models import Evidence, KnowledgeItem

logger = logging.getLogger(__name__)

_VALID_KINDS = frozenset({"FACT", "WORKFLOW", "CASE", "TEMPLATE"})
_IDENTITY_ITEM_FIELDS = ("vendor",)


@dataclass(frozen=True)
class KindRule:
    """One kind-inference rule. ``source_type is None`` means any source."""

    source_type: Optional[str]
    required_fields: tuple[str, ...]
    target_kind: str


# Priority within this table is list order. Applied after explicit kind:
# structural rules (source_type=None) then source_type defaults, else FACT.
KIND_RULES: tuple[KindRule, ...] = (
    KindRule(None, ("steps",), "WORKFLOW"),
    KindRule(None, ("workflow",), "WORKFLOW"),
    KindRule(None, ("case",), "CASE"),
    KindRule(None, ("template",), "TEMPLATE"),
    KindRule("OCR", ("items",), "FACT"),
)


class Structurer:
    def __init__(self, aliases: Optional[Mapping[str, str]] = None) -> None:
        self._normalizer = Normalizer(aliases=aliases)

    def structure(self, evidence: Evidence) -> KnowledgeItem:
        raw = evidence.raw or {}
        title = str(raw.get("title") or "untitled")
        body = raw.get("body") if isinstance(raw.get("body"), dict) else {"text": str(raw)}
        body = dict(body)
        self._normalize_identity_fields(body)

        entities = [str(e) for e in (raw.get("entities") or [])]
        entities = self._merge_identity_entities(body, entities)
        relations = list(raw.get("relations") or [])
        kind = self._infer_kind(evidence, body)
        now = int(time.time())

        return KnowledgeItem(
            id=gen_knowledge_id(),
            kind=kind,
            title=title,
            body=body,
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
        if explicit in _VALID_KINDS:
            kind = str(explicit)
            if not self._structure_ok(kind, body):
                logger.warning(
                    "knowledge kind=%s is explicit but body failed min structure; keeping kind",
                    kind,
                )
            return kind

        source = str(getattr(evidence.source_type, "value", evidence.source_type))
        inferred: Optional[str] = None
        for rule in KIND_RULES:
            if rule.source_type is not None:
                continue
            if self._fields_present(body, rule.required_fields):
                inferred = rule.target_kind
                break
        if inferred is None:
            for rule in KIND_RULES:
                if rule.source_type is None or rule.source_type != source:
                    continue
                if self._fields_present(body, rule.required_fields):
                    inferred = rule.target_kind
                    break
        if inferred is None:
            inferred = "FACT"

        if not self._structure_ok(inferred, body):
            logger.warning(
                "knowledge inferred kind=%s failed min structure; falling back to FACT",
                inferred,
            )
            return "FACT"
        return inferred

    @staticmethod
    def _fields_present(body: dict[str, Any], fields: tuple[str, ...]) -> bool:
        return all(field in body and body[field] is not None for field in fields)

    @staticmethod
    def _structure_ok(kind: str, body: dict[str, Any]) -> bool:
        if kind == "WORKFLOW":
            if isinstance(body.get("steps"), list):
                return True
            return "workflow" in body and body.get("workflow") is not None
        if kind == "TEMPLATE":
            return "template" in body and body.get("template") is not None
        if kind == "CASE":
            return "case" in body and body.get("case") is not None
        return True

    def _normalize_identity_fields(self, body: dict[str, Any]) -> None:
        items = body.get("items")
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            for field in _IDENTITY_ITEM_FIELDS:
                value = item.get(field)
                if isinstance(value, str):
                    item[field] = self._normalizer.normalize_entity(value)

    def _merge_identity_entities(
        self, body: dict[str, Any], entities: list[str]
    ) -> list[str]:
        names: list[str] = [
            self._normalizer.normalize_entity(name) for name in entities
        ]
        items = body.get("items")
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                for field in _IDENTITY_ITEM_FIELDS:
                    value = item.get(field)
                    if isinstance(value, str):
                        names.append(self._normalizer.normalize_entity(value))
        unique: list[str] = []
        seen: set[str] = set()
        for name in names:
            text = name.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            unique.append(text)
        return unique
