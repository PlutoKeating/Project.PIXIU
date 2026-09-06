#!/usr/bin/env python3
"""Render existing submission Markdown beside its PDF/DOCX, preserving headings.

Requires LibreOffice and requirements-docs.txt. No README or official source is
touched; temporary HTML and the LibreOffice profile stay outside the repository.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh_presentation(root: Path) -> dict:
    """Update reviewed text runs only; retain all slides, shapes and media."""
    path = root / "submission/01-项目报告/PIXIU项目报告.pptx"
    replacements = {
        ">0.1.7<": ">" + (root / "VERSION").read_text().strip() + "<",
        ">确认、级联清理、墓碑传播<": ">确认、隐藏知识、墓碑传播<",
        ">OCR<": ">OCR 文本<",
        ">Module E 809 <": ">Module E 823 <",
        ">量化指标为 <": ">历史量化基线：<",
    }
    with zipfile.ZipFile(path) as archive:
        entries = [(item, archive.read(item)) for item in archive.infolist()]
    with tempfile.TemporaryDirectory(prefix="pixiu-slides-export-") as temporary:
        generated = Path(temporary) / path.name
        with zipfile.ZipFile(generated, "w") as archive:
            for item, data in entries:
                if item.filename.startswith("ppt/slides/slide") and item.filename.endswith(".xml"):
                    content = data.decode("utf-8")
                    for old, new in replacements.items():
                        content = content.replace(old, new)
                    data = content.encode("utf-8")
                archive.writestr(item, data)
        shutil.copyfile(generated, path)
    return {"path": path.relative_to(root).as_posix(), "sha256": digest(path)}


def export(root: Path) -> list[dict]:
    import markdown

    records = []
    for source in sorted((root / "submission").rglob("*.md")):
        if source.name.lower() == "readme.md" or not source.with_suffix(".pdf").is_file():
            continue
        content = markdown.markdown(
            source.read_text(encoding="utf-8"), extensions=["tables", "fenced_code"]
        )
        with tempfile.TemporaryDirectory(prefix="pixiu-doc-export-") as temporary:
            work = Path(temporary)
            page = work / (source.stem + ".html")
            page.write_text(
                '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                f"<title>{html.escape(source.stem)}</title><style>"
                "@page {size:A4; margin:20mm}"
                "body {font-family:'Noto Sans CJK SC',sans-serif; font-size:11pt}"
                "h1,h2,h3,h4 {page-break-after:avoid}"
                "table {border-collapse:collapse; width:100%}"
                "th,td {border:1px solid #bbb; padding:5px; text-align:left}"
                "pre {white-space:pre-wrap; font-size:9pt}"
                "</style></head><body>" + content + "</body></html>",
                encoding="utf-8",
            )
            formats = ["pdf:writer_pdf_Export"]
            if source.with_suffix(".docx").is_file():
                formats.append("docx:Office Open XML Text")
            record = {"source": source.relative_to(root).as_posix(), "sha256": digest(source), "exports": []}
            for format_name in formats:
                subprocess.run(
                    ["libreoffice", "--headless", f"-env:UserInstallation={(work / 'profile').as_uri()}",
                     "--convert-to", format_name, "--outdir", str(work), str(page)],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=120, env={**os.environ, "SAL_USE_VCLPLUGIN": "svp"},
                )
                generated = page.with_suffix("." + format_name.split(":")[0])
                if not generated.is_file() or not generated.stat().st_size:
                    raise RuntimeError(f"LibreOffice produced no {format_name} for {source.name}")
                target = source.with_suffix(generated.suffix)
                shutil.copyfile(generated, target)
                record["exports"].append({"path": target.relative_to(root).as_posix(), "sha256": digest(target)})
            records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = root / "build/release/document-export-manifest.json"
    if args.check:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for record in data["documents"]:
            assert digest(root / record["source"]) == record["sha256"], record["source"]
            for item in record["exports"]:
                assert digest(root / item["path"]) == item["sha256"], item["path"]
        presentation = data["presentation"]
        assert digest(root / presentation["path"]) == presentation["sha256"]
        print("documentation source/export digests: OK")
    else:
        records = export(root)
        presentation = refresh_presentation(root)
        manifest.write_text(json.dumps({"schema": 1, "documents": records, "presentation": presentation}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Exported {len(records)} existing Markdown documents")


if __name__ == "__main__":
    main()
