"""Turn readable bill lines into an editable draft; never persist OCR guesses."""
from __future__ import annotations

import re


def expense_draft(text: str) -> list[dict]:
    items = []
    current_date = ""
    for line in text.splitlines():
        date = re.search(r"(20\d{2})[年/.-](\d{1,2})(?:[月/.-](\d{1,2}))?", line)
        if date:
            current_date = f"{date[1]}-{int(date[2]):02d}-{int(date[3] or 1):02d}"
            line = line[:date.start()] + line[date.end():]
        if any(word in line for word in ("合计", "总计", "总额", "TOTAL")):
            continue
        match = re.search(r"(?:[¥￥]\s*)?(-?\d+(?:\.\d{1,2})?)\s*(?:元|RMB|CNY)?\s*$", line)
        if not match:
            continue
        label = line[:match.start()].strip(" \t:：,，|日月")
        if not label or not re.search(r"[A-Za-z\u4e00-\u9fff]", label):
            continue
        category = next((category for words, category in (
            (("燃气", "电费", "水费"), "水电燃气"),
            (("餐", "饭", "食品"), "餐饮"),
            (("公交", "地铁", "打车", "交通"), "交通"),
            (("超市", "购物"), "购物"),
        ) if any(word in label for word in words)), "其他")
        items.append({"date": current_date, "category": category,
                      "vendor": label, "amount": float(match[1])})
    return items
