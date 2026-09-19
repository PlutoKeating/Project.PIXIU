"""Validate package integrity, evidence bytes and complete rendered-page coverage."""
from pathlib import Path
import hashlib, json, re, zipfile
import xml.etree.ElementTree as ET
from pptx import Presentation
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'submission/presentation-production'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((WORK/'review/build-manifest.json').read_text())
ppt=ROOT/m['output']['path']
assert digest(ppt)==m['output']['sha256']
for item in m['inputs']:assert digest(ROOT/item['path'])==item['sha256'], item['path']
with zipfile.ZipFile(ppt) as z:
 assert z.testzip() is None
 for name in z.namelist():
  if name.endswith(('.xml','.rels')):ET.fromstring(z.read(name))
 texts='\n'.join(z.read(n).decode() for n in z.namelist() if n.endswith('.xml'))
 for forbidden in ['华南理工大学','秦基赫','/home/pluto','localhost','127.0.0.1']:
  assert forbidden not in texts,forbidden
 media={hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('ppt/media/')}
 for slide in m['slides']:
  for item in slide['screenshots']:
   assert digest(ROOT/item['path'])==item['sha256']
   assert item['sha256'] in media, item['path']
prs=Presentation(ppt)
assert len(prs.slides)==len(m['slides'])==34
timeline=json.loads((ROOT/'submission/video-production/src/timeline.json').read_text())
shots={s['id']:s for s in timeline['shots']}
seen=[]
for rec,slide in zip(m['slides'],prs.slides):
 for sid in rec['shots']:
  assert shots[sid]['narration'] in slide.notes_slide.notes_text_frame.text, (rec['page'],sid)
  if sid not in seen:seen.append(sid)
assert seen==list(shots), 'Missing or reordered video shots'
toc=[s.click_action.target_slide for s in prs.slides[1].shapes if s.click_action.target_slide is not None]
assert [s.slide_id for s in toc]==[prs.slides[i-1].slide_id for i in [3,10,18,23,26,30]]
for slide in list(prs.slides)[2:]:
 links=[s for s in slide.shapes if s.has_text_frame and s.text=='目录']
 assert len(links)==1 and links[0].click_action.target_slide.slide_id==prs.slides[1].slide_id
reference=json.loads((WORK/'review/video-aligned/video-reference.json').read_text())
assert reference['video_sha256']==m['video_sha256']==digest(ROOT/reference['video'])
assert len(reference['frames'])==60
for frame in reference['frames']:assert digest(ROOT/frame['path'])==frame['sha256']
images=sorted((WORK/'render/final').glob('slide-*.png'))
assert [p.name for p in images]==[f'slide-{i:02}.png' for i in range(1,35)]
assert all(p.stat().st_size>10000 for p in images)
result={'pptx_sha256':digest(ppt),'pdf_sha256':digest(WORK/'render/final/项目报告.pdf'),
 'pages':34,'video_shots':len(seen),'toc_destinations':[3,10,18,23,26,30],
 'image_instances':sum(len(s['screenshots']) for s in m['slides']),
 'unique_original_images':len(media),'editable_shapes':sum(len(s.shapes) for s in prs.slides),
 'checks':['ZIP CRC and XML parse','all input digests','original screenshot bytes embedded','anonymous XML text','34 complete raster pages','30 video shots in film order, exact narration in notes','six TOC destinations and 32 return links','delivered video SHA-256 and 60 reference frames'],
 'visual_review':'See final-review.md; automated checks do not establish visual correctness.',
 'rendered_pages':[{'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p)} for p in images]}
(WORK/'review/validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='rendered_pages'},ensure_ascii=False))
