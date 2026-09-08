#!/usr/bin/env python3
"""Outline our concept diagrams with bundled Chinese fonts for stable rendering.

These are labeled explanatory diagrams, never reconstructed product screens.
Editable text originals remain under raw/concept.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
fonts = {
    weight: TTFont(ROOT / 'public/fonts' / f'NotoSansCJKsc-{name}.otf')
    for weight, name in [('400', 'Regular'), ('700', 'Bold')]
}
for source in sorted((ROOT / 'raw/concept').glob('*.svg')):
    tree = ET.parse(source)
    for parent in tree.iter():
        for node in list(parent):
            if node.tag != f'{{{NS}}}text':
                continue
            font = fonts[node.get('font-weight', '400')]
            glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
            scale = float(node.get('font-size', '24')) / font['head'].unitsPerEm
            x, y = float(node.get('x', '0')), float(node.get('y', '0'))
            group = ET.Element(f'{{{NS}}}g', {'fill': node.get('fill', '#172033')})
            for char in node.text or '':
                glyph = glyphs[cmap[ord(char)]]
                pen = SVGPathPen(glyphs)
                glyph.draw(TransformPen(pen, (scale, 0, 0, -scale, x, y)))
                ET.SubElement(group, f'{{{NS}}}path', {'d': pen.getCommands()})
                x += glyph.width * scale
            parent.insert(list(parent).index(node), group)
            parent.remove(node)
    tree.write(ROOT / 'public/concept' / source.name, encoding='unicode')
    print(source.name)
