"""Preference extraction rules — data separate from Extractor execution.

Extractor only iterates rules; adding a rule does not change the core loop.
No LLM, no extra dependencies: keyword / field matching only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from backend.foundation.core.models import Evidence

Candidate = dict[str, Any]
RuleFn = Callable[[Evidence, dict[str, Any], dict[str, Any]], Optional[Candidate]]

VERBOSITY_KEY = "output_style.verbosity"
COMPACT = "compact"
VERBOSE = "verbose"

# Engineering lexicons, not a general NLP model.
COMPACT_TERMS: tuple[str, ...] = (
    "简洁",
    "简单",
    "简短",
    "精简",
    "简明",
    "compact",
    "brief",
    "concise",
    "short",
)
VERBOSE_TERMS: tuple[str, ...] = (
    "详细",
    "展开",
    "全面",
    "详尽",
    "细致",
    "verbose",
    "detailed",
    "thorough",
)

_HOTKEY_ACTIONS = frozenset({"hotkey", "shortcut"})


@dataclass(frozen=True)
class Rule:
    name: str
    category: str
    source_types: Optional[frozenset[str]]
    apply: RuleFn


def collect_text(evidence: Evidence, body: dict[str, Any], raw: dict[str, Any]) -> str:
    """Flatten likely user-facing strings for light lexical matching."""
    parts: list[str] = []
    for source in (raw, body):
        for field in ("title", "text", "summary", "key", "tool_name", "command"):
            value = source.get(field)
            if isinstance(value, str) and value.strip():
                parts.append(value)
    events = body.get("events")
    if isinstance(events, list):
        for event in events:
            if isinstance(event, dict):
                for field in ("text", "utterance", "command", "key", "action"):
                    value = event.get(field)
                    if isinstance(value, str) and value.strip():
                        parts.append(value)
            elif isinstance(event, str):
                parts.append(event)
    return " ".join(parts)


def match_verbosity(text: str) -> Optional[str]:
    """Return compact / verbose when only one polarity is present."""
    lowered = text.casefold()
    has_compact = any(term.casefold() in lowered for term in COMPACT_TERMS)
    has_verbose = any(term.casefold() in lowered for term in VERBOSE_TERMS)
    if has_compact and has_verbose:
        return None
    if has_compact:
        return COMPACT
    if has_verbose:
        return VERBOSE
    return None


def verbosity_candidate(verbosity: str, confidence: float) -> Candidate:
    return {
        "category": "OUTPUT_STYLE",
        "key": VERBOSITY_KEY,
        "value": {"verbosity": verbosity},
        "confidence": confidence,
    }


def is_opposite_verbosity(old_value: dict[str, Any], new_value: dict[str, Any]) -> bool:
    old_v = old_value.get("verbosity")
    new_v = new_value.get("verbosity")
    return {old_v, new_v} == {COMPACT, VERBOSE}


def _hotkey_count(body: dict[str, Any], raw: dict[str, Any]) -> int:
    events = body.get("events") or body.get("actions") or []
    count = 0
    if isinstance(events, list):
        for event in events:
            if isinstance(event, dict) and event.get("action") in _HOTKEY_ACTIONS:
                count += 1
    action = body.get("action") or raw.get("action")
    if action in _HOTKEY_ACTIONS:
        count += 1
    blob = " ".join(
        str(raw.get(field) or body.get(field) or "")
        for field in ("title", "tool_name", "text")
    ).casefold()
    if "hotkey" in blob or "shortcut" in blob:
        count = max(count, 1)
    return count


def _habit_from_hotkey(
    evidence: Evidence, body: dict[str, Any], raw: dict[str, Any]
) -> Optional[Candidate]:
    count = _hotkey_count(body, raw)
    if count < 1:
        return None
    return {
        "category": "OP_HABIT",
        "key": "op_habit.prefer_hotkey",
        "value": {"enabled": True, "signal_count": count},
        "confidence": min(0.95, 0.6 + 0.1 * count),
    }


def _style_from_config(
    evidence: Evidence, body: dict[str, Any], raw: dict[str, Any]
) -> Optional[Candidate]:
    key = str(raw.get("title") or body.get("key") or "")
    verbosity: Optional[str] = None
    detail = body.get("detail_level") or body.get("style")
    if detail is not None:
        verbosity = match_verbosity(str(detail))
        if verbosity is None:
            token = str(detail).strip().casefold()
            if token in {"high", "full", "verbose", "detailed"}:
                verbosity = VERBOSE
            elif token in {"low", "short", "compact", "brief"}:
                verbosity = COMPACT
    if verbosity is None:
        body_text = " ".join(
            str(body.get(field) or "")
            for field in ("text", "summary", "utterance")
        )
        verbosity = match_verbosity(body_text)
    if verbosity is None and (
        "output_style" in key.casefold()
        or "compact" in key.casefold()
        or "verbosity" in key.casefold()
    ):
        enabled = body.get("enabled")
        if enabled is True:
            verbosity = COMPACT
        elif enabled is False:
            verbosity = VERBOSE
    if verbosity is None:
        return None
    return verbosity_candidate(verbosity, 0.9)


def _style_from_text(
    evidence: Evidence, body: dict[str, Any], raw: dict[str, Any]
) -> Optional[Candidate]:
    verbosity = match_verbosity(collect_text(evidence, body, raw))
    if verbosity is None:
        return None
    return verbosity_candidate(verbosity, 0.75)


def _security_from_config(
    evidence: Evidence, body: dict[str, Any], raw: dict[str, Any]
) -> Optional[Candidate]:
    key = str(raw.get("title") or body.get("key") or "")
    if "security" not in key.casefold() and body.get("no_exfiltrate") is None:
        return None
    return {
        "category": "SECURITY_POLICY",
        "key": "security.no_exfiltrate" if not key else (
            key if key.startswith("security") else "security.no_exfiltrate"
        ),
        "value": dict(body) if body else {"no_exfiltrate": True},
        "confidence": 0.92,
    }


def _security_from_ocr_finance(
    evidence: Evidence, body: dict[str, Any], raw: dict[str, Any]
) -> Optional[Candidate]:
    items = body.get("items") if isinstance(body.get("items"), list) else []
    has_amount = any(isinstance(item, dict) and "amount" in item for item in items)
    if not has_amount:
        return None
    return {
        "category": "SECURITY_POLICY",
        "key": "security.finance_private",
        "value": {"enabled": True, "scope_hint": "user"},
        "confidence": 0.7,
    }


def _security_from_sensitivity(
    evidence: Evidence, body: dict[str, Any], raw: dict[str, Any]
) -> Optional[Candidate]:
    if evidence.sensitivity < 2:
        return None
    return {
        "category": "SECURITY_POLICY",
        "key": "security.sensitive_filter",
        "value": {"min_sensitivity": 2},
        "confidence": 0.85,
    }


OP_HABIT_RULES: tuple[Rule, ...] = (
    Rule(
        name="behavior_hotkey",
        category="OP_HABIT",
        source_types=frozenset({"USER_BEHAVIOR"}),
        apply=_habit_from_hotkey,
    ),
    Rule(
        name="tool_result_hotkey",
        category="OP_HABIT",
        source_types=frozenset({"TOOL_RESULT"}),
        apply=_habit_from_hotkey,
    ),
)

OUTPUT_STYLE_RULES: tuple[Rule, ...] = (
    Rule(
        name="manual_config_verbosity",
        category="OUTPUT_STYLE",
        source_types=frozenset({"MANUAL_CONFIG"}),
        apply=_style_from_config,
    ),
    Rule(
        name="text_verbosity",
        category="OUTPUT_STYLE",
        source_types=frozenset({"USER_BEHAVIOR", "TOOL_RESULT"}),
        apply=_style_from_text,
    ),
)

SECURITY_RULES: tuple[Rule, ...] = (
    Rule(
        name="manual_config_security",
        category="SECURITY_POLICY",
        source_types=frozenset({"MANUAL_CONFIG"}),
        apply=_security_from_config,
    ),
    Rule(
        name="ocr_finance_private",
        category="SECURITY_POLICY",
        source_types=frozenset({"OCR"}),
        apply=_security_from_ocr_finance,
    ),
    Rule(
        name="high_sensitivity",
        category="SECURITY_POLICY",
        source_types=None,
        apply=_security_from_sensitivity,
    ),
)


def default_rules() -> tuple[Rule, ...]:
    return OP_HABIT_RULES + OUTPUT_STYLE_RULES + SECURITY_RULES
