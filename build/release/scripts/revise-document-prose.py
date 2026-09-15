#!/usr/bin/env python3
"""Apply a reviewed prose revision to an existing DOCX while preserving its layout."""
from pathlib import Path
from xml.dom import minidom
import copy,json,sys,zipfile
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def revise(path, recipe):
    plan=json.loads(recipe.read_text())
    with zipfile.ZipFile(path) as z: entries={n:z.read(n) for n in z.namelist()}
    d=minidom.parseString(entries['word/document.xml']);body=d.getElementsByTagNameNS(W,'body')[0]
    def text(p):return ''.join(n.firstChild.data for n in p.getElementsByTagNameNS(W,'t') if n.firstChild)
    def direct(p,name):return [c for c in p.childNodes if c.nodeType==c.ELEMENT_NODE and c.localName==name]
    def el(name,**attrs):
        n=d.createElementNS(W,'w:'+name)
        for k,v in attrs.items():n.setAttributeNS(W,'w:'+k,str(v))
        return n
    paras=direct(body,'p')
    def find(t):
        matches=[p for p in direct(body,'p') if text(p)==t]
        if len(matches)!=1:raise ValueError(f'Expected unique paragraph: {t[:60]} ({len(matches)})')
        return matches[0]
    def replace(p,t):
        runs=p.getElementsByTagNameNS(W,'r'); props=runs[0].getElementsByTagNameNS(W,'rPr') if runs else []
        rp=props[0].cloneNode(True) if props else None
        for c in list(p.childNodes):
            if c.nodeType==c.ELEMENT_NODE and c.localName!='pPr':p.removeChild(c)
        r=el('r')
        if rp:r.appendChild(rp)
        tt=el('t');tt.setAttribute('xml:space','preserve');tt.appendChild(d.createTextNode(t));r.appendChild(tt);p.appendChild(r)
    h2=find('测试数据集与标注') if any(text(p)=='测试数据集与标注' for p in paras) else find('Debian 兼容环境评测')
    heading_template=h2.cloneNode(True)
    body_template=find('PIXIU 按使用时间和用途保存三层记忆。任务进行时使用当前上下文，任务结束后保留有用状态，经过处理的知识和偏好可供以后使用。').cloneNode(True)
    anchors=[(find(entry['before']),entry['items']) for entry in plan['insertions']]
    for r in plan['replacements']:replace(find(r['old']),r['new'])
    for anchor,items in anchors:
        for kind,t in items:
            p=(heading_template if kind=='h2' else body_template).cloneNode(True);replace(p,t);body.insertBefore(p,anchor)
    bold_count=0
    for phrase in plan['bold_phrases']:
        matches=[p for p in direct(body,'p') if phrase in text(p)]
        if not matches:continue
        p=matches[0];t=text(p);start=t.index(phrase);parts=[t[:start],phrase,t[start+len(phrase):]]
        runs=p.getElementsByTagNameNS(W,'r');rp=runs[0].getElementsByTagNameNS(W,'rPr')
        template=rp[0].cloneNode(True) if rp else el('rPr')
        for r in list(direct(p,'r')):p.removeChild(r)
        for i,part in enumerate(parts):
            if not part:continue
            r=el('r');pr=template.cloneNode(True)
            for old in list(direct(pr,'b'))+list(direct(pr,'bCs')):pr.removeChild(old)
            pr.appendChild(el('b',val=1 if i==1 else 0));pr.appendChild(el('bCs',val=1 if i==1 else 0));r.appendChild(pr)
            tt=el('t');tt.setAttribute('xml:space','preserve');tt.appendChild(d.createTextNode(part));r.appendChild(tt);p.appendChild(r)
        bold_count+=1
    entries['word/document.xml']=d.toxml(encoding='utf-8')
    core=minidom.parseString(entries['docProps/core.xml'])
    for n in core.documentElement.childNodes:
        if n.nodeType==n.ELEMENT_NODE and n.localName in ('creator','lastModifiedBy'):
            while n.firstChild:n.removeChild(n.firstChild)
    entries['docProps/core.xml']=core.toxml(encoding='utf-8')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in entries.items():z.writestr(n,b)
    print(f"Revised {len(plan['replacements'])} paragraphs, inserted {sum(len(e['items']) for e in plan['insertions'])}, emphasized {bold_count} passages")
if __name__=='__main__':revise(Path(sys.argv[1]),Path(sys.argv[2]))
