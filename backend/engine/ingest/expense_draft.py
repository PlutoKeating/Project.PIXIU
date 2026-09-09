"""Preserve structured bill details during explicit user corrections."""
from __future__ import annotations

import re


def correct_expense_body(existing: dict, content: str) -> dict:
    """Apply one explicit amount correction without dropping other bill lines."""
    import copy
    match = re.search(r"(?:改为|改成|更正为|调整为|应为|(?<!不)是|to)\s*[¥￥]?\s*(\d+(?:\.\d{1,2})?)\s*(?:元)?", content)
    if not match:
        raise ValueError("Specify the bill item and its corrected amount")
    candidates = []
    for index, item in enumerate(existing.get("items", [])):
        vendor = str(item.get("vendor") or "")
        if vendor and vendor in content:
            candidates.append(index)
        elif any(word in vendor and word in content for word in ("燃气", "电费", "水费")):
            candidates.append(index)
    if len(candidates) != 1:
        raise ValueError("Choose one bill item to correct")
    updated = copy.deepcopy(existing)
    updated["items"][candidates[0]]["amount"] = float(match[1])
    updated["text"] = content
    updated["correction"] = content
    return updated
