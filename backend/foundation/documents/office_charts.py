"""Keep native Word/PowerPoint chart data omitted by the main extractor.

The pinned Kreuzberg adapter owns document text and pictures. This supplement
preserves chart definitions (including cached values and labels) as inert model
input; it never evaluates formulas, opens embedded workbooks or follows links.
"""
import io
import zipfile
from xml.etree import ElementTree


def supplement_charts(document, data, prefix):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in sorted(archive.namelist()):
            if not name.startswith(prefix + "/charts/") or not name.endswith(".xml"):
                continue
            # Style/color parts describe appearance, not the chart's content.
            raw = archive.read(name)
            try:
                root = ElementTree.fromstring(raw)
            except ElementTree.ParseError:
                document.warnings.append(f"未能读取图表：{name}")
                continue
            if root.tag.rsplit("}", 1)[-1] != "chartSpace":
                continue
            # Retain hierarchy and attributes: flattening all numbers loses
            # category/series associations and turns axes into apparent facts.
            document.text(f"图表 {name}（原文缓存数据，公式未计算、链接未访问）",
                          ElementTree.tostring(root, encoding="unicode"))
