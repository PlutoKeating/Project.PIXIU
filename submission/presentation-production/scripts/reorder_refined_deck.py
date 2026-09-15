"""Reorder the user-refined native deck without regenerating its artwork."""
from copy import deepcopy
from pathlib import Path, PurePosixPath
import hashlib
import json
import posixpath
import zipfile
from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'submission/presentation-production'
SOURCE = WORK / 'source/user-refined-20260915.pptx'
BASE_MANIFEST = WORK / 'source/user-refined-20260915-manifest.json'
OUT = WORK / 'render/abc-trial/PIXIU项目报告-科技风试作版.pptx'
MANIFEST = WORK / 'review/abc-trial-manifest.json'
ORDER = list(range(1, 8)) + [11, 8, 9] + list(range(12, 33))
NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
EMU = 914400


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(node):
    return ET.tostring(node, xml_declaration=True, encoding='UTF-8', standalone=True)


def shape_text(node):
    return ''.join(node.xpath('.//a:t/text()', namespaces=NS))


def origin(node):
    found = node.xpath('./p:spPr/a:xfrm/a:off | ./p:grpSpPr/a:xfrm/a:off', namespaces=NS)
    return found[0] if found else None


def move(node, dx):
    off = origin(node)
    assert off is not None
    off.set('x', str(int(off.get('x')) + round(dx * EMU)))


if OUT.exists():
    previous = json.loads(MANIFEST.read_text())
    if digest(OUT) not in {digest(SOURCE), previous['output_sha256']}:
        raise SystemExit('The output has new manual edits. Archive that latest PPTX before rebuilding.')

with zipfile.ZipFile(SOURCE) as source:
    blobs = {name: source.read(name) for name in source.namelist()}
    infos = source.infolist()
original_blobs = dict(blobs)
presentation = ET.fromstring(blobs['ppt/presentation.xml'])
rels = ET.fromstring(blobs['ppt/_rels/presentation.xml.rels'])
slide_list = presentation.find('p:sldIdLst', NS)
slide_ids = list(slide_list)
assert len(slide_ids) == 32
rel_by_id = {r.get('Id'): r for r in rels}
parts = {}
for old_page, slide_id in enumerate(slide_ids, 1):
    target = rel_by_id[slide_id.get('{'+NS['r']+'}id')].get('Target')
    parts[old_page] = posixpath.normpath(posixpath.join('ppt', target))
for node in slide_ids:
    slide_list.remove(node)
for old_page in ORDER:
    slide_list.append(slide_ids[old_page-1])
deleted_id = slide_ids[9].get('id')
deleted_rid = slide_ids[9].get('{'+NS['r']+'}id')
rels.remove(rel_by_id[deleted_rid])
# Remove references from optional section/custom-show metadata too.
for node in list(presentation.iter()):
    if node is presentation:
        continue
    if (ET.QName(node).localname == 'sldId' and node.get('id') == deleted_id) or node.get('{'+NS['r']+'}id') == deleted_rid:
        node.getparent().remove(node)
blobs['ppt/presentation.xml'] = encode(presentation)
blobs['ppt/_rels/presentation.xml.rels'] = encode(rels)

