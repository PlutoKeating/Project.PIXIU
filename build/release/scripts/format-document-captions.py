#!/usr/bin/env python3
"""Center image captions and label every document table above its content."""
from pathlib import Path
from xml.dom import minidom
import sys
import zipfile

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
TABLE_TITLES = [
    '运行与编译环境要求', '系统与解释器检查命令', '安装包校验与直接安装命令',
    '源码解压与摘要核对命令', '系统依赖准备命令', '宿主与运行时构建命令',
    '完整安装包构建命令', '重建安装包检查与安装命令', '常见故障与处理方法',
    '记忆服务状态检查与恢复命令', '后台资料整理流程与用户收益',
    '混合检索处理环节与结果', '产品功能与用户操作', '个性化设置及用途',
    '三层记忆的内容与用途', '应用场景与用户价值', '正式安装包测试结果',
    '功能验证范围与结果', 'Debian兼容环境量化评测结果', '麒麟平台适配范围',
    '原生环境验证结果', '源码目录职责与归属', '主要上游依赖及许可证',
]


def format_captions(path):
    with zipfile.ZipFile(path) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    doc = minidom.parseString(entries['word/document.xml'])
    body = doc.getElementsByTagNameNS(W, 'body')[0]
    def children(e):
        return [n for n in e.childNodes if n.nodeType == n.ELEMENT_NODE]
    def child(e, name, **attrs):
        found = [n for n in children(e) if n.namespaceURI == W and n.localName == name]
        node = found[0] if found else doc.createElementNS(W, 'w:' + name)
        if not found: e.appendChild(node)
        for k, v in attrs.items(): node.setAttributeNS(W, 'w:' + k, str(v))
        return node
    def text(e):
        return ''.join(n.firstChild.data for n in e.getElementsByTagNameNS(W, 't') if n.firstChild)
    def style(p, above=False):
        pr = child(p, 'pPr')
        if p.firstChild is not pr: p.insertBefore(pr, p.firstChild)
        child(pr, 'jc', val='center')
        ind = child(pr, 'ind', left=0, right=0, firstLine=0)
        for a in ('hanging', 'firstLineChars', 'leftChars', 'rightChars'):
            if ind.hasAttributeNS(W, a): ind.removeAttributeNS(W, a)
        child(pr, 'spacing', before=120 if above else 80, after=80 if above else 160, line=240, lineRule='auto')
        child(pr, 'keepLines')
        child(pr, 'keepNext', val='1' if above else '0')
    nodes = children(body)
    tables = [n for n in nodes if n.localName == 'tbl']
    if len(tables) != len(TABLE_TITLES):
        raise ValueError(f'Table inventory changed: {len(tables)}; review caption titles')
    images = 0
    for i, node in enumerate(nodes):
        if node.localName == 'p' and node.getElementsByTagNameNS(W, 'drawing'):
            following = next((n for n in nodes[i+1:] if text(n) or n.localName == 'tbl'), None)
            if following is None or following.localName != 'p' or not text(following).startswith(('0.1.12', '图')):
                raise ValueError('Image lacks an identifiable following caption')
            style(following)
            child(child(node, 'pPr'), 'keepNext')
            images += 1
    for number, (table, title) in enumerate(zip(tables, TABLE_TITLES), 1):
        previous = table.previousSibling
        while previous is not None and previous.nodeType != previous.ELEMENT_NODE:
            previous = previous.previousSibling
        caption = f'表{number}：{title}'
        if previous is not None and previous.localName == 'p' and text(previous) == caption:
            p = previous
        else:
            p = doc.createElementNS(W, 'w:p')
            body.insertBefore(p, table)
            run = child(p, 'r')
            rp = child(run, 'rPr')
            child(rp, 'rFonts', ascii='Noto Sans', hAnsi='Noto Sans', eastAsia='Noto Sans CJK SC')
            child(rp, 'sz', val=22)
            child(run, 't').appendChild(doc.createTextNode(caption))
        style(p, above=True)
    entries['word/document.xml'] = doc.toxml(encoding='utf-8')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in entries.items(): z.writestr(n, b)
    print(f'Centered {images} image captions and {len(tables)} table captions')

if __name__ == '__main__':
    format_captions(Path(sys.argv[1]))
