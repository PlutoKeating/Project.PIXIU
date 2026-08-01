"""Sensitive information detector — regex rules + sensitivity score 0~3."""

from __future__ import annotations

import json
import re
from typing import Any


_PATTERNS: dict[str, re.Pattern[str]] = {
    "身份证": re.compile(r"\b\d{17}[\dXx]\b"),
    "银行卡": re.compile(r"\b\d{16}\b|\b\d{19}\b"),
    "手机号": re.compile(r"\b1[3-9]\d{9}\b"),
}


class Detector:
    def detect(self, raw: dict[str, Any]) -> int:
        """Return sensitivity score: 0=none, 1=low, 2=mid, 3=high."""
        text = json.dumps(raw, ensure_ascii=False, default=str)
        hits = [name for name, pat in _PATTERNS.items() if pat.search(text)]
        if not hits:
            return 0
        if "身份证" in hits or "银行卡" in hits:
            return 3
        if "手机号" in hits:
            return 2
        return 1

    def find_matches(self, raw: dict[str, Any]) -> list[str]:
        text = json.dumps(raw, ensure_ascii=False, default=str)
        return [name for name, pat in _PATTERNS.items() if pat.search(text)]
