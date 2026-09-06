#!/usr/bin/env python3
"""Validate the offline rich-message renderer contract and bundled assets."""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
RENDERER = ROOT / "integrations/kylin_agent/message_renderer"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


html = (RENDERER / "index.html").read_text(encoding="utf-8")
readme = (RENDERER / "README.md").read_text(encoding="utf-8")

for asset in (
    "markdown-it.min.js",
    "katex.min.js",
    "katex.min.css",
    "markdown-it-texmath.js",
    "mermaid.min.js",
    "fonts/KaTeX_Main-Regular.woff2",
    "fonts/NotoColorEmoji.ttf",
    "licenses/LICENSE.markdown-it",
    "licenses/LICENSE.katex",
    "licenses/LICENSE.markdown-it-texmath",
    "licenses/LICENSE.mermaid",
    "licenses/LICENSE.noto-color-emoji",
):
    path = RENDERER / asset
    require(path.is_file() and path.stat().st_size > 0, f"renderer asset missing: {asset}")

for token in (
    "default-src 'none'",
    "html: false",
    "linkify: true",
    "breaks: true",
    "'mermaid', 'mindmap', 'flowchart', 'gantt'",
    "securityLevel: 'strict'",
    "window.structuredClone",
    "Object.hasOwn",
    "markdown.use(window.texmath",
    "delimiters: ['dollars', 'brackets', 'beg_end']",
    "throwOnError: false",
    "ResizeObserver",
    "pixiu-wheel:",
    "PIXIU Color Emoji",
    "text-align: start",
    "word-spacing: normal",
    "white-space: normal",
):
    require(token in html, f"renderer contract missing: {token}")

for version in (
    "markdown-it 14.1.0",
    "markdown-it-texmath 1.0.0",
    "KaTeX 0.16.22",
    "Mermaid 10.9.5",
):
    require(version in readme, f"renderer dependency version missing: {version}")

require("http://" not in html and "https://" not in html, "renderer must not load network resources")
require(
    (RENDERER / "fonts/NotoColorEmoji.ttf").stat().st_size > 10_000_000,
    "complete color emoji font is required",
)

body_rule = re.search(r"^\s*body\s*\{(?P<declarations>.*?)\}", html, re.DOTALL | re.MULTILINE)
require(body_rule is not None, "renderer body style is required")
body_style = body_rule.group("declarations")
text_font = body_style.find('"Noto Sans CJK SC"')
emoji_font = body_style.find('"PIXIU Color Emoji"')
require(text_font >= 0 and emoji_font >= 0, "renderer text and emoji fonts are required")
require(
    text_font < emoji_font,
    "text font must precede the color emoji fallback so ordinary spaces keep text metrics",
)
print("message renderer asset tests: OK")
