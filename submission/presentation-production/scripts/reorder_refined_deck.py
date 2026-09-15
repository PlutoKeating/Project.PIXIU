"""Reorder the user-refined native deck without regenerating its artwork."""
from copy import deepcopy
from pathlib import Path, PurePosixPath
import hashlib
import json
import posixpath
import zipfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from refine_explanations import COVERS, cover, explain, set_text, align_knowledge, explain_technical, TECH_EXPLANATIONS
from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'submission/presentation-production'
SOURCE = WORK / 'source/user-refined-20260915.pptx'
BASE_MANIFEST = WORK / 'source/user-refined-20260915-manifest.json'
OUT = WORK / 'render/abc-trial/PIXIU项目报告-科技风试作版.pptx'
MANIFEST = WORK / 'review/abc-trial-manifest.json'
ORDER = [1,2,33,3,4,34,5,6,35,7,11,8,9] + list(range(12,29)) + [36,30,31,32]
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
# New dividers are exact native copies of the accepted technical divider.
for key in COVERS:
    part = f'ppt/slides/slide{key}.xml'
    parts[key] = part
    blobs[part] = encode(cover(ET.fromstring(blobs[parts[12]]), key))
    source_rels = ET.fromstring(blobs['ppt/slides/_rels/slide12.xml.rels'])
    for relationship in list(source_rels):
        if relationship.get('Type').endswith('/notesSlide'):
            source_rels.remove(relationship)
    blobs[f'ppt/slides/_rels/slide{key}.xml.rels'] = encode(source_rels)
    rid = f'rIdPixiuChapter{key}'
    rel = ET.SubElement(rels, '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship', Id=rid, Type=NS['r']+'/slide', Target=f'slides/slide{key}.xml')
    node = ET.Element('{'+NS['p']+'}sldId', id=str(1000+key))
    node.set('{'+NS['r']+'}id', rid)
    slide_ids.append(node)
for node in list(slide_list):
    slide_list.remove(node)
for old_page in ORDER:
    slide_list.append(slide_ids[old_page-1])
for deleted_page in [10,29]:
    deleted_id = slide_ids[deleted_page-1].get('id')
    deleted_rid = slide_ids[deleted_page-1].get('{'+NS['r']+'}id')
    rels.remove(rel_by_id[deleted_rid])
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
        ids = node.xpath('.//p:cNvPr/@id', namespaces=NS)
        identity = int(ids[0]) if ids else -1
        if old_page == 28 and 23 <= identity <= 39:
            if identity <= 37:
                slot, component = divmod(identity - 23, 5)
                left = .85 + slot * 4
                positions = {
                    0: (left, 2.25, 3.63, 2.4),
                    1: (left + 1.245, 2.25, 1.14, 0),
                    2: (left + .15, 2.53, 3.33, .5),
                    3: (left + .20, 3.35, 3.23, 1),
                    4: ((2.665 if slot == 0 else 6.665), 4.80, (0 if slot == 1 else 4), .55),
                }
                px, py, width, height = positions[component]
            else:
                px, py, width, height = ((.85, 5.55, 11.63, .5) if identity == 38 else (.92, 5.64, 11.49, .32))
            off.set('x', str(round(px * EMU)))
            off.set('y', str(round(py * EMU)))
            extent = node.xpath('./p:spPr/a:xfrm/a:ext', namespaces=NS)[0]
            extent.set('cx', str(round(width * EMU)))
            extent.set('cy', str(round(height * EMU)))
            reason = 'align convergence cards arrows and result'
        elif old_page == 21 and 23 <= identity <= 37:
            slot, component = divmod(identity - 23, 4)
            left = .85 + slot * 2.99
            positions = {
                0: (left, 2.18, 2.66, .46),
                1: (left + .07, 2.25, 2.52, .32),
                2: (left, 2.83, 2.66, .35),
                3: (left + 2.74, 2.41, .17, 0),
            }
            px, py, width, height = positions[component]
            off.set('x', str(round(px * EMU)))
            off.set('y', str(round(py * EMU)))
            extent = node.xpath('./p:spPr/a:xfrm/a:ext', namespaces=NS)[0]
            extent.set('cx', str(round(width * EMU)))
            extent.set('cy', str(round(height * EMU)))
            reason = 'align lifecycle steps within panel'
        elif old_page == 4 and text in {
            '知识偏好演变', '新旧通知与偏好存在冲突', '版本与来源', '保留历史，更正经过审批'
        }:
            replacements = {
                '知识偏好演变': ['记忆依赖手动'],
                '新旧通知与偏好存在冲突': ['资料不断积累', '难以逐条交代与整合'],
                '版本与来源': ['自动记忆，持续整合'],
                '保留历史，更正经过审批': ['后台整合，更正合并经审批'],
            }
            runs = node.xpath('.//a:t', namespaces=NS)
            assert len(runs) == len(replacements[text])
            for run, value in zip(runs, replacements[text]):
                run.text = value
            size = {'版本与来源': '1800', '保留历史，更正经过审批': '1600'}.get(text)
            if size:
                for props in node.xpath('.//a:rPr | .//a:defRPr | .//a:endParaRPr', namespaces=NS):
                    props.set('sz', size)
            reason = 'align need and response with auto dreaming'
        elif old_page in {7, 8, 9, 11} and y < .8 and x >= 2.77:
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
    if old_page in {9,11}:
        root = explain(root, 'sharing' if old_page == 11 else 'billing')
    if old_page == 14:
        root = align_knowledge(root)
    if old_page in TECH_EXPLANATIONS:
        root = explain_technical(root,old_page)
    if old_page == 12:
        for node in tree:
            if shape_text(node) == '持续记忆技术体系':set_text(node,'技术架构与实现方案')
    if modified or old_page in {9,11,12,14,15,17,18}:
        blobs[part] = encode(root)
    changes[old_page] = modified

