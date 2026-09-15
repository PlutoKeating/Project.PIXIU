"""Use the latest user-edited 34-page file as the complete package baseline."""
from pathlib import Path
import json,hashlib,zipfile,posixpath
from lxml import etree as ET
import product_screenshots as shots
import varied_layouts as layouts
from remove_slide_notes import remove_notes

WORK=Path(__file__).resolve().parents[1]
SOURCE=WORK/'source/user-cover-closing-20260915.pptx'
OUT=WORK/'render/abc-trial/PIXIU项目报告-科技风试作版.pptx'
M=WORK/'review/abc-trial-manifest.json'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
previous=json.loads(M.read_text())
assert digest(OUT) in {digest(SOURCE),previous['output_sha256']},'Archive new manual edits before rebuilding'
with zipfile.ZipFile(SOURCE) as z:blobs={n:z.read(n) for n in z.namelist()}
ns=shots.NS
pres=ET.fromstring(blobs['ppt/presentation.xml']);rels=ET.fromstring(blobs['ppt/_rels/presentation.xml.rels'])
targets={r.get('Id'):r.get('Target') for r in rels}
parts={i:posixpath.normpath('ppt/'+targets[e.get('{'+ns['r']+'}id')]) for i,e in enumerate(pres.find('p:sldIdLst',ns),1)}
assert len(parts)==34
shots.compose=layouts.compose;shots.PAGES=layouts.PAGES
result=shots.enrich(blobs,parts,list(range(1,35)))
notes_parts=remove_notes(blobs)
with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as z:
 for n,b in blobs.items():z.writestr(n,b)
m=json.loads((WORK/'source/user-cover-closing-20260915-manifest.json').read_text())
m['output_sha256']=digest(OUT)
m['layout_revision']={'source':str(SOURCE.relative_to(WORK.parents[1])),'source_sha256':digest(SOURCE),'parts':parts,'modified_pages':sorted(layouts.PAGES),'preserved_user_pages':[1,34],'notes_removed_parts':notes_parts}
for i,e in enumerate(m['slides'],1):
 if i in result:e['product_evidence']=result[i]
inputs=[SOURCE,WORK/'source/user-cover-closing-20260915-manifest.json',WORK/'reference/ABC公司产品宣传路演PPT.pptx',Path(__file__),WORK/'scripts/varied_layouts.py',WORK/'scripts/remove_slide_notes.py',WORK/'scripts/product_screenshots.py']
inputs.extend(WORK.parents[1]/im['source'] for r in result.values() for im in r['screenshots'])
m['inputs']=[{'path':str(p.relative_to(WORK.parents[1])),'sha256':digest(p)} for p in sorted(set(inputs))]
M.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
print('Built 34 pages from the latest user cover/closing revision; redesigned',len(result),'bodies.')
