#!/usr/bin/env python3
"""Separate body first-line indentation from hanging numbered-list indentation."""
from pathlib import Path
from xml.dom import minidom
import sys,zipfile
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def fix(path):
    with zipfile.ZipFile(path) as z:entries={n:z.read(n) for n in z.namelist()}
    styles=minidom.parseString(entries['word/styles.xml']);doc=minidom.parseString(entries['word/document.xml']);numbering=minidom.parseString(entries['word/numbering.xml'])
    def direct(e,name):return [c for c in e.childNodes if c.nodeType==c.ELEMENT_NODE and c.localName==name]
    def child(e,name,**attrs):
        found=direct(e,name);v=found[0] if found else e.ownerDocument.createElementNS(W,'w:'+name)
        if not found:e.appendChild(v)
        for k,a in attrs.items():v.setAttributeNS(W,'w:'+k,str(a))
        return v
    body=next(s for s in styles.getElementsByTagNameNS(W,'style') if direct(s,'name') and direct(s,'name')[0].getAttributeNS(W,'val').replace(' ','').lower()=='bodytext')
    sz=body.getElementsByTagNameNS(W,'sz');em=int(sz[0].getAttributeNS(W,'val'))*10 if sz else 240
    # Word stores character units in hundredths; retain a matching twip fallback.
    child(child(body,'pPr'),'ind',firstLineChars=200,firstLine=em*2)
    sid='PIXIUBodyList'
    existing=[s for s in styles.getElementsByTagNameNS(W,'style') if s.getAttributeNS(W,'styleId')==sid]
    ls=existing[0] if existing else body.cloneNode(True)
    if not existing:styles.documentElement.appendChild(ls)
    ls.setAttributeNS(W,'w:styleId',sid);child(ls,'name',val='PIXIU Body List')
    def indent(pr):
        for n in direct(pr,'ind')+direct(pr,'tabs'):pr.removeChild(n)
        child(pr,'ind',left=em*3,hanging=em,leftChars=300,hangingChars=100)
        child(child(pr,'tabs'),'tab',val='num',pos=em*3)
    indent(child(ls,'pPr'))
    body_id=body.getAttributeNS(W,'styleId');ids=set();count=0
    for p in doc.getElementsByTagNameNS(W,'p'):
        prs=direct(p,'pPr')
        if not prs:continue
        pr=prs[0];ps=direct(pr,'pStyle');np=direct(pr,'numPr')
        if not ps or not np or ps[0].getAttributeNS(W,'val') not in (body_id,sid):continue
        nid=direct(np[0],'numId')
        if not nid or nid[0].getAttributeNS(W,'val')=='0':continue
        ids.add(nid[0].getAttributeNS(W,'val'));ps[0].setAttributeNS(W,'w:val',sid);indent(pr);count+=1
    aids={direct(n,'abstractNumId')[0].getAttributeNS(W,'val') for n in numbering.getElementsByTagNameNS(W,'num') if n.getAttributeNS(W,'numId') in ids}
    for a in numbering.getElementsByTagNameNS(W,'abstractNum'):
        if a.getAttributeNS(W,'abstractNumId') in aids:
            for lvl in direct(a,'lvl'):
                if lvl.getAttributeNS(W,'ilvl')=='0':
                    child(lvl,'suff',val='tab');indent(child(lvl,'pPr'))
    entries['word/styles.xml']=styles.toxml(encoding='utf-8');entries['word/document.xml']=doc.toxml(encoding='utf-8');entries['word/numbering.xml']=numbering.toxml(encoding='utf-8')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in entries.items():z.writestr(n,b)
    print('List paragraphs fixed:',count,'; body first-line: 2 characters')
if __name__=='__main__':fix(Path(sys.argv[1]))
