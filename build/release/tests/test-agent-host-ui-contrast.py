#!/usr/bin/env python3
"""Verify the downstream KylinAgent palette keeps normal text at WCAG AA contrast."""

from __future__ import annotations

import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATCH = ROOT / "build/release/agent-host/patches/0002-pixiu-premium-accessible-ui.patch"


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


source = PATCH.read_text(encoding="utf-8")
colors = set(re.findall(r"#[0-9a-fA-F]{6}", source))
required_colors = {
    "#132238", "#526477", "#627587", "#ffffff", "#f4f7fb", "#066a75", "#087f8c",
    "#edf5f7", "#a9bbc5", "#93a8b3", "#111a23", "#0b1117", "#167d80", "#41d3c4",
}
missing = required_colors - colors
if missing:
    raise AssertionError(f"expected palette colors missing from UI patch: {sorted(missing)}")

for args in (
    ("light primary text", "#132238", "#ffffff"),
    ("light secondary text", "#526477", "#ffffff"),
    ("light placeholder", "#627587", "#ffffff"),
    ("light primary button", "#ffffff", "#066a75"),
    ("light user bubble", "#ffffff", "#087f8c"),
    ("dark primary text", "#edf5f7", "#111a23"),
    ("dark secondary text", "#a9bbc5", "#111a23"),
    ("dark placeholder", "#93a8b3", "#111a23"),
    ("dark user bubble", "#ffffff", "#167d80"),
    ("dark accent", "#41d3c4", "#0b1117"),
):
    require_pair(*args)

print("agent host UI contrast tests: OK")
