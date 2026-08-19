"""Preference extractor — rule-driven signals (no LLM)."""

from __future__ import annotations

from typing import Any, Sequence

from backend.foundation.core.models import Evidence

from backend.engine.preference.rules import Rule, default_rules


class Extractor:
    """Extract OP_HABIT / OUTPUT_STYLE / SECURITY_POLICY by iterating rules."""

    def __init__(self, rules: Sequence[Rule] | None = None) -> None:
        self._rules: tuple[Rule, ...] = tuple(rules) if rules is not None else default_rules()

    def extract(self, evidence: Evidence) -> list[dict[str, Any]]:
        """Return candidate preference dicts (without id/version/timestamps)."""
        raw = evidence.raw or {}
        body = raw.get("body") if isinstance(raw.get("body"), dict) else {}
        source_type = str(
            getattr(evidence.source_type, "value", evidence.source_type)
        )
        found: dict[str, dict[str, Any]] = {}
        for rule in self._rules:
            if rule.source_types is not None and source_type not in rule.source_types:
                continue
            candidate = rule.apply(evidence, body, raw)
            if not candidate:
                continue
            key = str(candidate.get("key") or "")
            if not key:
                continue
            found[key] = candidate
        return list(found.values())
