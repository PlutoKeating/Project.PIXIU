#!/usr/bin/env python3
"""Assemble the technical manuscript and export the two competition documents.

Requires LibreOffice and requirements-docs.txt. Intermediate files stay in out/.
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
from submission_layout import paths


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


def assemble(root: Path) -> Path:
    directory = root / "docs/delivery"
    names = ["TECHNICAL_SOLUTION", "DEPLOYMENT_GUIDE", "USER_MANUAL",
             "MEMORY_LIFECYCLE", "APPLICATION_CASES", "TEST_REPORT",
             "KYLIN_V11_ADAPTATION_REPORT", "SOURCE_AND_LICENSES"]
    body = ["# PIXIU 技术方案\n\n版本：" + (root / "VERSION").read_text().strip()
            + "\n\n平台：银河麒麟桌面操作系统 V11\n"]
    for name in names:
        content = (directory / (name + ".md")).read_text()
        body.append(re.sub(r"^(#{1,5}) ", r"#\1 ", content, flags=re.M))
    source = directory / "COMBINED_TECHNICAL.md"
    source.write_text("\n\n".join(body))
    return source


def convert(source: Path, output: Path, format_name: str, profile: Path) -> Path:
    subprocess.run(
        ["libreoffice", "--headless", f"-env:UserInstallation={profile.as_uri()}",
         "--convert-to", format_name, "--outdir", str(output), str(source)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
        env={**os.environ, "SAL_USE_VCLPLUGIN": "svp"},
    )
    generated = output / (source.stem + "." + format_name.split(":")[0])
    if not generated.is_file() or not generated.stat().st_size:
        raise RuntimeError("LibreOffice 未生成文档：" + format_name)
    return generated


def export(root: Path) -> tuple[list[dict], dict]:
    import markdown
    source = assemble(root)
    _, materials, _ = paths(root)
    materials.mkdir(parents=True, exist_ok=True)
    output = root / "build/release/out/documents"
    output.mkdir(parents=True, exist_ok=True)
    content = markdown.markdown(source.read_text(), extensions=["tables", "fenced_code"])
    content, images = prepare_images(content, source, root)
    # A submitted document must not depend on internal manuscript hyperlinks.
    content = re.sub(r'<a href="(?!https?://)[^"]*">(.*?)</a>', r"\1", content)
    with tempfile.TemporaryDirectory(prefix="pixiu-doc-export-") as temporary:
        work = Path(temporary)
        page = work / "技术方案.html"
        page.write_text(
            '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<title>PIXIU 技术方案</title><style>'
            '@page {size:A4; margin:20mm}'
            "body {font-family:'Noto Sans CJK SC',sans-serif; font-size:11pt}"
            'h1,h2,h3,h4 {page-break-after:avoid}'
            'table {border-collapse:collapse; width:100%}'
            'th,td {border:1px solid #bbb; padding:5px; text-align:left}'
            'pre {white-space:pre-wrap; font-size:9pt}'
            'img {max-width:100%; height:auto; page-break-inside:avoid}'
            '</style></head><body>' + content + '</body></html>')
        docx = convert(page, output, "docx:Office Open XML Text", work / "profile")
        embed_word_images(docx, root)
        doc = convert(docx, materials, "doc:MS Word 97", work / "profile")
        # Inspect the actual delivered binary document, not only the intermediate.
        pdf = convert(doc, output, "pdf:writer_pdf_Export", work / "profile")
    template = root / "docs/delivery/assets/项目报告.pptx"
    ppt = materials / "项目报告.pptx"
    shutil.copyfile(template, ppt)
    record = {"source": source.relative_to(root).as_posix(), "sha256": digest(source),
              "inputs": [{"path": p.relative_to(root).as_posix(), "sha256": digest(p)} for p in sorted((root / "docs/delivery").glob("*.md")) if p.name in {"TECHNICAL_SOLUTION.md", "DEPLOYMENT_GUIDE.md", "USER_MANUAL.md", "MEMORY_LIFECYCLE.md", "APPLICATION_CASES.md", "TEST_REPORT.md", "KYLIN_V11_ADAPTATION_REPORT.md", "SOURCE_AND_LICENSES.md"}],
              "images": images, "exports": [{"path": doc.relative_to(root).as_posix(), "sha256": digest(doc)}]}
    presentation = {"source": template.relative_to(root).as_posix(), "path": ppt.relative_to(root).as_posix(), "sha256": digest(ppt)}
    return [record], presentation


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
            for item in record.get("images", []) + record.get("inputs", []):
                assert digest(root / item["path"]) == item["sha256"], item["path"]
        presentation = data["presentation"]
        assert digest(root / presentation["path"]) == presentation["sha256"]
        assert digest(root / presentation["source"]) == presentation["sha256"]
        print("documentation source/export digests: OK")
    else:
        records, presentation = export(root)
        manifest.write_text(json.dumps({"schema": 1, "documents": records, "presentation": presentation}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("已导出项目报告.pptx 和技术方案.doc；复核 PDF 位于 build/release/out/documents")


if __name__ == "__main__":
    main()
