#!/usr/bin/env python3
"""Remove terminal-box captions and consecutively number real table captions."""
from pathlib import Path
from xml.dom import minidom
import re,sys,zipfile
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def normalize(path):
    with zipfile.ZipFile(path) as z:entries={n:z.read(n) for n in z.namelist()}
    d=minidom.parseString(entries['word/document.xml']);body=d.getElementsByTagNameNS(W,'body')[0]
    def text(e):return ''.join(n.firstChild.data for n in e.getElementsByTagNameNS(W,'t') if n.firstChild)
    nodes=[n for n in body.childNodes if n.nodeType==n.ELEMENT_NODE];removed=count=0
    for i,table in enumerate(nodes):
        if table.localName!='tbl':continue
        previous=nodes[i-1] if i else None
        caption=previous if previous is not None and previous.localName=='p' and re.match(r'^表\s*\d+\s*[：:]',text(previous)) else None
        terminal=text(table).lstrip().startswith('$ ') and any(n.getAttributeNS(W,'fill').upper()=='18212B' for n in table.getElementsByTagNameNS(W,'shd'))
        if terminal:
            if caption is not None:body.removeChild(caption);removed+=1
            continue
        if caption is None:raise ValueError('Normal table lacks a caption')
        count+=1;content=re.sub(r'^表\s*\d+\s*[：:]\s*',f'表{count}：',text(caption))
        ts=caption.getElementsByTagNameNS(W,'t')
        for n in ts:
            while n.firstChild:n.removeChild(n.firstChild)
        ts[0].appendChild(d.createTextNode(content))
    entries['word/document.xml']=d.toxml(encoding='utf-8')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in entries.items():z.writestr(n,b)
    print(f'Removed {removed} terminal captions; numbered {count} table captions')
if __name__=='__main__':normalize(Path(sys.argv[1]))
