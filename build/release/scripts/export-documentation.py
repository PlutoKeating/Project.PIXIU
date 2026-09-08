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
import re
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from xml.dom import minidom
import zipfile
from urllib.parse import unquote, urlsplit


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_images(content: str, source: Path, root: Path) -> tuple[str, list[dict]]:
    """Resolve reviewed PNGs before moving HTML into the temporary directory."""
    records = []

    def replace(match: re.Match) -> str:
        address = html.unescape(match.group(1))
        if urlsplit(address).scheme or address.startswith("//"):
            raise ValueError(f"Use repository PNG images in {source.name}: {address}")
        path = (source.parent / unquote(address)).resolve()
        relative = path.relative_to(root)
        data = path.read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"Expected a PNG screenshot: {relative}")
        width, height = struct.unpack(">II", data[16:24])
        display_width = min(width, 640)
        display_height = round(height * display_width / width)
        records.append({"path": relative.as_posix(), "sha256": digest(path)})
        tag = match.group(0)
        tag = re.sub(r'src="[^"]*"', 'src="' + path.as_uri() + '"', tag)
        return tag.replace("<img ", f'<img width="{display_width}" height="{display_height}" ')

    content = re.sub(r'<img\b[^>]*\bsrc="([^"]+)"[^>]*>', replace, content)
    # Writer can place a tall inline image above the next page's top margin.
    # Start each screenshot on its own page and keep its caption immediately after.
    content = re.sub(r'<p>(<img\b[^>]*>)</p>',
                     r'<p style="page-break-before:always;page-break-after:avoid">\1</p>', content)
    return content, records


def embed_word_images(path: Path, root: Path) -> None:
    """Make LibreOffice's linked HTML pictures portable inside the DOCX."""
    with zipfile.ZipFile(path) as archive:
        entries = {item.filename: archive.read(item) for item in archive.infolist()}
    rel_path = "word/_rels/document.xml.rels"
    relationships = ET.fromstring(entries[rel_path])
    embedded_ids = set()
    for relationship in relationships:
        if not relationship.get("Type", "").endswith("/image"):
            continue
        if relationship.get("TargetMode") != "External":
            continue
        address = urlsplit(relationship.attrib["Target"])
        if address.scheme != "file" or address.netloc:
            raise ValueError("Word image must come from a local repository file")
        source = Path(unquote(address.path)).resolve()
        source.relative_to(root)
        data = source.read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Word image must be a PNG")
        name = "media/pixiu-" + digest(source) + ".png"
        entries["word/" + name] = data
        relationship.set("Target", name)
        del relationship.attrib["TargetMode"]
        embedded_ids.add(relationship.attrib["Id"])
    if not embedded_ids:
        return
    # Preserve namespace declarations used by Word's mc:Ignorable attribute.
    document = minidom.parseString(entries["word/document.xml"])
    namespace = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    for node in document.getElementsByTagNameNS("*", "blip"):
        linked_id = node.getAttributeNS(namespace, "link")
        if linked_id in embedded_ids:
            node.removeAttributeNS(namespace, "link")
            node.setAttributeNS(namespace, "r:embed", linked_id)
    types = ET.fromstring(entries["[Content_Types].xml"])
    if not any(item.get("Extension") == "png" for item in types):
        ET.SubElement(types, "{http://schemas.openxmlformats.org/package/2006/content-types}Default",
                      {"Extension": "png", "ContentType": "image/png"})
    entries["word/document.xml"] = document.toxml(encoding="utf-8")
    for name, element in [(rel_path, relationships), ("[Content_Types].xml", types)]:
        # LibreOffice's package detector expects the original default namespace.
        ET.register_namespace("", element.tag.split("}", 1)[0][1:])
        entries[name] = ET.tostring(element, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


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
        content, images = prepare_images(content, source, root)
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
                "img {max-width:100%; height:auto; page-break-inside:avoid}"
                "</style></head><body>" + content + "</body></html>",
                encoding="utf-8",
            )
            formats = ["pdf:writer_pdf_Export"]
            if source.with_suffix(".docx").is_file():
                formats.append("docx:Office Open XML Text")
            record = {"source": source.relative_to(root).as_posix(), "sha256": digest(source), "images": images, "exports": []}
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
                if generated.suffix == ".docx":
                    embed_word_images(generated, root)
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
            for item in record.get("images", []):
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
