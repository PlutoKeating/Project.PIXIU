"""ID card validation helpers (GB 11643 checksum + basic date)."""

from __future__ import annotations

import re
from datetime import datetime

_ID_CANDIDATE = re.compile(r"(?<![0-9Xx])(\d{17}[\dXx])(?![0-9Xx])")
_CHECK_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_CHECK_MAP = "10X98765432"


def iter_id_candidates(text: str) -> list[str]:
    return [m.group(1).upper() for m in _ID_CANDIDATE.finditer(text)]


def is_valid_id_card(value: str) -> bool:
    normalized = value.strip().upper()
    if len(normalized) != 18 or not normalized[:17].isdigit():
        return False
    if normalized[-1] not in "0123456789X":
        return False
    if not _valid_birth_date(normalized[6:14]):
        return False
    total = sum(int(normalized[i]) * _CHECK_WEIGHTS[i] for i in range(17))
    return _CHECK_MAP[total % 11] == normalized[-1]


def _valid_birth_date(yyyymmdd: str) -> bool:
    if len(yyyymmdd) != 8 or not yyyymmdd.isdigit():
        return False
    try:
        datetime.strptime(yyyymmdd, "%Y%m%d")
    except ValueError:
        return False
    return True
