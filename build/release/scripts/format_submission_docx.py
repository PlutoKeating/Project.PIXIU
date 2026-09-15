"""Normalize anonymous DOCX metadata, plain lists and terminal examples."""
from pathlib import Path
from xml.dom import minidom
import zipfile

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def format_document(path: Path) -> None:
    with zipfile.ZipFile(path) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    d = minidom.parseString(entries['word/document.xml'])

    def child(parent, name, **attrs):
        found = [c for c in parent.childNodes if c.nodeType == c.ELEMENT_NODE and c.localName == name]
        node = found[0] if found else d.createElementNS(W, 'w:' + name)
        if not found:
            parent.appendChild(node)
        for key, val in attrs.items():
            node.setAttributeNS(W, 'w:' + key, str(val))
        return node

    def text(p):
        return ''.join(n.firstChild.data for n in p.getElementsByTagNameNS(W, 't') if n.firstChild)

    def is_code(p):
        if p.nodeType != p.ELEMENT_NODE or p.localName != 'p':
            return False
        return any(s.getAttributeNS(W, 'val') == 'PreformattedText' for s in p.getElementsByTagNameNS(W, 'pStyle'))

    body = d.getElementsByTagNameNS(W, 'body')[0]
    nodes = list(body.childNodes)
    i = 0
    while i < len(nodes):
        if not is_code(nodes[i]):
            i += 1
            continue
        group = []
        while i < len(nodes) and is_code(nodes[i]):
            group.append(nodes[i]); i += 1
        table = d.createElementNS(W, 'w:tbl')
        body.insertBefore(table, group[0])
        props = child(table, 'tblPr')
        child(props, 'tblW', w=9600, type='dxa')
        child(props, 'tblLayout', type='fixed')
        borders = child(props, 'tblBorders')
        for side in ('top', 'left', 'bottom', 'right'):
            child(borders, side, val='single', sz=8, color='000000')
        margins = child(props, 'tblCellMar')
        for side in ('top', 'left', 'bottom', 'right'):
            child(margins, side, w=140, type='dxa')
        child(child(table, 'tblGrid'), 'gridCol', w=9600)
        row = child(table, 'tr')
        child(child(row, 'trPr'), 'cantSplit')
        cell = child(row, 'tc')
        cp = child(cell, 'tcPr')
        child(cp, 'tcW', w=9600, type='dxa')
        child(cp, 'shd', val='clear', color='auto', fill='18212B')
        continued = False
        for p in group:
            original = text(p)
            prompt = '> ' if continued else '$ '
            continued = original.rstrip().endswith('\\')
            pp = child(p, 'pPr')
            child(pp, 'spacing', before=0, after=40, line=240, lineRule='auto')
            child(pp, 'ind', left=0, right=0, firstLine=0)
            child(pp, 'shd', val='clear', color='auto', fill='18212B')
            run = d.createElementNS(W, 'w:r')
            t = child(run, 't'); t.setAttribute('xml:space', 'preserve');t.appendChild(d.createTextNode(prompt))
            p.insertBefore(run, pp.nextSibling)
            for r in p.getElementsByTagNameNS(W, 'r'):
                rp = child(r, 'rPr')
                if r.firstChild is not rp:
                    r.insertBefore(rp, r.firstChild)
                child(rp, 'rFonts', ascii='DejaVu Sans Mono', hAnsi='DejaVu Sans Mono', eastAsia='Noto Sans CJK SC')
                child(rp, 'color', val='E6EDF3')
                child(rp, 'sz', val=18);child(rp, 'szCs', val=18)
            cell.appendChild(p)
    # Writer merges directly adjacent tables on import; keep terminal examples
    # separate from preceding data tables with a minimal paragraph boundary.
    for table in list(body.childNodes):
        if table.nodeType == table.ELEMENT_NODE and table.localName == 'tbl':
            previous = table.previousSibling
            if previous is not None and previous.nodeType == previous.ELEMENT_NODE and previous.localName == 'tbl':
                gap = d.createElementNS(W, 'w:p')
                child(child(gap, 'pPr'), 'spacing', before=0, after=0, line=40, lineRule='exact')
                body.insertBefore(gap, table)
    entries['word/document.xml'] = d.toxml(encoding='utf-8')
    # Symbol-font bullets are rendered as emoji by some office applications.
    if 'word/numbering.xml' in entries:
        n = minidom.parseString(entries['word/numbering.xml'])
        for level in n.getElementsByTagNameNS(W, 'lvl'):
            formats = level.getElementsByTagNameNS(W, 'numFmt')
            if formats and formats[0].getAttributeNS(W, 'val') == 'bullet':
                for label in level.getElementsByTagNameNS(W, 'lvlText'):
                    label.setAttributeNS(W, 'w:val', '-')
                for font in level.getElementsByTagNameNS(W, 'rFonts'):
                    for attr in ('ascii', 'hAnsi', 'cs'):
                        font.setAttributeNS(W, 'w:' + attr, 'Arial')
        entries['word/numbering.xml'] = n.toxml(encoding='utf-8')
    if 'docProps/core.xml' in entries:
        core = minidom.parseString(entries['docProps/core.xml'])
        for node in list(core.documentElement.childNodes):
            if node.nodeType == node.ELEMENT_NODE and node.localName in ('creator', 'lastModifiedBy'):
                while node.firstChild: node.removeChild(node.firstChild)
        entries['docProps/core.xml'] = core.toxml(encoding='utf-8')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():z.writestr(name, data)
