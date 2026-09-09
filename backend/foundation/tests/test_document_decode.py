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


def test_workbook_keeps_formula_comment_chart_and_embedded_image():
    import io
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, Reference
    from openpyxl.comments import Comment
    from openpyxl.drawing.image import Image
    from PIL import Image as Raster

    book = Workbook()
    sheet = book.active
    sheet.title = "家庭开支"
    sheet.append(["项目", "金额"])
    sheet.append(["电费", 50])
    sheet.append(["燃气费", 30])
    sheet["B4"] = "=SUM(B2:B3)"
    sheet["B4"].comment = Comment("家庭能源支出合计", "用户")
    image = io.BytesIO()
    Raster.new("RGB", (12, 12), "blue").save(image, format="PNG")
    sheet.add_image(Image(image), "D2")
    chart = BarChart()
    chart.title = "能源开支比较"
    chart.add_data(Reference(sheet, min_col=2, min_row=1, max_row=3), titles_from_data=True)
    sheet.add_chart(chart, "F2")
    source = io.BytesIO()
    book.save(source)
    result = decode_document(source.getvalue(), "开支.xlsx")
    text = "\n".join(block.text for block in result.blocks)
    assert "=SUM(B2:B3)" in text and "家庭能源支出合计" in text
    assert "能源开支比较" in text and "$B$2:$B$3" in text
    images = [block for block in result.blocks if block.kind == "image"]
    assert len(images) == 1 and "家庭开支" in images[0].location
    assert not result.warnings


@pytest.mark.parametrize("kind,suffix", [("WEBP", ".webp"), ("BMP", ".bmp"), ("TIFF", ".tiff"), ("GIF", ".gif")])
def test_common_images_are_decoded_to_model_supported_content(kind, suffix):
    import io
    import base64
    from PIL import Image
    output = io.BytesIO()
    Image.new("RGB", (24, 16), "red").save(output, format=kind)
    document = decode_document(output.getvalue(), "资料" + suffix)
    assert not document.warnings
    assert len(document.blocks) == 1
    image = Image.open(io.BytesIO(base64.b64decode(document.blocks[0].data_base64)))
    assert image.size == (24, 16)
    assert image.convert("RGB").getpixel((0, 0))[0] > 240


def test_multipage_image_keeps_each_page():
    import io
    import base64
    from PIL import Image
    output = io.BytesIO()
    Image.new("RGB", (12, 12), "red").save(output, format="TIFF", save_all=True,
        append_images=[Image.new("RGB", (12, 12), "blue")])
    document = decode_document(output.getvalue(), "扫描件.tiff")
    assert not document.warnings and len(document.blocks) == 2
    colors = [Image.open(io.BytesIO(base64.b64decode(block.data_base64))).getpixel((0, 0))
              for block in document.blocks]
    assert colors == [(255, 0, 0), (0, 0, 255)]
    assert document.blocks[0].location != document.blocks[1].location


def test_corrupt_image_is_not_reported_as_readable():
    document = decode_document(b"\x89PNG\r\n\x1a\nnot-an-image", "bad.png")
    assert not document.blocks and document.warnings
