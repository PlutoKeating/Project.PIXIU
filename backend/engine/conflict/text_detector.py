"""Text contradiction detection without online models.

Documents require: text fields use semantic similarity / antonymy, not
raw ``old != new``. This module is the extension point:

* ``TextConflictDetector`` — injectable protocol
* ``RuleBasedTextConflictDetector`` — default offline implementation
  (normalize + synonym canon + antonym / negation + token overlap)

A future embedding-backed detector can implement the same protocol and be
injected into Arbiter. Unit tests must not require the Kylin SDK.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Protocol

# Phrase → canonical form. Longest match first at runtime.
# General lexical knowledge, not acceptance-sample special cases.
_SYNONYM_CANON: dict[str, str] = {
    "喜欢": "偏好",
    "偏爱": "偏好",
    "倾向": "偏好",
    "偏好": "偏好",
    "likes": "prefer",
    "like": "prefer",
    "prefers": "prefer",
    "prefer": "prefer",
    "简洁": "简短",
    "精简": "简短",
    "简明": "简短",
    "简要": "简短",
    "简短": "简短",
    "concise": "brief",
    "short": "brief",
    "brief": "brief",
    "详尽": "详细",
    "细致": "详细",
    "详细": "详细",
    "verbose": "detailed",
    "thorough": "detailed",
    "detailed": "detailed",
    "回复": "回答",
    "应答": "回答",
    "回答": "回答",
    "replies": "answer",
    "reply": "answer",
    "answers": "answer",
    "answer": "answer",
    "开启": "打开",
    "启用": "打开",
    "打开": "打开",
    "关闭": "关掉",
    "禁用": "关掉",
    "关掉": "关掉",
}

# Antonym groups: any term in left vs any term in right is opposing.
_ANTONYM_GROUPS: tuple[tuple[frozenset[str], frozenset[str]], ...] = (
    (
        frozenset({"简短", "简洁", "精简", "简明", "简要", "brief", "concise"}),
        frozenset({"详细", "详尽", "细致", "冗长", "detailed", "verbose"}),
    ),
    (
        frozenset({"打开", "开启", "启用", "on", "enabled", "open"}),
        frozenset({"关掉", "关闭", "禁用", "off", "disabled", "closed"}),
    ),
    (
        frozenset({"允许", "许可", "同意", "allow", "permit", "agree"}),
        frozenset({"禁止", "拒绝", "不允许", "forbid", "deny", "reject"}),
    ),
    (frozenset({"多", "more", "many"}), frozenset({"少", "less", "few"})),
    (frozenset({"高", "high"}), frozenset({"低", "low"})),
    (frozenset({"大", "large", "big"}), frozenset({"小", "small"})),
    (frozenset({"快", "fast", "quick"}), frozenset({"慢", "slow"})),
    (frozenset({"是", "yes", "true"}), frozenset({"否", "no", "false"})),
)

_NEGATION_PHRASES: tuple[str, ...] = (
    "不是",
    "不要",
    "不会",
    "不能",
    "没有",
    "绝不",
    "并不",
    "不",
    "没",
    "非",
    "勿",
    "未",
    "无",
    "别",
    "not",
    "never",
    "no",
)

_PUNCT = re.compile(r"[，。！？、；：,.!?;:\"'“”‘’（）()\[\]【】·…—～~]+")
_SPACE = re.compile(r"\s+")

# After synonym canonicalization, treat as paraphrase if overlap is high.
_PARAPHRASE_JACCARD = 0.75


class TextConflictDetector(Protocol):
    def is_conflict(self, old_text: str, new_text: str) -> bool:
        """Return True only when the two strings truly contradict."""
        ...


class RuleBasedTextConflictDetector:
    """Offline rule detector: identity, paraphrase, antonym, negation."""

    def __init__(self, paraphrase_jaccard: float = _PARAPHRASE_JACCARD) -> None:
        self._paraphrase_jaccard = paraphrase_jaccard
        self._synonyms = tuple(
            sorted(_SYNONYM_CANON.items(), key=lambda kv: len(kv[0]), reverse=True)
        )
        self._negations = tuple(
            sorted(_NEGATION_PHRASES, key=len, reverse=True)
        )

    def is_conflict(self, old_text: str, new_text: str) -> bool:
        if old_text == new_text:
            return False
        old_c = self._canonicalize(old_text)
        new_c = self._canonicalize(new_text)
        if old_c == new_c:
            return False
        if not old_c or not new_c:
            return False
        if self._has_antonym_pair(old_c, new_c):
            return True
        if self._negation_mismatch(old_c, new_c):
            return True
        jaccard = self._jaccard(self._tokens(old_c), self._tokens(new_c))
        if jaccard >= self._paraphrase_jaccard:
            return False
        return False

    def _canonicalize(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text).strip().casefold()
        normalized = _PUNCT.sub("", normalized)
        normalized = _SPACE.sub("", normalized)
        for src, dst in self._synonyms:
            normalized = normalized.replace(src, dst)
        return normalized

    @staticmethod
    def _has_antonym_pair(left: str, right: str) -> bool:
        for pos, neg in _ANTONYM_GROUPS:
            left_pos = any(term in left for term in pos)
            left_neg = any(term in left for term in neg)
            right_pos = any(term in right for term in pos)
            right_neg = any(term in right for term in neg)
            if (left_pos and right_neg) or (left_neg and right_pos):
                return True
        return False

    def _negation_mismatch(self, left: str, right: str) -> bool:
        left_neg = self._has_negation(left)
        right_neg = self._has_negation(right)
        if left_neg == right_neg:
            return False
        stripped_left = self._strip_negation(left)
        stripped_right = self._strip_negation(right)
        if stripped_left == stripped_right:
            return True
        tokens_l = self._tokens(stripped_left)
        tokens_r = self._tokens(stripped_right)
        return self._jaccard(tokens_l, tokens_r) >= 0.5

    def _has_negation(self, text: str) -> bool:
        return any(neg in text for neg in self._negations)

    def _strip_negation(self, text: str) -> str:
        out = text
        for neg in self._negations:
            out = out.replace(neg, "")
        return out

    @staticmethod
    def _tokens(text: str) -> set[str]:
        if not text:
            return set()
        if len(text) == 1:
            return {text}
        return {text[i : i + 2] for i in range(len(text) - 1)}

    @staticmethod
    def _jaccard(left: set[str], right: set[str]) -> float:
        if not left and not right:
            return 1.0
        union = left | right
        if not union:
            return 1.0
        return len(left & right) / len(union)
