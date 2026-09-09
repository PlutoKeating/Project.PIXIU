"""Real fixtures from the pinned MIT-licensed document library; OCR stays off."""
from pathlib import Path
import hashlib

import pytest

from backend.foundation.documents import decode_document

FIXTURES = Path(__file__).resolve().parents[3] / "third_party/kreuzberg/test_documents"


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "gb18030"])
def test_large_text_preserves_every_character(encoding):
    original = "生活记录：买菜，水电费。\n" * 10000 + "全文最后的关键事实"
    result = decode_document(original.encode(encoding), "日记.txt")
    assert "".join(block.text for block in result.blocks) == original
    assert len(result.blocks) > 10
    assert len({block.id for block in result.blocks}) == len(result.blocks)
    assert not result.warnings


@pytest.mark.parametrize("filename, expected", [
    ("doc/unit_test_lists.doc", "List item 2"),
    ("ppt/simple.ppt", "Things to think about"),
    ("xls/tests_example.xls", "What is 2+2?"),
    ("xlsx/excel_multi_sheet.xlsx", "second_sheet"),
    ("docx/word_image_anchors.docx", "Transcript"),
    ("pptx/powerpoint_with_image.pptx", "Image test"),
])
def test_real_office_formats_are_read_without_external_office(filename, expected):
    path = FIXTURES / filename
    data = path.read_bytes()
    result = decode_document(data, path.name)
    assert expected in "\n".join(block.text for block in result.blocks)
    assert result.version == hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize("filename, count", [
    ("docx/word_image_anchors.docx", 3),
    ("pptx/powerpoint_with_image.pptx", 1),
])
def test_embedded_images_are_kept_for_current_model(filename, count):
    path = FIXTURES / filename
    result = decode_document(path.read_bytes(), path.name)
    images = [block for block in result.blocks if block.kind == "image"]
    assert len(images) == count
    assert all(block.mime_type and block.data_base64 and block.location for block in images)


def test_scanned_pdf_has_visual_pages_and_no_ocr_knowledge():
    path = FIXTURES / "pdf/image_only_german_pdf.pdf"
    result = decode_document(path.read_bytes(), path.name)
    assert result.blocks
    assert all(block.kind == "image" and not block.text for block in result.blocks)
    assert all("完整图像" in block.location for block in result.blocks)


def test_file_version_tracks_original_content():
    first = decode_document(b"first", "same.txt")
    second = decode_document(b"second", "same.txt")
    assert first.version != second.version
    assert first.version == decode_document(b"first", "renamed.txt").version
