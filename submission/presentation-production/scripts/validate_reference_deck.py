"""Check the reference trial package, input provenance and rendered-page coverage."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw
from pptx import Presentation

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'submission/presentation-production'
OUT = WORK / 'render/abc-trial'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


m = json.loads((WORK / 'review/abc-trial-manifest.json').read_text())
ppt = OUT / 'PIXIU项目报告-科技风试作版.pptx'
assert digest(ppt) == m['output_sha256']
for item in m['inputs']:
    assert digest(ROOT / item['path']) == item['sha256'], item['path']
assert {n for s in m['slides'] + m.get('removed_slides', []) for n in s['source_pages']} == set(range(1, 32))
count = len(m['slides'])
assert count == 34
assert m['revision']['source_page_order'] == [1,2,33,3,4,34,5,6,35,7,11,8,9] + list(range(12,29)) + [36,30,31,32]
with zipfile.ZipFile(ppt) as z:
    assert z.testzip() is None
    xml_parts = []
    for name in z.namelist():
        assert not name.startswith('ppt/embeddings/'), name
        if name.endswith(('.xml', '.rels')):
            data = z.read(name)
            root = ET.fromstring(data)
            xml_parts.append(data.decode())
            if name.endswith('.rels'):
                assert all(e.get('TargetMode') != 'External' for e in root), name
    text = '\n'.join(xml_parts)
    for obsolete in ['记忆焕新', '记忆互联']:
        assert obsolete not in text, obsolete
    for forbidden in ['ABC', 'XYZ', '人从众', '1234567890', '华南理工',
                      '秦基赫', 'InnoSync', '/home/pluto', 'localhost', '127.0.0.1']:
        assert forbidden not in text, forbidden
    media = {hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()
             if n.startswith('ppt/media/')}
    for slide in m['slides']:
        for path in slide['screenshots'] + slide.get('illustrations', []):
            assert digest(ROOT / path) in media, path

prs = Presentation(ppt)
assert len(prs.slides) == count
for slide in m['slides']:
    assert not any(c in slide['title'] for c in '。？！：'), slide['title']
# Main topics must be present above the body; chapter covers have a separate hierarchy.
for n, (page, entry) in enumerate(zip(prs.slides, m['slides']), 1):
    visible = [(a.text, a.top / 914400) for a in page.shapes if a.has_text_frame]
    matches = [y for t, y in visible if t == entry['title']]
    assert matches, (n, entry['title'])
    assert min(matches) < (3.2 if n in {3,6,9,14,24,31} else 1.6), (n, matches)
    assert any(t == f'{n:02}' and 7.1 < y < 7.3 for t,y in visible), (n, 'folio')
    if n in {1,2,3,6,9,14,24,31,34}:
        assert 'navigation' not in entry
    else:
        nav=entry['navigation']
        header={t.replace('\n','') for t,y in visible if y < .8}
        assert nav['chapter'] in header and set(nav['tabs']) <= header, (n, nav)
        assert nav['active'] in nav['tabs']
    for t, y in visible:
        assert not any(x in t for x in ['风格试作版', '真实界面：', 'PRODUCT  /  MEMORY']), (n, t)
        assert not (y > 7.1 and ('SDK' in t or '实拍' in t)), (n, t)
# The two product capabilities must remain prominent and consistently named.
for n in [1,2,7,10,34]:
    wording='\n'.join(a.text for a in prs.slides[n-1].shapes if a.has_text_frame)
    assert '自动记忆，持续整合' in wording and '记忆共享，分布互连' in wording, (n, 'flagship names')
assert [entry['title'] for entry in m['slides'][9:13]] == ['两大核心亮点', '记忆共享，分布互连', '自动记忆，持续整合', '场景示例 · 账单检索']
assert all(not any(t in a.text for t in ['偏好演进','验证结果与待测范围','持续记忆技术体系']) for page in prs.slides for a in page.shapes if a.has_text_frame)
for page in prs.slides:
    assert all('目录整理' not in a.text for a in page.shapes if a.has_text_frame)
for path, expected in [(OUT / 'PIXIU项目报告-科技风试作版.pdf', count),
                       (WORK / 'render/reference/ABC公司产品宣传路演PPT.pdf', 20)]:
    info = subprocess.run(['pdfinfo', str(path)], check=True, capture_output=True, text=True).stdout
    assert int(re.search(r'Pages:\s+(\d+)', info).group(1)) == expected, path
rendered = []
for folder, folder_count in [('reference', 20), ('abc-trial', count)]:
    paths = sorted((WORK / 'render' / folder).glob('slide-*.png'))
    assert [p.name for p in paths] == [f'slide-{i:02}.png' for i in range(1, folder_count + 1)]
    for path in paths:
        with Image.open(path) as im:
            assert im.size == (1600, 900), path
            im.verify()
        rendered.append({'path': str(path.relative_to(ROOT)), 'sha256': digest(path)})

# Check that the user-refined shapes survive, beyond a successful render.
from lxml import etree as LET
source = WORK / 'source/user-refined-20260915.pptx'
ns = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
with zipfile.ZipFile(source) as before, zipfile.ZipFile(ppt) as after:
    for old_page in m['revision']['source_page_order']:
        part = f'ppt/slides/slide{old_page}.xml'
        if old_page > 32:
            import sys
            sys.path.insert(0,str(WORK/'scripts'))
            from refine_explanations import cover
            old = cover(LET.fromstring(before.read('ppt/slides/slide12.xml')), old_page)
        else:
            old = LET.fromstring(before.read(part))
        new = LET.fromstring(after.read(part))
        old_shapes = old.find('p:cSld/p:spTree', ns)
        new_shapes = new.find('p:cSld/p:spTree', ns)
        edits = {x['shape_id']: x['reason'] for x in m['revision']['shape_changes'][str(old_page)]}
        def key(node):
            ids = node.xpath('.//p:cNvPr/@id', namespaces=ns)
            return ids[0] if ids else None
        actual = {key(n): n for n in new_shapes if key(n) is not None}
        for node in old_shapes:
            identity = key(node)
            if identity is None:
                continue
            reason = edits.get(identity)
            offsets=node.xpath('./p:spPr/a:xfrm/a:off',namespaces=ns)
            y=int(offsets[0].get('y'))/914400 if offsets else -1
            if old_page in {9,11,14} and 1.85 <= y <= 7.1:
                continue  # Authorized diagram resizing / explanatory body rewrite.
            if old_page == 12 and ''.join(node.xpath('.//a:t/text()',namespaces=ns)) == '持续记忆技术体系':
                assert ''.join(actual[identity].xpath('.//a:t/text()',namespaces=ns)) == '技术架构与实现方案'
                continue
            if reason == 'remove preference navigation':
                assert identity not in actual
                continue
            other = actual[identity]
            if reason in {'reorder feature navigation', 'swap complete flagship panels'}:
                for element in [node, other]:
                    element.xpath('./p:spPr/a:xfrm/a:off | ./p:grpSpPr/a:xfrm/a:off', namespaces=ns)[0].set('x', '0')
            if reason == 'renumber folio' or (reason == 'swap complete flagship panels' and ''.join(node.xpath('.//a:t/text()', namespaces=ns)) in {'01','02'}):
                for element in [node, other]:
                    element.xpath('.//a:t', namespaces=ns)[0].text = 'folio'
            assert LET.tostring(node, method='c14n') == LET.tostring(other, method='c14n'), (old_page, identity, reason)
    assert before.read('ppt/slides/slide1.xml') == after.read('ppt/slides/slide1.xml')
    for part in m['revision']['removed_package_parts']:
        assert part not in after.namelist()

# Preserve the accepted 31-page candidate and its formal asset byte-for-byte.
baseline = '4bf08a7c3b504341cf4082b9f98f63fd2db98a521356674c1eecb36d530eef8e'
assert digest(WORK / 'render/项目报告.pptx') == baseline
assert digest(ROOT / 'docs/delivery/assets/项目报告.pptx') == baseline

# A compact overview complements the full-page images and PDF.
overview = Image.new('RGB', (1600, 9 * 250), '#041F3B')
draw = ImageDraw.Draw(overview)
for i in range(count):
    with Image.open(OUT / f'slide-{i+1:02}.png') as im:
        im = im.resize((400, 225), Image.Resampling.LANCZOS)
        x, y = (i % 4) * 400, (i // 4) * 250
        overview.paste(im, (x, y))
        draw.text((x + 10, y + 230), f'{i+1:02}', fill='#57F1FF')
overview.save(OUT / 'overview.png')
result = {
    'pptx_sha256': digest(ppt),
    'pdf_sha256': digest(OUT / 'PIXIU项目报告-科技风试作版.pdf'),
    'reference_pdf_sha256': digest(WORK / 'render/reference/ABC公司产品宣传路演PPT.pdf'),
    'pages': count, 'reference_pages': 20,
    'checks': ['ZIP CRC and XML parse', 'all input hashes',
               'retained and explicitly removed source pages accounted for', 'original screenshot bytes embedded',
               'no template identity in XML', 'no embedded workbooks or external links',
               '34 main topics present above body', '34 folios and 25 chapter navigation bars', 'production footnotes removed', 'two flagship names and dedicated feature pages',
               '54 full-page PNGs verified', 'formal candidate and asset unchanged', 'user-refined shapes preserved outside requested content edits; chapter artwork copied'],
    'visual_review': 'See abc-style-review.md. XML checks cannot inspect raster identity or layout.',
    'rendered_pages': rendered,
}
(WORK / 'review/abc-trial-validation.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'rendered_pages'}, ensure_ascii=False))
