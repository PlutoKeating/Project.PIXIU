#!/usr/bin/env python3
"""Bind Chinese major headings and legal Arabic subheadings to native Word numbering."""
from pathlib import Path
import sys
from xml.dom import minidom
import zipfile

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def apply_numbering(path):
    with zipfile.ZipFile(path) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    styles = minidom.parseString(entries['word/styles.xml'])
    levels = {}
    for s in styles.getElementsByTagNameNS(W, 'style'):
        names = s.getElementsByTagNameNS(W, 'name')
        if names:
            name = names[0].getAttributeNS(W, 'val').lower().replace(' ', '')
            if name in ('heading1', 'heading2'):
                levels[s.getAttributeNS(W, 'styleId')] = int(name[-1]) - 1
    if set(levels.values()) != {0, 1}:
        raise ValueError('Missing first/second heading styles')
    d = minidom.parseString(entries['word/numbering.xml'])

    def node(doc, parent, name, **attrs):
        e = doc.createElementNS(W, 'w:' + name)
        for k, v in attrs.items(): e.setAttributeNS(W, 'w:' + k, str(v))
        parent.appendChild(e)
        return e

    aid = max([int(n.getAttributeNS(W, 'abstractNumId')) for n in d.getElementsByTagNameNS(W, 'abstractNum')] + [0]) + 1
    nid = max([int(n.getAttributeNS(W, 'numId')) for n in d.getElementsByTagNameNS(W, 'num')] + [0]) + 1
    abstract = node(d, d.documentElement, 'abstractNum', abstractNumId=aid)
    node(d, abstract, 'multiLevelType', val='multilevel')
    for level in (0, 1):
        lvl = node(d, abstract, 'lvl', ilvl=level)
        node(d, lvl, 'start', val=1)
        node(d, lvl, 'numFmt', val='chineseCounting' if level == 0 else 'decimal')
        node(d, lvl, 'pStyle', val=next(k for k, v in levels.items() if v == level))
        if level == 1: node(d, lvl, 'isLgl')
        node(d, lvl, 'suff', val='space')
        node(d, lvl, 'lvlText', val='%1、' if level == 0 else '%1.%2')
        node(d, lvl, 'lvlJc', val='left')
    num = node(d, d.documentElement, 'num', numId=nid)
    node(d, num, 'abstractNumId', val=aid)
    doc = minidom.parseString(entries['word/document.xml'])
    count = [0, 0]
    for p in doc.getElementsByTagNameNS(W, 'p'):
        props = [n for n in p.childNodes if n.nodeType == n.ELEMENT_NODE and n.localName == 'pPr']
        if not props: continue
        prop = props[0]
        style = prop.getElementsByTagNameNS(W, 'pStyle')
        if not style or style[0].getAttributeNS(W, 'val') not in levels: continue
        level = levels[style[0].getAttributeNS(W, 'val')]
        for old in list(prop.childNodes):
            if old.nodeType == old.ELEMENT_NODE and old.localName == 'numPr': prop.removeChild(old)
        np = node(doc, prop, 'numPr'); node(doc, np, 'ilvl', val=level);node(doc, np, 'numId', val=nid)
        count[level] += 1
    if count[0] != 8: raise ValueError(f'Expected eight major headings, got {count}')
    for style in styles.getElementsByTagNameNS(W, 'style'):
        sid = style.getAttributeNS(W, 'styleId')
        if sid not in levels: continue
        props = [p for p in style.childNodes if p.nodeType == p.ELEMENT_NODE and p.localName == 'pPr']
        pr = props[0] if props else node(styles, style, 'pPr')
        for old in list(pr.childNodes):
            if old.nodeType == old.ELEMENT_NODE and old.localName == 'numPr': pr.removeChild(old)
        np = node(styles, pr, 'numPr')
        node(styles, np, 'ilvl', val=levels[sid]); node(styles, np, 'numId', val=nid)
    entries['word/styles.xml'] = styles.toxml(encoding='utf-8')
    entries['word/document.xml'] = doc.toxml(encoding='utf-8')
    entries['word/numbering.xml'] = d.toxml(encoding='utf-8')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in entries.items(): z.writestr(n, b)
    print('Native heading numbering:', count)


if __name__ == '__main__':
    apply_numbering(Path(sys.argv[1]))
