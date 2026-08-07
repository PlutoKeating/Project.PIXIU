"""Preference extractor — rule-based signals for V0.1."""

from __future__ import annotations

from typing import Any

from backend.foundation.core.models import Evidence


class Extractor:
    """Extract OP_HABIT / OUTPUT_STYLE / SECURITY_POLICY from Evidence."""

    def extract(self, evidence: Evidence) -> list[dict[str, Any]]:
        """Return candidate preference dicts (without id/version/timestamps)."""
        candidates: list[dict[str, Any]] = []
        raw = evidence.raw or {}
        body = raw.get("body") if isinstance(raw.get("body"), dict) else {}

        candidates.extend(self._from_behavior(evidence, body))
        candidates.extend(self._from_config(evidence, body, raw))
        candidates.extend(self._from_security_signals(evidence, body, raw))
        return candidates

    def _from_behavior(
        self, evidence: Evidence, body: dict[str, Any]
    ) -> list[dict[str, Any]]:
        if evidence.source_type != "USER_BEHAVIOR":
            return []
        events = body.get("events") or []
        hotkey_count = sum(
            1
            for e in events
            if isinstance(e, dict) and e.get("action") in {"hotkey", "shortcut"}
        )
        if hotkey_count >= 1:
            return [
                {
                    "category": "OP_HABIT",
                    "key": "op_habit.prefer_hotkey",
                    "value": {"enabled": True, "signal_count": hotkey_count},
                    "confidence": min(0.95, 0.6 + 0.1 * hotkey_count),
                }
            ]
        return []

    def _from_config(
        self,
        evidence: Evidence,
        body: dict[str, Any],
        raw: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if evidence.source_type != "MANUAL_CONFIG":
            return []
        key = str(raw.get("title") or body.get("key") or "")
        results: list[dict[str, Any]] = []

        compact = body.get("enabled")
        detail = body.get("detail_level") or body.get("style")
        if "output_style" in key or detail is not None or (
            "compact" in key and compact is not None
        ):
            value: dict[str, Any] = {}
            if compact is not None:
                value["enabled"] = bool(compact)
            if detail is not None:
                value["detail_level"] = detail
            if not value:
                value = dict(body)
            results.append(
                {
                    "category": "OUTPUT_STYLE",
                    "key": key if key.startswith("output_style") else "output_style.compact",
                    "value": value,
                    "confidence": 0.9,
                }
            )

        if "security" in key.lower() or body.get("no_exfiltrate") is not None:
            results.append(
                {
                    "category": "SECURITY_POLICY",
                    "key": key if key else "security.no_exfiltrate",
                    "value": dict(body) if body else {"no_exfiltrate": True},
                    "confidence": 0.92,
                }
            )
        return results

    def _from_security_signals(
        self,
        evidence: Evidence,
        body: dict[str, Any],
        raw: dict[str, Any],
    ) -> list[dict[str, Any]]:
        # Financial OCR → prefer not syncing finance outward
        items = body.get("items") if isinstance(body.get("items"), list) else []
        has_amount = any(
            isinstance(i, dict) and "amount" in i for i in items
        )
        if evidence.source_type == "OCR" and has_amount:
            return [
                {
                    "category": "SECURITY_POLICY",
                    "key": "security.finance_private",
                    "value": {"enabled": True, "scope_hint": "user"},
                    "confidence": 0.7,
                }
            ]
        # Explicit sensitivity already high on evidence
        if evidence.sensitivity >= 2:
            return [
                {
                    "category": "SECURITY_POLICY",
                    "key": "security.sensitive_filter",
                    "value": {"min_sensitivity": 2},
                    "confidence": 0.85,
                }
            ]
        _ = raw
        return []
