#!/usr/bin/env python3
"""Verify the downstream KylinAgent palette keeps normal text at WCAG AA contrast."""

from __future__ import annotations

import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATCHES = (
    ROOT / "build/release/agent-host/patches/0002-pixiu-premium-accessible-ui.patch",
    ROOT / "build/release/agent-host/patches/0004-working-agent-experience.patch",
)


def relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else math.pow((value + 0.055) / 1.055, 2.4)
              for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def require_pair(name: str, foreground: str, background: str, minimum: float = 4.5) -> None:
    ratio = contrast(foreground, background)
    if ratio < minimum:
        raise AssertionError(
            f"{name} contrast {ratio:.2f}:1 is below {minimum:.1f}:1 "
            f"({foreground} on {background})"
        )


source = "\n".join(path.read_text(encoding="utf-8") for path in PATCHES)
colors = set(re.findall(r"#[0-9a-fA-F]{6}", source))
required_colors = {
    "#172033", "#5b6474", "#ffffff", "#f6f7f9", "#147d78", "#e3f4f1",
    "#f3f6f8", "#abb6c3", "#96a3b2", "#171c22", "#101418", "#1d5f5b", "#55c8be",
}
missing = required_colors - colors
if missing:
    raise AssertionError(f"expected palette colors missing from UI patch: {sorted(missing)}")

for args in (
    ("light primary text", "#172033", "#ffffff"),
    ("light secondary text", "#5b6474", "#ffffff"),
    ("light primary button", "#ffffff", "#147d78"),
    ("light user bubble", "#172033", "#e3f4f1"),
    ("dark primary text", "#f3f6f8", "#171c22"),
    ("dark secondary text", "#abb6c3", "#171c22"),
    ("dark placeholder", "#96a3b2", "#171c22"),
    ("dark user bubble", "#f3f6f8", "#1d5f5b"),
    ("dark accent", "#55c8be", "#101418"),
):
    require_pair(*args)

print("agent host UI contrast tests: OK")
