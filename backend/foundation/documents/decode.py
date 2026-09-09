"""Format adapters; never execute macros, formulas, document links or model code."""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
import io
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile


@dataclass
class DocumentBlock:
    id: str
    location: str
    kind: str
    text: str = ""
    mime_type: str = ""
    data_base64: str = ""


@dataclass
class DecodedDocument:
    name: str
    version: str
    blocks: list[DocumentBlock] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def text(self, location: str, text: str):
        # Fixed size pages are an internal reading cursor, never a truncation rule.
        for offset in range(0, len(text), 6000):
            value = text[offset:offset+6000]
            if value.strip():
                self.blocks.append(DocumentBlock(f"block-{len(self.blocks)+1}", f"{location}:{offset}", "text", value))

    def image(self, location: str, data: bytes):
        mime = "image/png" if data.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg" if data.startswith(b"\xff\xd8\xff") else ""
        if mime:
            self.blocks.append(DocumentBlock(f"block-{len(self.blocks)+1}", location, "image",
                                             mime_type=mime, data_base64=base64.b64encode(data).decode()))
        else:
            self.warnings.append(f"未解析的图片/绘图：{location}")


def _xml(data: bytes):
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Document entity declarations are not permitted")
    return ET.fromstring(data)


def _tag(node):
    return node.tag.rsplit("}", 1)[-1]


def _office(document: DecodedDocument, data: bytes):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 20000 or sum(entry.file_size for entry in entries) > 100*1024*1024:
            raise ValueError("Document archive exceeds the supported size")
        names = set(archive.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            shared = ["".join(part.text or "" for part in node.iter() if _tag(part) == "t")
                      for node in _xml(archive.read("xl/sharedStrings.xml"))]
        for name in sorted(names):
            if "/media/" in name:
                document.image(name, archive.read(name)); continue
            if "/embeddings/" in name or name.lower().endswith("vbaproject.bin"):
                document.warnings.append(f"嵌入对象或宏未执行：{name}"); continue
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                sheet = _xml(archive.read(name))
                rows = []
                for cell in (node for node in sheet.iter() if _tag(node) == "c"):
                    values = [node.text or "" for node in cell if _tag(node) == "v"]
                    value = values[0] if values else ""; kind = cell.get("t")
                    if kind == "s" and value.isdigit():
                        index = int(value)
                        if index >= len(shared):
                            document.warnings.append(f"共享字符串缺失：{name}:{cell.get('r', '')}")
                        value = shared[index] if index < len(shared) else "[共享字符串缺失]"
                    if kind == "inlineStr":
                        value = "".join(node.text or "" for node in cell.iter() if _tag(node) == "t")
                    formula = next((node.text for node in cell if _tag(node) == "f"), None)
                    rows.append(f"{cell.get('r', '')}: {value}" + (f" [公式: {formula}]" if formula else ""))
                document.text(name, "\n".join(rows)); continue
            content_part = (name.startswith("word/") and re.search(r"/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml$", name)
                or name.startswith("ppt/slides/slide") and name.endswith(".xml")
                or name.startswith("ppt/notesSlides/notesSlide") and name.endswith(".xml")
                or name.startswith("xl/comments") and name.endswith(".xml")
                or "/charts/" in name and name.endswith(".xml")
                or "/diagrams/data" in name and name.endswith(".xml"))
            if content_part:
                root = _xml(archive.read(name)); lines = []
                for node in root.iter():
                    if _tag(node) in {"t", "v", "instrText"} and node.text:
                        lines.append(node.text)
                    elif _tag(node) in {"tab", "br"}:
                        lines.append("\t" if _tag(node) == "tab" else "\n")
                document.text(name, "\n".join(lines))
        if "xl/workbook.xml" in names:
            document.text("工作表目录", "\n".join(node.get("name", "") for node in _xml(archive.read("xl/workbook.xml")).iter() if _tag(node) == "sheet"))


def _pdf(document: DecodedDocument, data: bytes):
    with tempfile.TemporaryDirectory(prefix="pixiu-decode-") as directory:
        source = Path(directory)/"document.pdf"; source.write_bytes(data)
        def command(args, timeout=60):
            return subprocess.run(args, capture_output=True, check=True, timeout=timeout).stdout
        info = command(["pdfinfo", str(source)]).decode(errors="replace")
        match = re.search(r"^Pages:\s*(\d+)", info, re.MULTILINE)
        if not match or int(match[1]) > 200:
            raise ValueError("PDF page count unavailable or exceeds supported size")
        image_pages = set()
        listing = command(["pdfimages", "-list", str(source)]).decode(errors="replace")
        for line in listing.splitlines():
            fields = line.split()
            if len(fields) >= 3 and fields[0].isdigit(): image_pages.add(int(fields[0]))
        for page in range(1, int(match[1])+1):
            text = command(["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(source), "-"]).decode(errors="replace").strip()
            document.text(f"第 {page} 页", text)
            # Keep mixed visual/text pages as visuals too; text extraction alone
            # cannot represent photographs, diagrams or scanned areas.
            if page in image_pages or not text:
                output = Path(directory)/f"page-{page}"
                command(["pdftoppm", "-f", str(page), "-l", str(page), "-singlefile", "-scale-to", "1600", "-png", str(source), str(output)])
                document.image(f"第 {page} 页图像", output.with_suffix(".png").read_bytes())


def decode_document(data: bytes, name: str) -> DecodedDocument:
    if len(data) > 30*1024*1024:
        raise ValueError("Document exceeds supported size")
    result = DecodedDocument(Path(name).name, hashlib.sha256(data).hexdigest())
    suffix = Path(name).suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json", ".log"}:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "gb18030")
            except UnicodeDecodeError as exc:
                raise ValueError("无法完整解码文本文件") from exc
        result.text("正文", text)
    elif suffix in {".docx", ".xlsx", ".pptx"}:
        _office(result, data)
    elif suffix == ".pdf":
        _pdf(result, data)
    elif suffix in {".png", ".jpg", ".jpeg"}:
        result.image("原图", data)
    else:
        result.warnings.append(f"尚未支持的文件格式：{suffix}")
    if not result.blocks and not result.warnings:
        result.warnings.append("未发现可读取内容")
    return result
