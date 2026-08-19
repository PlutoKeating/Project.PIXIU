"""Sensitive information detector — validated patterns + sensitivity 0~3."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from backend.engine.security.id_card import is_valid_id_card, iter_id_candidates
from backend.engine.security.luhn import passes_luhn

# Explicit digit boundaries (avoid unreliable \\b around CJK).
_PHONE_PATTERN = re.compile(r"(?<![0-9])1[3-9]\d{9}(?![0-9])")
_BANK_PATTERN = re.compile(r"(?<![0-9])(\d{16}|\d{19})(?![0-9])")

_TYPE_LABELS = {
    "id_card": "身份证",
    "bank_card": "银行卡",
    "phone": "手机号",
}

_SENSITIVITY_BY_TYPE = {
    "id_card": 3,
    "bank_card": 3,
    "phone": 2,
}


@dataclass(frozen=True)
class DetectionResult:
    score: int
    types: list[str]


class Detector:
    def detect(self, raw: dict[str, Any]) -> int:
        return self.detect_detail(raw).score

    def detect_detail(self, raw: dict[str, Any]) -> DetectionResult:
        text = json.dumps(raw, ensure_ascii=False, default=str)
        hits = self._find_types(text)
        if not hits:
            return DetectionResult(score=0, types=[])
        score = max(_SENSITIVITY_BY_TYPE[t] for t in hits)
        return DetectionResult(score=score, types=hits)

    def find_matches(self, raw: dict[str, Any]) -> list[str]:
        """Legacy Chinese labels for matched types."""
        detail = self.detect_detail(raw)
        return [_TYPE_LABELS[t] for t in detail.types]

    def _find_types(self, text: str) -> list[str]:
        found: list[str] = []
        if any(is_valid_id_card(value) for value in iter_id_candidates(text)):
            found.append("id_card")
        if self._has_valid_bank_card(text):
            found.append("bank_card")
        if _PHONE_PATTERN.search(text):
            found.append("phone")
        return found

    @staticmethod
    def _has_valid_bank_card(text: str) -> bool:
        for match in _BANK_PATTERN.finditer(text):
            if passes_luhn(match.group(1)):
                return True
        return False
