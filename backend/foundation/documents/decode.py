"""Format adapters; never execute macros, formulas, document links or model code."""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
import io
from pathlib import Path
import tempfile
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


def _extract(document: DecodedDocument, data: bytes, suffix: str):
    import kreuzberg as k

    # Only decode locally. PIXIU owns model selection, memory and image meaning.
    config = k.ExtractionConfig(
        use_cache=False, enable_quality_processing=False, disable_ocr=True,
        force_ocr=False, include_document_structure=True,
        images=k.ImageExtractionConfig(extract_images=True),
        pages=k.PageConfig(extract_pages=True),
        extraction_timeout_secs=60,
    )
    mime = MIME_TYPES[suffix]
    if suffix in {".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"}:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 20000 or sum(entry.file_size for entry in entries) > 100 * 1024 * 1024:
                raise ValueError("Document archive exceeds the supported size")
            for entry in entries:
                if "/embeddings/" in entry.filename:
                    document.warnings.append(f"嵌入对象需单独读取：{entry.filename}")
    try:
        extracted = k.extract_bytes_sync(data, mime, config)
    except k.KreuzbergError as exc:
        raise ValueError("Document decoding failed") from exc
    document.text("正文（含表格与备注）", extracted.content)
    document.warnings.extend(str(warning) for warning in (extracted.processing_warnings or []))
    image_pages = set()
    for index, item in enumerate(extracted.images or []):
        page = item.get("page_number")
        if page is not None:
            image_pages.add(page)
        if suffix != ".pdf":
            document.image(f"第 {page or '?'} 页/幻灯片，图片 {index + 1}", item["data"])
    if suffix == ".xlsx":
        from .spreadsheets import supplement_workbook
        supplement_workbook(document, data)
    if suffix == ".pdf":
        # Native PDFium is included in the wheel. No external executable, OCR,
        # office installation, network download or display server is involved.
        with tempfile.TemporaryDirectory(prefix="pixiu-document-") as directory:
            source = Path(directory) / "source.pdf"
            source.write_bytes(data)
            for page in extracted.pages or []:
                number = page["page_number"]
                if number in image_pages or not page.get("content", "").strip():
                    document.image(f"第 {number} 页完整图像", k.render_pdf_page(source, number - 1, dpi=144))


MIME_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".doc": "application/msword", ".xls": "application/vnd.ms-excel",
    ".ppt": "application/vnd.ms-powerpoint", ".pdf": "application/pdf",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation", ".rtf": "application/rtf",
}


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
    elif suffix in MIME_TYPES:
        _extract(result, data, suffix)
    elif suffix in {".png", ".jpg", ".jpeg"}:
        result.image("原图", data)
    else:
        result.warnings.append(f"尚未支持的文件格式：{suffix}")
    if not result.blocks and not result.warnings:
        result.warnings.append("未发现可读取内容")
    return result
