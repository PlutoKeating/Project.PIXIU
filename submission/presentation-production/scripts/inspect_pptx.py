"""Extract every package part, slide element, relationship and text for review."""
from pathlib import Path
import argparse, hashlib, json, re, zipfile
import xml.etree.ElementTree as ET
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(a.input) as z:
 parts=[]
 for name in z.namelist():
  data=z.read(name); parts.append({'part':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
  dest=a.output/'package'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
 slides=[]
 for name in sorted((n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+.xml',n)),key=lambda n:int(re.search(r'(\d+)\.xml',n)[1])):
  root=ET.fromstring(z.read(name)); elems=[]
  for e in root.findall('.//p:spTree/*',NS):
   elems.append({'type':e.tag.split('}')[-1], 'texts':[t.text or '' for t in e.findall('.//a:t',NS)],'xml':ET.tostring(e,encoding='unicode')})
  slides.append({'part':name,'elements':elems,'all_text':[t.text or '' for t in root.findall('.//a:t',NS)]})
 report={'input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'parts':parts,'slides':slides}
 (a.output/'inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 (a.output/'text.md').write_text('\n\n'.join('## '+s['part']+'\n'+'\n'.join(s['all_text']) for s in slides))
 print(json.dumps({'slides':len(slides),'parts':len(parts),'elements':sum(len(s['elements']) for s in slides),'sha256':report['input_sha256']}))