# Delete the removed slide and its notes, not just the visible slide-list entry.
removed = set()
def relationship_part(part):
    p = PurePosixPath(part)
    return str(p.parent / '_rels' / (p.name + '.rels'))
for deleted_page in [10,29]:
    removed.add(parts[deleted_page])
    rpart = relationship_part(parts[deleted_page])
    removed.add(rpart)
    if rpart in blobs:
        for rel in ET.fromstring(blobs[rpart]):
            if rel.get('Type').endswith('/notesSlide'):
                note = posixpath.normpath(posixpath.join(posixpath.dirname(parts[deleted_page]), rel.get('Target')))
                removed.update({note, relationship_part(note)})
for name in removed:
    blobs.pop(name, None)
ct = ET.fromstring(blobs['[Content_Types].xml'])
for node in list(ct):
    if node.get('PartName', '').lstrip('/') in removed:
        ct.remove(node)
for key in COVERS:
    ET.SubElement(ct, '{http://schemas.openxmlformats.org/package/2006/content-types}Override', PartName='/'+parts[key], ContentType='application/vnd.openxmlformats-officedocument.presentationml.slide+xml')
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
    for old in ORDER:
        node = deepcopy(nodes[-32:][old-1 if old <= 32 else 11])
        if old in COVERS:node.text = COVERS[old][1]
        head.append(node)
    for node in head:vector.append(node)
    vector.set('size', str(len(vector)))
blobs['docProps/app.xml'] = encode(app)

from product_screenshots import enrich
product_evidence = enrich(blobs, parts, ORDER)

with zipfile.ZipFile(OUT, 'w') as target:
    for info in infos:
        if info.filename in blobs:
            target.writestr(info, blobs[info.filename])
    for name in blobs.keys() - original_blobs.keys():
        target.writestr(name, blobs[name], compress_type=zipfile.ZIP_DEFLATED)
base = json.loads(BASE_MANIFEST.read_text())
manifest = deepcopy(base)
manifest['slides'] = []
for new_page, old_page in enumerate(ORDER, 1):
    entry = deepcopy(base['slides'][old_page-1 if old_page<=32 else 11])
    if old_page in COVERS:
        entry['title'] = COVERS[old_page][1]
        entry['source_pages'] = []
        entry['chapter_cover'] = True
    if old_page == 12:entry['title'] = '技术架构与实现方案'
    entry['page'] = new_page
    entry['user_refined_source_page'] = old_page
    if old_page in {7, 8, 9, 11}:
        entry['navigation']['tabs'] = ['两大亮点', '记忆共享，分布互连', '自动记忆，持续整合', '场景示例']
    if new_page in product_evidence:
        entry['product_evidence'] = product_evidence[new_page]
        entry['screenshots'] = sorted(set(entry['screenshots']) | {i['source'] for i in product_evidence[new_page]['screenshots']})
    manifest['slides'].append(entry)
manifest['removed_slides'] = [{'user_refined_source_page': n, 'title': base['slides'][n-1]['title'], 'source_pages': base['slides'][n-1]['source_pages']} for n in [10,29]]
manifest['inputs'] = [{'path': str(p.relative_to(ROOT)), 'sha256': digest(p)} for p in [SOURCE, BASE_MANIFEST, Path(__file__).resolve(), WORK/'scripts/build_reference_deck.py', WORK/'scripts/refine_explanations.py']]
extra_inputs = {WORK/'scripts/product_screenshots.py', WORK/'source/product-captures/capture-manifest.json'}
extra_inputs |= {ROOT / i['source'] for v in product_evidence.values() for i in v['screenshots']}
manifest['inputs'] += [{'path': str(p.relative_to(ROOT)), 'sha256': digest(p)} for p in sorted(extra_inputs)]
manifest['output_sha256'] = digest(OUT)
manifest['revision'] = {
    'mode': 'preserve user-refined package', 'source_sha256': digest(SOURCE),
    'source_page_order': ORDER, 'shape_changes': changes,
    'content_revised_source_pages': [4,9,11,12,14,15,17,18], 'cloned_chapter_sources': {str(k):12 for k in COVERS},
    'unchanged_package_parts': sum(blobs.get(k) == v for k,v in original_blobs.items()),
    'removed_package_parts': sorted(removed),
}
MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'slides': len(ORDER), 'file': str(OUT), 'user_refined_source_sha256': digest(SOURCE)}, ensure_ascii=False))
