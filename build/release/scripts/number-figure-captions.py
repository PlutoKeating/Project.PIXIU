#!/usr/bin/env python3
"""Number existing figure captions and reuse the user's table-caption style."""
from pathlib import Path
from xml.dom import minidom
import re,sys,zipfile
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
def apply(path):
    with zipfile.ZipFile(path) as z:entries={n:z.read(n) for n in z.namelist()}
    d=minidom.parseString(entries['word/document.xml']);s=minidom.parseString(entries['word/styles.xml'])
    def direct(e,k):return [n for n in e.childNodes if n.nodeType==n.ELEMENT_NODE and n.localName==k]
    def text(e):return ''.join(n.firstChild.data for n in e.getElementsByTagNameNS(W,'t') if n.firstChild)
    sid=next(st.getAttributeNS(W,'styleId') for st in s.getElementsByTagNameNS(W,'style') if direct(st,'name') and direct(st,'name')[0].getAttributeNS(W,'val')=='1')
    body=d.getElementsByTagNameNS(W,'body')[0];nodes=[n for n in body.childNodes if n.nodeType==n.ELEMENT_NODE]
    template=next(n for n in nodes if n.localName=='p' and re.match(r'表\s*1[：:]',text(n)))
    assert direct(direct(template,'pPr')[0],'pStyle')[0].getAttributeNS(W,'val')==sid
    rpr=template.getElementsByTagNameNS(W,'r')[0].getElementsByTagNameNS(W,'rPr')
    count=0
    for i,node in enumerate(nodes):
        if node.localName!='p' or not node.getElementsByTagNameNS(W,'drawing'):continue
        p=next(n for n in nodes[i+1:] if text(n))
        assert p.localName=='p' and text(p).startswith(('0.1.12','图'))
        count+=1;t=f'图{count}：'+re.sub(r'^图\s*\d+\s*[：:]\s*','',text(p))
        for n in list(p.childNodes):p.removeChild(n)
        pr=direct(template,'pPr')[0].cloneNode(True)
        for k in direct(pr,'keepNext'):k.setAttributeNS(W,'w:val','0')
        p.appendChild(pr)
        r=d.createElementNS(W,'w:r')
        if rpr:r.appendChild(rpr[0].cloneNode(True))
        tt=d.createElementNS(W,'w:t');tt.appendChild(d.createTextNode(t));r.appendChild(tt);p.appendChild(r)
    entries['word/document.xml']=d.toxml(encoding='utf-8')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in entries.items():z.writestr(n,b)
    print('Figure captions numbered and assigned style 1:',count)
if __name__=='__main__':apply(Path(sys.argv[1]))
