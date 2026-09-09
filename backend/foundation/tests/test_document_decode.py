"""Real format fixtures: preserve content and report incomplete decoding."""
import base64
import io
import zipfile

import pytest

from backend.foundation.documents import decode_document


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXioAAAAASUVORK5CYII="
)


def office(parts):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return output.getvalue()


def text(document):
    return "\n".join(block.text for block in document.blocks if block.kind == "text")


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "gb18030"])
def test_large_text_preserves_every_character(encoding):
    original = "生活记录：买菜，水电费。\n" * 10000 + "全文最后的关键事实"
    result = decode_document(original.encode(encoding), "日记.txt")
    assert "".join(block.text for block in result.blocks) == original
    assert len(result.blocks) > 10
    assert len({block.id for block in result.blocks}) == len(result.blocks)
    assert not result.warnings


def test_docx_preserves_body_table_notes_and_images():
    data = office({
        "word/document.xml": '<document><p><t>项目报告</t></p><tbl><tr><tc><t>金额</t></tc><tc><t>45</t></tc></tr></tbl></document>',
        "word/header1.xml": "<hdr><t>页眉</t></hdr>",
        "word/footnotes.xml": "<footnotes><t>核对说明</t></footnotes>",
        "word/media/image1.png": PNG,
    })
    result = decode_document(data, "报告.docx")
    for value in ["项目报告", "金额", "45", "页眉", "核对说明"]:
        assert value in text(result)
    images = [block for block in result.blocks if block.kind == "image"]
    assert len(images) == 1
    assert base64.b64decode(images[0].data_base64) == PNG
    assert images[0].location == "word/media/image1.png"
    assert not result.warnings


def test_xlsx_preserves_cells_formula_cached_result_comments_and_images():
    data = office({
        "xl/sharedStrings.xml": "<sst><si><t>电费</t></si></sst>",
        "xl/workbook.xml": '<workbook><sheets><sheet name="家庭开支"/></sheets></workbook>',
        "xl/worksheets/sheet1.xml": '<worksheet><row><c r="A1" t="s"><v>0</v></c><c r="B1"><f>20+30</f><v>50</v></c><c r="C1" t="inlineStr"><is><t>已支付</t></is></c></row></worksheet>',
        "xl/comments1.xml": "<comments><comment><text><t>需报销</t></text></comment></comments>",
        "xl/media/image1.png": PNG,
    })
    result = decode_document(data, "账单.xlsx")
    for value in ["A1: 电费", "B1: 50 [公式: 20+30]", "C1: 已支付", "需报销", "家庭开支"]:
        assert value in text(result)
    assert any(block.kind == "image" for block in result.blocks)


def test_pptx_includes_speaker_notes_and_visuals():
    result = decode_document(office({
        "ppt/slides/slide1.xml": "<slide><t>下一步工作</t></slide>",
        "ppt/notesSlides/notesSlide1.xml": "<notes><t>周五交付</t></notes>",
        "ppt/media/image1.png": PNG,
    }), "工作.pptx")
    assert "下一步工作" in text(result) and "周五交付" in text(result)
    assert any(block.kind == "image" for block in result.blocks)


def test_unsupported_embedded_objects_are_not_silently_dropped():
    result = decode_document(office({
        "word/document.xml": "<document><t>正文</t></document>",
        "word/embeddings/oleObject1.bin": b"opaque",
        "word/media/image1.emf": b"unsupported drawing",
    }), "嵌入.docx")
    assert len(result.warnings) == 2
    assert "正文" in text(result)


def test_external_xml_entities_are_rejected():
    data = office({"word/document.xml": '<!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/passwd">]><d>&x;</d>'})
    with pytest.raises(ValueError, match="entity"):
        decode_document(data, "malicious.docx")


def test_missing_spreadsheet_string_marks_incomplete():
    result = decode_document(office({
        "xl/worksheets/sheet1.xml": '<sheet><c r="A1" t="s"><v>99</v></c></sheet>',
    }), "损坏.xlsx")
    assert result.warnings and "A1" in result.warnings[0]


def test_file_version_tracks_original_content():
    first = decode_document(b"first", "same.txt")
    second = decode_document(b"second", "same.txt")
    assert first.version != second.version
    assert first.version == decode_document(b"first", "renamed.txt").version


def test_legacy_office_is_explicitly_incomplete_until_converter_is_connected():
    result = decode_document(b"legacy", "old.doc")
    assert not result.blocks and result.warnings