# Keep every retained shape as authored; only navigation, folios and the two
# complete overview panels change. Their internal offsets/effects remain intact.
changes = {}
for new_page, old_page in enumerate(ORDER, 1):
    part = parts[old_page]
    root = ET.fromstring(blobs[part])
    tree = root.find('p:cSld/p:spTree', NS)
    modified = []
    for node in list(tree):
        off = origin(node)
        if off is None:
            continue
        x, y = int(off.get('x')) / EMU, int(off.get('y')) / EMU
        text = shape_text(node)
        reason = None
        if old_page in {7, 8, 9, 11} and y < .8 and x >= 2.77:
            slot = int((x - 2.78 + .015) // 1.61)
            if slot in {0, 1, 2, 3, 4}:
                if slot == 3:
                    tree.remove(node)
                    reason = 'remove preference navigation'
                else:
                    target_slot = {0: 0, 4: 1, 1: 2, 2: 3}[slot]
                    if target_slot != slot:
                        move(node, (target_slot-slot)*1.61)
                        reason = 'reorder feature navigation'
        elif old_page == 7 and 1.9 < y < 6.9:
            # Whole left/right groups, including art, move by the same amount.
            move(node, 6.34 if x < 6.6 else -6.34)
            if text in {'01', '02'}:
                node.xpath('.//a:t', namespaces=NS)[0].text = '02' if text == '01' else '01'
            reason = 'swap complete flagship panels'
        if text == f'{old_page:02}' and 7.1 < y < 7.3 and new_page != old_page:
            runs = node.xpath('.//a:t', namespaces=NS)
            assert len(runs) == 1
            runs[0].text = f'{new_page:02}'
            reason = 'renumber folio'
        if reason:
            ids = node.xpath('.//p:cNvPr/@id', namespaces=NS)
            modified.append({'shape_id': ids[0] if ids else None, 'reason': reason})
    if modified:
        blobs[part] = encode(root)
    changes[old_page] = modified

# Delete the removed slide and its notes, not just the visible slide-list entry.
removed = {parts[10]}
def relationship_part(part):
    p = PurePosixPath(part)
    return str(p.parent / '_rels' / (p.name + '.rels'))
rpart = relationship_part(parts[10])
removed.add(rpart)
if rpart in blobs:
    for rel in ET.fromstring(blobs[rpart]):
        if rel.get('Type').endswith('/notesSlide'):
            note = posixpath.normpath(posixpath.join(posixpath.dirname(parts[10]), rel.get('Target')))
            removed.update({note, relationship_part(note)})
for name in removed:
    blobs.pop(name, None)
ct = ET.fromstring(blobs['[Content_Types].xml'])
for node in list(ct):
    if node.get('PartName', '').lstrip('/') in removed:
        ct.remove(node)
blobs['[Content_Types].xml'] = encode(ct)
app = ET.fromstring(blobs['docProps/app.xml'])
for node in app:
    if ET.QName(node).localname == 'Slides':
        node.text = str(len(ORDER))
pairs = app.xpath('//*[local-name()="HeadingPairs"]/*/*')
if pairs:
    pairs[-1][0].text = str(len(ORDER))
vectors = app.xpath('//*[local-name()="TitlesOfParts"]/*')
if vectors:
    vector = vectors[0]
    nodes = list(vector)
    head = nodes[:-32]
    for node in nodes:
        vector.remove(node)
    for node in head + [nodes[-32:][old-1] for old in ORDER]:
        vector.append(node)
    vector.set('size', str(len(vector)))
blobs['docProps/app.xml'] = encode(app)

with zipfile.ZipFile(OUT, 'w') as target:
    for info in infos:
        if info.filename in blobs:
            target.writestr(info, blobs[info.filename])
base = json.loads(BASE_MANIFEST.read_text())
manifest = deepcopy(base)
manifest['slides'] = []
for new_page, old_page in enumerate(ORDER, 1):
    entry = deepcopy(base['slides'][old_page-1])
    entry['page'] = new_page
    entry['user_refined_source_page'] = old_page
    if old_page in {7, 8, 9, 11}:
        entry['navigation']['tabs'] = ['两大亮点', '记忆共享，分布互连', '自动记忆，持续整合', '场景示例']
    manifest['slides'].append(entry)
manifest['removed_slides'] = [{'user_refined_source_page': 10, 'title': base['slides'][9]['title'], 'source_pages': base['slides'][9]['source_pages']}]
manifest['inputs'] = [{'path': str(p.relative_to(ROOT)), 'sha256': digest(p)} for p in [SOURCE, BASE_MANIFEST, Path(__file__).resolve(), WORK/'scripts/build_reference_deck.py']]
manifest['output_sha256'] = digest(OUT)
manifest['revision'] = {
    'mode': 'preserve user-refined package', 'source_sha256': digest(SOURCE),
    'source_page_order': ORDER, 'shape_changes': changes,
    'unchanged_package_parts': sum(blobs.get(k) == v for k,v in original_blobs.items()),
    'removed_package_parts': sorted(removed),
}
MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'slides': len(ORDER), 'file': str(OUT), 'user_refined_source_sha256': digest(SOURCE)}, ensure_ascii=False))
