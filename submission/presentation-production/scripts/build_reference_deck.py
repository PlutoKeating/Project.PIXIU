"""Create an editable PIXIU trial by copying selected ABC artwork and layouts.

No original company text, product photos, charts, logos, notes or embedded
workbooks are imported. Only explicitly selected decorative elements are copied.
"""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import hashlib
import json
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE as S, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'submission/presentation-production'
REF = WORK / 'reference/ABC公司产品宣传路演PPT.pptx'
OUT = WORK / 'render/abc-trial'
OUT.mkdir(parents=True, exist_ok=True)
ref = Presentation(REF)
prs = Presentation()
# Keep source theme colors so copied gradients and 3D effects retain their palette.
for rel in ref.slides[4].slide_layout.slide_master.part.rels.values():
    if rel.reltype.endswith('/theme'):
        source_theme = rel.target_part.blob
        break
for rel in prs.slide_master.part.rels.values():
    if rel.reltype.endswith('/theme'):
        rel.target_part._blob = source_theme
prs.slide_width, prs.slide_height = ref.slide_width, ref.slide_height
C, WHITE, GOLD, PALE = '57F1FF', 'FFFFFF', 'FFDCAB', 'C4DDED'
BG, PANEL, BLUE = '04264D', '07426A', '007AC1'
FONT = 'Microsoft YaHei'
NSR = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
manifest = {'reference_sha256': hashlib.sha256(REF.read_bytes()).hexdigest(), 'slides': []}
original = json.loads((WORK / 'review/build-manifest.json').read_text())['slides']
inputs = {REF, Path(__file__).resolve(), WORK/'review/build-manifest.json', WORK/'render/项目报告.pptx'}

def xml(tag, **attrs):
    e = OxmlElement(tag)
    for k, v in attrs.items(): e.set(k, str(v))
    return e

def clone(s, page, idx, x=None, y=None, w=None, h=None):
    src = ref.slides[page-1]
    e = deepcopy(src.shapes[idx]._element)
    # Remove unrelated metadata; never carry author tags or executable links.
    for tag in ('p:custDataLst', 'a:hlinkClick', 'a:hlinkMouseOver', 'p:extLst', 'a:extLst'):
        for z in e.xpath('.//' + tag): z.getparent().remove(z)
    for b in e.xpath('.//a:blip'):
        rid = b.get('{'+NSR+'}embed')
        if rid:
            _, new_id = s.part.get_or_add_image_part(BytesIO(src.part.related_part(rid).blob))
            b.set('{'+NSR+'}embed', new_id)
    for t in e.xpath('.//a:t'): t.text = ''
    for tag in ('p:cNvPr',):
        for el in e.xpath('.//' + tag):
            el.set('id', str(s.shapes._next_shape_id + len(e.xpath('.//p:cNvPr'))))
            el.set('name', f'Copied decorative artwork {page}-{idx}')
            for key in ('descr', 'title'): el.attrib.pop(key, None)
    s.shapes._spTree.insert_element_before(e, 'p:extLst')
    a = s.shapes[-1]
    for name, val in [('left', x), ('top', y), ('width', w), ('height', h)]:
        if val is not None: setattr(a, name, Inches(val))
    manifest['slides'][list(prs.slides).index(s)]['copied_artwork'].append([page, idx])
    return a

def shape(s, x, y, w, h, color=PANEL, kind=S.RECTANGLE, border=None, alpha=None):
    a = s.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if color:
        a.fill.solid(); a.fill.fore_color.rgb = RGBColor.from_string(color)
        if alpha is not None: a._element.spPr.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr').append(xml('a:alpha', val=alpha))
    else: a.fill.background()
    if border: a.line.color.rgb = RGBColor.from_string(border); a.line.width = Pt(.7)
    else: a.line.fill.background()
    if kind == S.ROUNDED_RECTANGLE: a.adjustments[0] = .10
    return a

def txt(s, t, x, y, w, h=.45, size=22, color=WHITE, bold=False, align=None, font=FONT):
    a = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = a.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, line in enumerate(t.split('\n')):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line; p.font.name = font; p.font.size = Pt(size); p.font.bold = bold
        p.font.color.rgb = RGBColor.from_string(color); p.space_after = Pt(6); p.line_spacing = 1.12
        if align is not None: p.alignment = align
        for r in p.runs: r._r.get_or_add_rPr().append(xml('a:ea', typeface=font))
    return a

def center(s, t, x, y, w, h=.45, size=22, color=WHITE, bold=True):
    return txt(s,t,x,y,w,h,size,color,bold,PP_ALIGN.CENTER)

def line(s,x1,y1,x2,y2,color=C,width=1.5,arrow=False):
    a=s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Inches(x1),Inches(y1),Inches(x2),Inches(y2))
    a.line.color.rgb=RGBColor.from_string(color);a.line.width=Pt(width)
    if arrow: a.line._get_or_add_ln().append(xml('a:tailEnd',type='triangle'))
    return a

def panel(s,x,y,w,h):
    # Copy the original translucent gradient panel and its glowing cap.
    clone(s,8,1,x,y,w,h)
    clone(s,8,2,x+w*.35,y,w*.3,0)

def label(s,t,x,y,w,color=C):
    shape(s,x,y,w,.46,BLUE,kind=S.ROUNDED_RECTANGLE,alpha=65000)
    center(s,t,x+.07,y+.07,w-.14,.32,16 if '，' in t else 18,color)

def foot(s,t):
    s.notes_slide.notes_text_frame.text += '\n' + t

def note(s,t):
    s.notes_slide.notes_text_frame.text += '\n' + t

def shot(s,name,x,y,w,h):
    p=ROOT/'docs/delivery/assets/operations/03-current-workflows'/name
    if p.read_bytes().startswith(b'version https://git-lfs'): p=WORK/'assets'/name
    inputs.add(p)
    from PIL import Image
    iw,ih=Image.open(p).size
    scale=min(w/iw,h/ih);dw,dh=iw*scale,ih*scale
    xx=x+(w-dw)/2;yy=y+(h-dh)/2
    shape(s,xx-.035,yy-.035,dw+.07,dh+.07,None,border=C)
    a=s.shapes.add_picture(str(p),Inches(xx),Inches(yy),Inches(dw),Inches(dh))
    manifest['slides'][-1]['screenshots'].append(str(p.relative_to(ROOT)))
    return a

TITLES = ['PIXIU · 貔貅','汇报导览','多设备 Agent 的记忆断点','需求缺口与方案回应','桌面智能体记忆中枢','业务与技术全景','两大核心亮点','自动记忆，持续整合','场景示例 · 账单检索','偏好演进与版本历史','记忆共享，分布互连','持续记忆技术体系','多源知识接入','知识结构与来源关联','三路混合检索','记忆阶段流转','双层冲突治理','去中心化同步协议','全生命周期安全','智能体记忆生命周期','原生部署与兼容路径','真实操作案例','活动资料与任务要素','自动记忆，持续整合｜跨会话召回','自动记忆，持续整合｜更正审批','场景应用价值','开发基线量化评测','记忆共享，分布互连｜三端收敛','验证结果与待测范围','服务模式与持续运营','商业试点路线','PIXIU · 貔貅']
SIDE = {5,9}
CUSTOM = {1,2,6,12,22,27,30,31,32}

def gradient(element, colors=('E9FFFF','57F1FF','18A4D3'), angle=5400000):
    for tag in ('a:solidFill','a:gradFill','a:noFill'):
        for e in element.findall(tag, element.nsmap): element.remove(e)
    fill=xml('a:gradFill',rotWithShape='1');stops=xml('a:gsLst')
    for i,c in enumerate(colors):
        stop=xml('a:gs',pos=round(i*100000/(len(colors)-1)));stop.append(xml('a:srgbClr',val=c));stops.append(stop)
    fill.append(stops);fill.append(xml('a:lin',ang=angle,scaled='1'));element.append(fill)

def arttext(s,t,x,y,w,h=.7,size=36,align=PP_ALIGN.CENTER,gold=False):
    a=txt(s,t,x,y,w,h,size,C,True,align)
    for para in a.text_frame.paragraphs:
        for run in para.runs:
            r=run._r.get_or_add_rPr();gradient(r,('FFFFFF','FFE7A6','EFC773') if gold else ('FFFFFF','9CF9FF','18BDE5'))
            effects=xml('a:effectLst');shadow=xml('a:outerShdw',blurRad='25000',dist='25000',dir='5400000',algn='ctr',rotWithShape='0')
            col=xml('a:srgbClr',val='001128');col.append(xml('a:alpha',val=65000));shadow.append(col);effects.append(shadow);r.append(effects)
    return a

def frame(s,x,y,w,h):
    a=shape(s,x,y,w,h,PANEL,S.SNIP_2_SAME_RECTANGLE,C,65000)
    gradient(a._element.spPr,('095976','06335A','073B60'),0)
    for xx,yy in [(x,y+.17),(x+w-.035,y+h-.65)]:shape(s,xx,yy,.035,.48,C)
    return a

def medallion(s,t,x,y,w=1.0):
    a=shape(s,x,y,w,w,'05698F',S.HEXAGON,C);gradient(a._element.spPr,('5FF6F6','1079A7','033962'))
    arttext(s,t,x+.04,y+w*.30,w-.08,w*.42,22)

def chip(s,x,y,w=1.5,title='PIXIU'):
    # AI-created concept illustration; labels and surrounding circuitry remain editable.
    path=WORK/'assets/memory-core-illustration.png';inputs.add(path)
    s.shapes.add_picture(str(path),Inches(x-.25*w),Inches(y-.52*w),width=Inches(w*1.5),height=Inches(w*1.25))
    arttext(s,title,x-.3,y+w*.46,w+.6,.30,16)
    manifest['slides'][-1].setdefault('illustrations',[]).append(str(path.relative_to(ROOT)))

def base(title,chapter=0,tab=0,sources=(),cover=False):
    s=prs.slides.add_slide(prs.slide_layouts[6]);n=len(prs.slides);title=TITLES[n-1]
    manifest['slides'].append({'page':n,'title':title,'source_pages':list(sources),'copied_artwork':[],'screenshots':[]})
    if cover:
        clone(s,1,0);clone(s,1,1);clone(s,1,15)
    else:
        master=ref.slides[4].slide_layout.slide_master
        s.shapes.add_picture(BytesIO(master.part.related_part('rId4').blob),0,0,prs.slide_width,prs.slide_height)
        # Chapter is a quiet folio; each page determines its own title composition.
        if n not in CUSTOM and n not in SIDE:
            if n in {2,7,15,19,26,29}:
                clone(s,16,23,.0,.40,13.33,.91)
                arttext(s,title,.8,.56,11.73,.7,35)
            else:
                clone(s,6,3,.7,1.25,11.9,.38)
                arttext(s,title,.8,.52,11.73,.7,37)
    notes=[]
    for n in sources:notes.append(f'原提交稿第{n}页：'+original[n-1].get('notes',''))
    notes.append('实拍为PIXIU 0.1.12银河麒麟V11公开合成资料；示意图不代表新的实测结果。')
    s.notes_slide.notes_text_frame.text='\n'.join(notes)
    return s

def device(s,x,y,w,title,body='本地记忆副本'):
    shape(s,x,y,w,w*.56,'062E50',S.ROUNDED_RECTANGLE,C)
    shape(s,x+.10,y+.10,w-.20,w*.56-.20,'0A5275',border='2386A3')
    center(s,title,x+.15,y+.24,w-.3,.45,22,C)
    center(s,body,x+.15,y+.76,w-.3,.45,12,PALE,False)
    shape(s,x+w*.44,y+w*.56,.12,.16,C)
    shape(s,x-.12,y+w*.56+.16,w+.24,.12,BLUE,S.TRAPEZOID,C)

def steps(s,items,y=2.15,x=.65,w=3.8,h=3.95,gap=.32):
    for i,(title,body) in enumerate(items):
        xx=x+i*(w+gap);panel(s,xx,y,w,h)
        center(s,f'{i+1:02}',xx+.2,y+.25,w-.4,.65,39,C)
        center(s,title,xx+.2,y+1.0,w-.4,.55,24,GOLD)
        txt(s,body,xx+.28,y+1.85,w-.56,h-2.0,19,WHITE)
        if i<len(items)-1: clone(s,7,24,xx+w+.015,y+1.6,gap-.03,.29)

# 01 – Copy the original cover stage; replace product hardware with editable devices.
s=base('PIXIU · 貔貅',sources=[1],cover=True)
txt(s,'PIXIU',.7,.42,2,.45,27,C,True)
center(s,'PIXIU · 貔貅',.55,1.28,12.2,1.05,76,C,True)
arttext(s,'自动记忆，持续整合  /  记忆共享，分布互连',1,2.52,11.3,.65,28)
center(s,'面向麒麟 OS Agent 的去中心化记忆系统设计与实现',1.1,3.25,11.1,.5,23,PALE,False)
for x,y,w,t in [(1.0,4.32,2.55,'书房 Agent'),(5.1,4.68,2.85,'客厅 Agent'),(9.5,4.32,2.55,'随身 Agent')]:
    clone(s,1,5,x-.35,y+.68,w+.7,1.55)
    device(s,x,y,w,t,'知识 · 来源 · 版本')

# 02 – Editorial chapter index, using a large original digital-vortex illustration.
s=base('',sources=[2])
clone(s,18,22,6.10,1.50,6.75,4.47)
arttext(s,'汇报导览',.72,.67,5.4,.85,48,PP_ALIGN.LEFT)
for i,(t,b) in enumerate([('场景需求','持续记忆的使用背景'),('方案架构','智能体与记忆的分工'),('功能亮点','两大核心能力'),('技术实现','数据、算法与边界'),('案例验证','完整操作与量化证据'),('商业探索','部署服务与试点路径')]):
    y=2.45+i*.62
    arttext(s,f'0{i+1}',.78,y,.65,.43,25)
    txt(s,t,1.66,y+.02,2.2,.39,22,WHITE,True)
    txt(s,b,4.00,y+.08,3.45,.32,15,PALE)
    line(s,1.66,y+.48,6.92,y+.48,'226186',.6)
a=arttext(s,'自动记忆，持续整合',7.12,5.06,5.5,.76,29,PP_ALIGN.LEFT)
for r in a.text_frame.paragraphs[0].runs:r.font.italic=True;r._r.get_or_add_rPr().set('spc','160')
a=arttext(s,'记忆共享，分布互连',8.22,5.98,4.7,.76,29,PP_ALIGN.LEFT)
for r in a.text_frame.paragraphs[0].runs:r.font.italic=True;r._r.get_or_add_rPr().set('spc','160')
for i in range(3):shape(s,7.31+i*.23,6.18,.13,.32,C,S.PARALLELOGRAM)
line(s,7.16,5.91,11.52,5.91,'2386A3',.8)

# 03 – Introduce the person, fragmented context and the product's purpose.
s=base('',1,0,[3])
txt(s,'设想一位在家办公的用户：书房处理文件，客厅核对安排，出门使用笔记本。\n三台设备都有 Agent（智能助手），但资料、对话和更正记录可能各留一处。',.76,1.98,11.85,.91,20,WHITE)
for i,(place,title,body) in enumerate([
    ('书房','01  保存过，还要重新交代','以家庭账单为例：用户把清单交给书房\n的助手。换个会话或设备，若没有持续\n记忆，就得重新找文件、补充背景。'),
    ('客厅','02  想查询，却缺少上下文','到了客厅，他只记得“水电燃气花了钱”。\n这里的助手需要找到先前的明细和来源，\n才能核对开销，而非让用户从头描述。'),
    ('随身','03  已更正，旧记录仍在','出门后，他发现其中一项金额有误。\n如果更新只留在笔记本，其他助手仍可能\n沿用旧信息；更正需要跨设备接续。')]):
    x=.66+i*4.20
    clone(s,1,5,x+.07,3.96,3.67,1.03)
    device(s,x+.72,3.10,2.27,place,'Agent · 本地信息')
    txt(s,title,x,4.95,3.86,.40,20,C,True)
    txt(s,body,x,5.48,3.90,.98,15,WHITE)
center(s,'PIXIU 为 Agent 持续保存、整合记忆，并在可信设备间按授权共享。',.72,6.60,11.89,.37,20,C)
center(s,'同样的需求，也存在于项目资料、会议记录和活动安排中。',.72,7.02,11.89,.28,14,PALE,False)
note(s,'本页为需求引入：设想用户在多台设备间使用 Agent，但缺乏持续、共享记忆时会反复说明背景、丢失来源或使用旧版本。家庭账单仅为场景示例，不是产品专用领域或新增实测。共享必须经过授权，断连期间不保证即时一致。')

# 04 – Directly copy the pain/solution two-row composition.
s=base('',1,1,[4])
for y in (2.0,4.35):frame(s,.55,y,12.23,1.72)
for y,t in [(2.51,'需求缺口'),(4.86,'方案回应')]:arttext(s,t,.70,y,1.9,.52,23)
for i,(a,b,c,d) in enumerate([('多源资料分散','文件、工具与行为\n来源格式不同','统一接入','清洗、标准化、质量校验'),('知识偏好演变','新旧通知与偏好\n存在冲突','版本与来源','保留历史，更正经过审批'),('跨域使用需求','新会话、多设备\n不同权限范围','可信连续性','按范围召回，授权后共享')]):
    x=2.9+i*3.24
    center(s,a,x,2.26,2.97,.45,23,GOLD)
    center(s,b,x,2.85,2.97,.65,17,WHITE,False)
    a=shape(s,x+1.35,3.82,.26,.46,C,S.CHEVRON);a.rotation=90;gradient(a._element.spPr,('E9FFFF','57F1FF','159EC4'))
    label(s,c,x,4.60,2.97)
    center(s,d,x,5.35,2.97,.46,16,WHITE,False)

# 05 – Large product screenshot, asymmetrical three statements.
s=base('为桌面智能体，接上一份持续可用的记忆',2,0,[5])
panel(s,.6,1.92,8.0,4.55);shot(s,'shared-workspace.png',.82,2.12,7.55,4.12)
for i,(t,b) in enumerate([('自动记忆，持续整合','后台理解资料，关联既有记忆\n新建知识，提出更正与合并'),('记忆共享，分布互连','可信设备之间共享 Agent 记忆\n各端独立保存，重连补齐差异')]):
    y=2.14+i*2.10
    arttext(s,t,8.98,y,3.90,.56,23,PP_ALIGN.LEFT)
    txt(s,b,9.01,y+.80,3.80,1.12,17)
center(s,'来源追溯 · 偏好适配 · 授权控制',8.85,6.26,4.05,.40,16,C)
note(s,'自动记忆，持续整合对应受控 Dreaming：私人范围内后台理解与整合，更正和合并须审批。记忆共享，分布互连对应 shared 范围的分布式 Agent 记忆共享；私人记忆不自动共享。')

# 06 – Bespoke panoramic architecture, inspired by the exact reference slide 6.
s=base('',2,1,[6,21])
clone(s,6,3,.6,.88,12.1,.37);arttext(s,'业务与技术全景',1.4,.29,10.5,.68,39)
for y,h in [(1.42,1.5),(3.10,1.49),(4.78,1.5)]:frame(s,.36,y,12.61,h)
for y,n,t,b in [(1.70,'01','交互与任务层','宿主 · Runtime · 工具'),(3.36,'02','原创记忆引擎','知识 · 检索 · 对等同步'),(5.04,'03','存储与平台层','数据库 · 系统能力 · 部署')]:
    arttext(s,n,.58,y,.75,.5,27);txt(s,t,1.4,y,2.83,.43,23,WHITE,True);txt(s,b,1.42,y+.58,2.85,.3,14,PALE)
chip(s,6.10,2.00,1.35,'Agent')
for x,t in [(4.38,'会话消息'),(8.28,'规划与工具')]:
    label(s,t,x,1.89,1.52)
line(s,5.89,2.1,5.95,2.1,C,2,True);line(s,7.88,2.1,8.19,2.1,C,2,True)
txt(s,'会话生命周期\n公共 API 接入',10.38,1.75,2.1,.85,18,C,True)
# Browser-like memory workbench instead of three plain text boxes.
a=shape(s,4.40,3.25,5.58,1.18,'07325A',S.ROUNDED_RECTANGLE,'35B9D3');gradient(a._element.spPr,('074878','062B52'),0)
for i,c in enumerate(['F77469','F7D27A','6EDCA6']):shape(s,4.56+i*.15,3.37,.07,.07,c,S.OVAL)
txt(s,'PIXIU MEMORY ENGINE',5.20,3.32,3.78,.25,13,C,True)
for i,t in enumerate(['知识与偏好','三路检索','CRDT 同步']):
    label(s,t,4.58+i*1.74,3.84,1.58)
txt(s,'来源与版本关联\n授权与审批约束',10.38,3.45,2.1,.85,18,C,True)
for i,(t,b) in enumerate([('SQLite','来源 · 版本 · 审计'),('系统双 SDK','向量化 · 向量检索'),('单一安装包','签名升级 · 故障恢复')]):
    x=4.46+i*1.90
    shape(s,x,5.02,1.69,.46,'076293',S.BEVEL,C);center(s,t,x,5.10,1.69,.3,17,C)
    center(s,b,x-.10,5.67,1.90,.32,12,WHITE,False)
txt(s,'麒麟原生优先\nDebian 兼容路径',10.38,5.16,2.1,.85,18,C,True)
arttext(s,'智能体宿主 × 原创记忆 × 可信设备',.5,6.60,12.33,.5,27)

# 07 – Two flagship capabilities with equal visual prominence.
s=base('',3,0,[7])
for x in [.60,6.94]:
    frame(s,x,2.02,5.79,4.80)
for x,n,t,d in [(.60,'01','自动记忆，持续整合','后台理解与记忆整合'),(6.94,'02','记忆共享，分布互连','分布式多设备 Agent 记忆共享')]:
    medallion(s,n,x+.24,2.27,.70)
    arttext(s,t,x+1.12,2.34,4.26,.52,24,PP_ALIGN.LEFT)
    txt(s,d,x+.31,3.02,5.17,.43,21,WHITE,True)
chip(s,2.65,4.05,1.22,'Dreaming')
for x,t in [(1.00,'理解资料'),(2.78,'关联记忆'),(4.56,'整合更新')]:
    label(s,t,x,5.04,1.42)
center(s,'新知识按授权保存 · 更正与合并先审批',.89,5.85,5.20,.44,17,WHITE,False)
center(s,'资料有变化，记忆接续更新',.89,6.32,5.20,.34,19,C)
# Three compact native device interfaces linked in a peer mesh.
for x1,y1,x2,y2 in [(9.87,4.16,8.13,4.73),(9.87,4.16,11.62,4.73),(8.83,5.03,10.92,5.03)]:
    line(s,x1,y1,x2,y2,C,1.4)
for x,y,t in [(9.21,3.67,'Agent A'),(7.48,4.60,'Agent B'),(10.96,4.60,'Agent C')]:
    shape(s,x,y,1.34,.64,'07496B',S.ROUNDED_RECTANGLE,C)
    center(s,t,x+.04,y+.12,1.26,.23,14,C)
    center(s,'本地记忆',x+.04,y+.40,1.26,.17,9,WHITE,False)
    shape(s,x+.60,y+.64,.14,.10,C)
    shape(s,x-.06,y+.74,1.46,.06,BLUE,S.TRAPEZOID,C)
center(s,'授权共享 · 对等同步 · 离线保留本地副本',7.23,5.85,5.20,.44,17,WHITE,False)
center(s,'换一台设备，Agent 接着使用记忆',7.23,6.32,5.20,.34,19,C)
note(s,'两项是产品主推能力。Dreaming 不等同文件整理或模型训练：新资料触发受控理解、检索关联、新建或更正/合并计划。共享仅在授权 shared 范围发生，不将私人 Dreaming 结果自动广播。')

# 08 – Dreaming is an understanding/consolidation loop, beyond directory capture.
s=base('',3,0,[8])
arttext(s,'后台理解与记忆整合',.91,2.08,5.70,.52,27,PP_ALIGN.LEFT)
shot(s,'dreaming-review.png',.90,2.85,5.63,3.50)
center(s,'新旧内容对照 · 用户审批',.90,6.40,5.63,.32,18,C)
for i,(t,b) in enumerate([
    ('理解资料','按块理解已授权内容\n保留事实与原始来源'),
    ('关联记忆','检索、读取已有记录\n形成新建、更正或合并方案'),
    ('整合更新','新建按授权保存\n更正与合并经审批后生效')]):
    y=2.15+i*1.50
    label(s,f'{i+1:02}  {t}',7.06,y,5.19)
    txt(s,b,7.15,y+.60,5.0,.81,18)
note(s,'产品名称：自动记忆，持续整合。技术名称：Dreaming。目录监视是当前触发入口，核心是模型驱动的受控记忆整合。后台仅处理任务授权的私人资料；不宣称睡眠调度、无依据联想或模型参数训练。更正与合并必须读取原记忆、冻结版本并经过用户审批。截图为更正审批实拍，不作为合并实测证明。')

# 09 – Bill: screenshot left, oversized number right.
s=base('得到答案，也能找到依据',3,1,[10])
panel(s,.65,1.93,7.0,4.53);shot(s,'bill-recall.png',.88,2.12,6.54,4.14)
center(s,'家庭账单合计',7.95,2.05,4.7,.48,24,WHITE)
center(s,'434.50',7.92,2.83,4.75,1.0,65,C)
center(s,'元 · 本例合计',8.05,3.85,4.5,.36,18,PALE,False)
for i,(t,n) in enumerate([('电费','210.00'),('水费','68.50'),('燃气','156.00')]):
    y=4.5+i*.57;txt(s,t,8.3,y,1.5,.35,19);txt(s,n,10.4,y,1.7,.35,21,GOLD,True,PP_ALIGN.RIGHT);line(s,8.2,y+.43,12.2,y+.43,'1C678D',.7)
foot(s,'语义找到相关知识，结构核算金额，来源支持复核')
note(s,'实拍为九月公开合成账单；不能视为四月家庭真实消费。')

# 10 – Preferences with version trail.
s=base('理解现在的偏好，保留变化的来路',3,2,[11,16])
panel(s,.65,1.93,7.15,4.55);shot(s,'preference-history.png',.83,2.1,6.77,4.2)
for i,(v,t,b) in enumerate([('v1','简洁回答','初始表达被提取'),('v2','仍然简洁','保留更新记录'),('v3','详细说明','当前值用于后续会话')]):
    y=2.15+i*1.39;shape(s,8.35,y,.61,.61,BLUE,S.OVAL,C);center(s,v,8.39,y+.14,.53,.32,19,C)
    txt(s,t,9.25,y,3.25,.42,24,GOLD,True);txt(s,b,9.25,y+.58,3.28,.36,17)
    if i<2:line(s,8.65,y+.62,8.65,y+1.37,C,1.2,True)
foot(s,'从用户原话提取；按当前有效版本和授权范围适配')
note(s,'安全策略由明确配置管理，模型不能随意放宽授权。')

# 11 – P2P product evidence.
s=base('换一台设备，接着使用同一份经验',3,3,[12])
# Three illustrated interfaces form a complete peer mesh; this is a topology diagram.
for x1,y1,x2,y2 in [(4.9,3.23,2.95,4.78),(8.43,3.23,10.4,4.78),(4.2,5.35,9.1,5.35)]:
    line(s,x1,y1,x2,y2,C,2)
for x,y,t in [(4.98,1.92,'设备 A · 书房'),(.85,4.28,'设备 B · 客厅'),(9.12,4.28,'设备 C · 随身')]:
    device(s,x,y,3.35,t,'')
    label(s,'会话   记忆   设备',x+.24,y+.73,2.87)
    for j,(a,b) in enumerate([('活动安排','时间 / 地点'),('资料来源','原文 / 版本')]):
        txt(s,a,x+.28,y+1.28+j*.25,1.12,.22,10,C,True)
        txt(s,b,x+1.53,y+1.28+j*.25,1.54,.22,10,WHITE)
arttext(s,'Agent 共享记忆',4.55,4.32,4.23,.48,27)
center(s,'本地副本 · 对等连接',4.61,5.83,4.11,.37,17,WHITE,False)
center(s,'分布式多设备 Agent 记忆共享',2.4,6.67,8.53,.43,23,C)
note(s,'三台电脑界面为可编辑协作示意，非三端截图。接收端实拍见产品页；三端验证见第28页。')

# 12 – Chapter hero, keeping ABC's technology illustration.
s=base('技术实现',cover=True,sources=[13,14,15,16,17,18,19,20,21,22])
clone(s,18,22,6.80,1.25,6.0,4.0)
txt(s,'04',.85,1.23,4,1.4,102,C,True);arttext(s,'持续记忆技术体系',.9,3.03,10,.78,44,PP_ALIGN.LEFT)
txt(s,'数据有结构，更新有依据，协作有边界',.93,4.18,11.2,.55,27,PALE)
for i,t in enumerate(['多源知识','混合检索','版本流转','对等同步','安全部署']):label(s,t,.92+i*2.42,5.75,2.13)

# 13 – A circuit-board fan-in composition with native source icons and a glowing core.
s=base('',4,0,[13])
for i,(t,b) in enumerate([('对话与工具','用户原话 / 执行结果'),('文档与图片','附件 / 已授权目录'),('行为与配置','授权统计 / 手动记录')]):
    y=2.10+i*1.32
    medallion(s,str(i+1),.70,y,.85)
    arttext(s,t,1.80,y+.06,2.63,.44,23,PP_ALIGN.LEFT)
    txt(s,b,1.82,y+.65,2.85,.30,14,PALE)
    line(s,4.55,y+.58,5.04,y+.58,C,1);line(s,5.04,y+.58,5.56,3.98,C,1)
clone(s,1,5,4.82,3.72,3.60,2.20);chip(s,5.72,3.24,1.65,'接入核心')
arttext(s,'清洗 · 标准化 · 质量校验',4.72,1.95,4.12,.43,19)
center(s,'来源 / 幂等键 / 授权范围',4.89,5.40,3.70,.55,17,WHITE,False)
for i,(t,b) in enumerate([('Evidence','内容 · 依据 · 位置'),('Knowledge','结构 · 状态 · 版本'),('Preference','类别 · 当前值 · 历史')]):
    y=2.10+i*1.32
    line(s,7.75,3.98,8.29,y+.58,C,1);line(s,8.29,y+.58,8.78,y+.58,C,1,True)
    frame(s,8.91,y,3.80,1.03)
    arttext(s,t,9.06,y+.13,3.49,.39,22)
    center(s,b,9.06,y+.65,3.49,.28,15,WHITE,False)
foot(s,'同一套来源、质量和权限约束，贯穿数据接入与后续使用')

# 14 – Knowledge topology.
s=base('一条事实，连着来源与可复用经验',4,0,[15])
for i,(t,b) in enumerate([('事实 FACT','时间 · 地点 · 金额'),('流程 WORKFLOW','先做什么 · 后做什么'),('案例 CASE','问题 · 处理 · 结果'),('模板 TEMPLATE','可重复使用的结构')]):
    x=.65+i*3.2;panel(s,x,2.0,2.9,1.25);center(s,t,x+.1,2.22,2.7,.33,18,C);center(s,b,x+.1,2.78,2.7,.3,14,WHITE,False)
shape(s,5.05,3.75,3.22,1.80,'075C83',S.HEXAGON,C);center(s,'Knowledge',5.28,4.13,2.77,.45,26,WHITE);center(s,'状态 · 范围 · 版本',5.28,4.76,2.77,.4,17,C)
panel(s,.95,4.05,3.18,1.4);center(s,'Evidence',1.1,4.32,2.88,.43,26,C);center(s,'原文 / 原图 / 文档块',1.1,4.94,2.88,.35,16,WHITE,False)
line(s,4.18,4.7,5.0,4.7,C,2,True)
for y,t in [(3.63,'实体'),(4.55,'关系'),(5.47,'检索索引')]:
    line(s,8.3,4.66,9.25,y+.23,C,1.2,True);label(s,t,9.4,y,2.65)
foot(s,'来源与知识分开保存，通过关联保持追溯')

# 15 – Three retrieval channels, true source triptych artwork.
s=base('混合检索：语义找到，结构算清，来源可追',4,1,[14])
label(s,'当前问题 + 授权范围 + 时间条件 + 有效状态',1.45,1.95,10.43)
for i,(t,b) in enumerate([('关键词 FTS5','精确标题与词面匹配'),('向量 · 系统 SDK','找回语义相近的记忆'),('实体关系 Graph','沿类目关联商户与事实')]):
    x=.65+i*4.2;panel(s,x,2.80,3.8,2.23);center(s,f'0{i+1}',x+.2,3.03,3.4,.64,40,C);center(s,t,x+.15,3.85,3.5,.42,23,GOLD);center(s,b,x+.15,4.49,3.5,.3,16,WHITE,False)
    line(s,x+1.9,5.06,x+1.9,5.42,C,1.5,True)
label(s,'RRF 融合 → 词法与年月重排 → 明细过滤 / 聚合 → 附来源引用',.92,5.58,11.5)
foot(s,'检索子路径不额外调用生成式 LLM')
note(s,'完整助手的规划与回答仍可使用模型；当前重排为词法与业务年月规则，不宣称神经网络重排。')

# 16 – Stage memory as staggered three terraces.
s=base('短、中、长期记忆，接住不同时间尺度的任务',4,2,[17])
for i,(t,b,y) in enumerate([('短期 · 当前任务','本轮开始与结束\n服务当前任务上下文',3.15),('中期 · 阶段状态','压缩、切换与会话结束\n保留阶段内容和到期时间',2.6),('长期 · 持久知识','选择长期保留\n进入统一知识与检索管线',2.05)]):
    x=.7+i*4.18;clone(s,1,5,x-.17,y+1.16,4.02,1.95);frame(s,x,y,3.68,1.82);arttext(s,t,x+.16,y+.22,3.36,.5,23);center(s,b,x+.22,y+.89,3.24,.84,18,WHITE,False)
    if i<2:line(s,x+3.7,y+1.15,x+4.13,y+.61,C,2,True)
line(s,10.84,4.62,10.84,6.1);line(s,10.84,6.1,2.54,6.1);line(s,2.54,6.1,2.54,5.68,C,1.5,True)
foot(s,'长期知识按新问题召回，再注入当前会话')
note(s,'阶段记忆按到期规则清理；长期知识持续受授权、状态和遗忘控制。')

# 17 – Two conflict lanes.
s=base('两层冲突处理，让更新可解释、可核对',4,2,[18,9])
for x,t,b,c in [(.65,'副本层：同一知识 ID','版本向量判断因果\nLWW 选择确定的并发胜者','副本一致性'),(6.94,'业务层：不同记录矛盾','比较实体与字段\nNEW_WINS / MERGE / MANUAL','内容更新策略')]:
    panel(s,x,2.02,5.74,2.33);center(s,t,x+.2,2.3,5.34,.48,25,C);center(s,b,x+.25,3.03,5.24,1.0,20,WHITE,False)
    label(s,c,x+.1,4.67,5.54)
center(s,'物化正文、版本与来源',.82,5.57,5.34,.4,18,WHITE,False)
center(s,'更正方案冻结版本，用户批准后保存',6.95,5.57,5.74,.4,18,WHITE,False)
foot(s,'协议保证确定性，业务规则与人工审批共同维护内容质量')

# 18 – Sequence diagram.
s=base('对等同步：在线扩散，离线累积，重连对账',4,3,[19])
for x,t in [(1.08,'设备 A · 本地写入'),(5.08,'设备 B · 在线'),(9.08,'设备 C · 暂时离线')]:
    label(s,t,x,1.98,3.2);line(s,x+1.6,2.67,x+1.6,6.1,'24618B',1)
for y,x1,x2,t in [(3.03,2.68,6.68,'签名操作 → Gossip 推送'),(3.83,6.68,2.68,'确认收到 / 本地物化'),(4.68,10.68,2.68,'C 重连：交换摘要，发现缺失'),(5.53,2.68,10.68,'补齐操作 → CRDT 合并 → 重建索引')]:
    center(s,t,min(x1,x2),y-.39,abs(x2-x1),.3,16,WHITE,False);line(s,x1,y,x2,y,C,2,True)
foot(s,'私人范围不入同步队列；仅授权共享范围传播')
note(s,'配对身份 + TLS 1.3 双向认证 + 操作签名；离线期间不承诺即时一致。')

# 19 – Security gates over a glowing lifecycle path.
s=base('',4,4,[20])
line(s,1.64,3.09,11.67,3.09,C,2)
for i,(t,b) in enumerate([('采集授权','未授权不采集\n只读已选目录与来源'),('敏感过滤','规则识别与标记\n敏感共享写入拒绝'),('范围控制','个人与共享分开\n召回再次检查范围'),('精准遗忘','预览目标与范围\n确认后失效并删向量')]):
    x=.67+i*3.2
    clone(s,1,5,x+.40,3.22,2.05,1.31)
    medallion(s,f'0{i+1}',x+.97,2.50,1.05)
    arttext(s,t,x+.05,4.54,2.82,.49,26)
    center(s,b,x+.04,5.19,2.84,.78,17,WHITE,False)
clone(s,16,23,.67,6.31,12.0,.59)
center(s,'共享遗忘 → 墓碑传播 → 远端隐藏与向量删除',.9,6.43,11.52,.35,20,C)
note(s,'当前保留部分证据、关系及全文载荷；遗忘不等于物理擦除所有介质。云模型理解内容涉及外部推理服务。')

# 20 – Runtime with genuine tools screenshot.
s=base('让记忆真正进入智能体的任务循环',4,2,[21])
for i,(t,b) in enumerate([('任务开始','按问题召回有效记忆'),('上下文注入','范围 / 来源 / 字符预算'),('规划与工具','执行工具与审批'),('结果沉淀','对话 / 工具 / 阶段内容')]):
    x=.65+i*3.2;label(s,t,x,1.99,2.9);center(s,b,x,2.65,2.9,.35,15,PALE,False)
    if i<3:line(s,x+2.94,2.21,x+3.15,2.21,C,1.4,True)
panel(s,.65,3.35,6.28,3.03);shot(s,'agent-tools-completed.png',.82,3.52,5.94,2.68)
arttext(s,'上下文注入边界',7.36,3.8,5.25,.58,27)
txt(s,'保留来源与记忆实际使用记录\n按预算注入当前任务\n记忆文本不升级为系统指令',7.62,4.75,4.95,1.42,21)
foot(s,'通用任务能力复用上游，持续记忆与对等协作由 PIXIU 提供')

# 21 – Exact source technical-feature panel and proof panel composition.
s=base('',4,4,[22])
panel(s,.60,1.93,4.0,4.75);panel(s,4.97,1.93,7.76,4.75)
label(s,'部署能力',.85,2.14,3.50)
label(s,'原生验证与恢复记录',5.25,2.14,7.20)
for y,t,b in [(3.01,'银河麒麟 V11','Embedding / Vector Engine'),(4.23,'Debian 兼容','基本记忆读写与检索'),(5.45,'签名升级','版本校验与失败恢复')]:
    arttext(s,t,.88,y,3.44,.43,23)
    center(s,b,.79,y+.54,3.62,.37,15,WHITE,False)
    if y<5:line(s,1.25,y+.99,3.95,y+.99,'2386A3',.7)
shot(s,'sdk-version.png',5.30,2.95,7.06,1.70)
arttext(s,'47',5.62,5.23,1.8,.94,62)
txt(s,'条记忆',7.8,5.22,3.8,.41,24,WHITE)
txt(s,'升级与恢复前后摘要一致',7.8,5.86,4.38,.42,20,WHITE)
note(s,'0.1.12 升级恢复实测；严格原生画像缺少 SDK 即失败。常驻资源、CPU 和索引增长仍需专项测量。')

# 22 – Case chapter with original atmospheric artwork.
s=base('完整用户案例',cover=True,sources=[25,26,27,28])
clone(s,18,21,7.1,2.68,5.83,3.51)
txt(s,'05',.85,1.08,3.4,1.33,99,C,True);arttext(s,'真实操作案例',.9,2.77,10.6,.85,48,PP_ALIGN.LEFT)
arttext(s,'星河观测活动记录',.96,4.05,8.8,.62,31,PP_ALIGN.LEFT)
txt(s,'资料采集  /  跨会话查询  /  更正复用',.96,5.26,10.8,.57,23,PALE)
note(s,'真实软件操作，使用公开合成的星河观测活动资料。案例展示通用记忆能力，不限定产品行业。')

# 23 – Case setup.
s=base('起点：组织者要安排时间、器材与预算',5,0,[25])
panel(s,.65,1.97,6.3,4.48);shot(s,'directory-source.png',.87,2.16,5.86,4.08)
label(s,'星河观测活动 · 初始安排',7.31,2.04,5.33)
for y,t,b in [(2.85,'11月8日 19:00','社区天文台三层'),(4.13,'2680 元','器材预算'),(5.35,'领手册 → 检查 → 分组 → 归还','可复用的器材流程')]:
    txt(s,t,7.48,y,5.0,.5,27 if y<5 else 19,C,True);txt(s,b,7.5,y+.59,4.93,.34,18)
foot(s,'资料会更新、沟通跨会话，行动依据需要持续维护')

# 24 – Two real screens from source to recall.
s=base('保存资料 → 自动整理 → 新会话找回',5,0,[26])
panel(s,.60,1.95,5.78,4.97);panel(s,6.95,1.95,5.78,4.97)
label(s,'01  目录授权与资料采集',.80,2.14,5.38)
shot(s,'directory-folder.png',.87,2.85,5.24,1.42)
label(s,'活动记录 · 初始安排',.89,4.56,5.2)
for i,(a,b) in enumerate([('集合时间','11月8日 19:00'),('集合地点','社区天文台三层'),('器材预算','2680 元')]):
    y=5.25+i*.46;txt(s,a,1.02,y,1.4,.32,16,PALE);txt(s,b,2.72,y,3.1,.32,18,WHITE,True)
label(s,'02  新会话查询与来源核对',7.15,2.14,5.38)
shot(s,'directory-recall.png',7.17,2.88,5.34,3.53)
line(s,6.43,4.33,6.85,4.33,C,2,True)
center(s,'时间 · 地点 · 预算 · 来源',7.22,6.52,5.22,.30,17,C)
note(s,'同次实录：后台保存 1 条记忆；新会话返回初始时间、地点与 2680 元预算。')

# 25 – Approval and updated recall with explicit changes.
s=base('',5,1,[9,27])
for x,title,name in [(.60,'01  内容对照与审批','dreaming-review.png'),(6.95,'02  更新知识召回','updated-recall.png')]:
    panel(s,x,1.95,5.78,4.44);label(s,title,x+.18,2.14,5.42)
    shot(s,name,x+.19,2.91,5.40,3.23)
line(s,6.43,4.28,6.85,4.28,C,2,True)
for x,t,b in [(.65,'时间调整','11/8 19:00 → 11/15 19:30'),(4.86,'地点调整','三层 → 二层'),(9.07,'预算保留','2680 元')]:
    label(s,t,x,6.42,3.62)
    center(s,b,x,6.95,3.62,.27,15,WHITE,False)
note(s,'Dreaming 提出对照方案，用户批准后保存；更正以冻结的目标版本核验，避免误覆盖。')

# 26 – Transformation value table.
s=base('从一份通知，看到可重复使用的服务价值',5,1,[28])
for i,(t,a,b) in enumerate([('保存资料','需要再次说明文档背景','目录资料进入记忆，后续按需提问'),('核对安排','在多个文件和对话间查找','回答与来源相连，可以核对原文'),('接收变更','新旧通知混用、内容容易遗漏','先对照审批，再在新会话使用'),('延续经验','完成任务后，流程继续散落','知识与阶段保留支持后续复用')]):
    y=2.02+i*1.05;panel(s,.65,y,12,.82);txt(s,t,.88,y+.23,2.0,.37,22,C,True);txt(s,a,3.03,y+.25,3.96,.35,18,PALE);line(s,7.08,y+.43,7.70,y+.43,C,1.5,True);txt(s,b,7.93,y+.25,4.45,.36,17,WHITE)
foot(s,'少重复说明 · 更便于核对 · 更正更有序 · 经验可接续')
note(s,'以上为功能支持的定性价值；尚无真实用户对照实验量化节省时间或降低错误的比例。')

# 27 – Table plus measured-vs-target graph, preserving reference slide 16 framing.
s=base('',5,2,[23])
clone(s,16,23,0,.27,13.33,.84);arttext(s,'开发基线量化评测',.8,.43,11.73,.62,36)
for idx in [22,25,26,27,32,33]:clone(s,16,idx)
arttext(s,'样本与统计口径',.69,2.32,5.75,.40,24)
arttext(s,'质量指标与目标线',7.71,2.38,4.9,.35,21)
txt(s,'Debian portable  /  pixiu-family-expense-v1',.53,1.46,10.6,.39,20,PALE)
rows=[('评测项目','开发结果','样本 / 口径'),('偏好准确率','100%','15 / 15'),('知识召回率','100%','50 组检索均值'),('冲突正确率','96%','24 / 25'),('检索 P95','115 ms','1000 次查询')]
for i,(a,b,c) in enumerate(rows):
    y=2.99+i*.69
    if i==0:shape(s,.40,y,6.48,.57,'1673AB')
    for x,w,t in [(.58,2.07,a),(2.68,1.38,b),(4.21,2.45,c)]:txt(s,t,x,y+.13,w,.36,17 if i else 18,C if i and x==2.68 else WHITE,i==0)
    line(s,.4,y+.64,6.88,y+.64,'207BA1',.7)
label(s,'时延目标 ≤500 ms',.65,6.63,5.98)
# Native editable bars with copied 3D source bevel, on a zero-based percentage axis.
for v in [0,25,50,75,100]:
    y=6.49-v*.031
    line(s,7.79,y,12.69,y,'225274',.6);txt(s,str(v),7.29,y-.11,.41,.24,11,PALE,False,PP_ALIGN.RIGHT)
for i,(t,v,goal) in enumerate([('偏好',100,85),('召回',100,85),('冲突',96,88)]):
    x=8.11+i*1.54;h=v*.031
    clone(s,16,45,x,6.49-h,.62,h)
    arttext(s,f'{v}%',x-.12,6.00-h,.97,.35,22)
    center(s,t,x-.32,6.69,1.24,.26,15,WHITE,False)
    line(s,x-.2,6.49-goal*.031,x+.90,6.49-goal*.031,GOLD,2)
    txt(s,f'{goal}%',x+.68,6.49-goal*.031-.31,.56,.22,10,GOLD)
line(s,10.03,1.63,10.47,1.63,GOLD,2);txt(s,'目标值',10.59,1.46,1.8,.35,16,GOLD)
note(s,'历史 portable 合成数据评测；V11 同版最终质量、时延与泛化仍需验证。召回按指定 top-k，P95 为排序第 950 个耗时。')

# 28 – Three machine evidence, not invented metrics.
s=base('原生实测：三端断连并发，恢复后记录一致',5,3,[24])
for i,(t,b) in enumerate([('设备 A · v2','11/9 10:00\n二楼档案室'),('设备 B · v2','11/10 15:00\n三楼档案室'),('设备 C · v1','11/8 09:00\n一楼档案室')]):
    x=.65+i*4.2;panel(s,x,2.10,3.8,2.4);center(s,t,x+.15,2.38,3.5,.5,25,C);center(s,b,x+.2,3.2,3.4,1.0,22,WHITE,False)
    line(s,x+1.9,4.57,6.63,5.08,C,1.5,True)
label(s,'重连后均为 v2 · 11/10 15:00 · 三楼档案室',1.25,5.24,10.8)
foot(s,'同宿主三台独立 V11 虚拟机 · 云杉资料移交场景')
note(s,'约 30.5 秒为本次恢复观测值，非性能保证；证据来自 0.1.12 三端检查点与测试报告。')

# 29 – Evidence split (original split-pane style).
s=base('已验证的能力，与下一步要验证的范围',5,3,[22,23,24])
for x,t,items in [(.65,'0.1.12 · V11 已有实证',['系统双 SDK 增删查','自动记忆，持续整合｜更正审批','安装、签名升级与故障恢复','47 条恢复一致 / 三端断连并发']), (6.95,'专项待测范围',['最终同版四项量化指标','更多真实业务与对照实验','常驻资源、CPU 与索引增长','物理设备及复杂网络环境'])]:
    panel(s,x,2.02,5.73,4.28);label(s,t,x+.17,2.23,5.39)
    for i,a in enumerate(items):txt(s,f'{i+1:02}   {a}',x+.3,3.16+i*.68,5.13,.45,19,C if i==0 else WHITE)
foot(s,'每项结论对应自己的版本、环境和证据')
note(s,'局部检查通过不推出全部赛题验收通过；不同版本记录不合并冒充同版结果。')

# 30 – Source strategy composition: timeline, service descriptions and atmospheric illustrations.
s=base('',6,0,[29])
clone(s,18,39,2.16,.38,7.55,1.0);arttext(s,'服务模式与持续运营',1.53,.53,10.2,.64,36)
clone(s,18,27,.50,1.60,12.3,0)
for i,(t,b,c) in enumerate([('组织部署','访谈与环境适配\n资料范围与使用培训','按实施工作量讨论服务费'),('持续维护','兼容更新与故障处理\n资料流程与使用支持','按支持范围讨论年度服务'),('生态集成','应用与方案方协作\n共同适配真实业务','按集成与维护范围评估报价')]):
    x=.65+i*4.2
    a=shape(s,x+1.69,1.47,.27,.27,C,S.OVAL);gradient(a._element.spPr,('B2F9FF','1378B7'))
    clone(s,18,28,x,2.55,3.79,2.19)
    arttext(s,t,x,1.94,3.8,.50,27)
    txt(s,b,x+.18,2.81,3.42,.95,20,WHITE)
    txt(s,c,x+.18,4.02,3.42,.49,15,GOLD)
clone(s,18,22,.52,4.85,4.2,2.13);clone(s,18,21,4.71,4.85,4.04,2.13)
arttext(s,'部署适配\n持续服务',9.10,5.08,3.54,1.39,34)
note(s,'面向已有麒麟桌面、反复整理资料的小型组织。商业模式待验证；暂无付费客户、定价或盈利数据。')

# 31 – Original orbital composition, including every original card and gradient title.
s=base('',6,1,[30])
clone(s,13,2,.50,.35,12.30,1.16)
arttext(s,'商业试点路线',.83,.65,11.66,.62,38)
g=clone(s,13,9,.32,1.85,12.70,5.12)
# Replace the original card strings within their existing styled text shapes.
for cg,title,body in zip(list(g.shapes)[1:],['需求确认','有限试点','效果复核','成本核对','续用判断'],['角色访谈\n高频任务','约定资料范围\n确定支持边界','成功率与耗时\n记录实际差错','部署培训人时\n维护与推理费','使用意愿\n成本与续费']):
    title_shape=cg.shapes[2]
    ts=title_shape._element.xpath('.//a:t')
    if ts:ts[0].text=title
    # Preserve the template body paragraph style and its position.
    bs=cg.shapes[3];tf=bs.text_frame;tf.text=body
    for para in tf.paragraphs:
        para.alignment=PP_ALIGN.CENTER;para.font.name=FONT;para.font.size=Pt(16);para.font.color.rgb=RGBColor.from_string(WHITE)
        for run in para.runs:run.font.name=FONT;run.font.size=Pt(16)
# Original large orbital label uses the original text effect.
old=g.shapes[0].shapes[4]._element.xpath('.//a:t')
if old:old[0].text='商 业 试 点'
note(s,'拟议商业验证路径；尚无认证或合作声明。模型推理费用与承担方需单独约定。')

# 32 – Closing uses the original closing background and light beam.
s=base('让每一台设备的记忆，彼此相通。',cover=True,sources=[31])
clone(s,20,4,.6,4.76,12.0,.88)
center(s,'PIXIU · 貔貅',.7,1.2,11.9,.75,49,C)
arttext(s,'自动记忆，持续整合\n记忆共享，分布互连',.6,2.53,12.1,1.30,34)
center(s,'让每一台设备的记忆，彼此相通。',.6,4.13,12.1,.65,26,WHITE,False)
for x,t,d in [(1.15,'自动记忆，持续整合','后台理解与记忆整合'),(7.05,'记忆共享，分布互连','分布式多设备 Agent 记忆共享')]:
    label(s,t,x,5.55,5.15)
    center(s,d,x,6.16,5.15,.34,18,WHITE,False)
center(s,'聚财守忆',.7,6.76,11.9,.45,23,PALE,False)

# Page-specific title hierarchy; no sentence is used as a page title.
for n,s in enumerate(prs.slides,1):
    if n in SIDE:
        # Break the centred layout with a large two-part masthead and asymmetric rule.
        title=TITLES[n-1]
        arttext(s,title,.64,.57,10.0,.73,39,PP_ALIGN.LEFT)
        line(s,.68,1.47,8.30,1.47,C,1.3)

# Persistent chapter navigation, copied from the reference's native header artwork.
NAV_GROUPS = [
    ('场景需求', [('使用场景',[3]),('需求回应',[4])]),
    ('方案架构', [('产品定位',[5]),('技术全景',[6])]),
    ('功能亮点', [('两大亮点',[7]),('自动记忆，持续整合',[8]),('场景示例',[9]),('偏好演进',[10]),('记忆共享，分布互连',[11])]),
    ('技术实现', [('多源接入',[13]),('知识检索',[14,15]),('记忆流转',[16,17]),('对等同步',[18]),('安全部署',[19,21]),('任务循环',[20])]),
    ('案例验证', [('资料准备',[23]),('跨会话查询',[24]),('更正审批',[25]),('应用价值',[26]),('量化评测',[27]),('协作验证',[28,29])]),
    ('商业探索', [('服务模式',[30]),('试点路线',[31])]),
]
EXCLUDE_NAV = {1,2,12,22,32}
GLASS_PAGES = {8,10,14,17,18,20,28,29}
for n,s in enumerate(prs.slides,1):
    if n not in EXCLUDE_NAV:
        # Keep the approved body geometry; create room by moving only the title band.
        for a in list(s.shapes)[1:]:
            y=a.top/914400
            if n == 6:
                if y >= 1.40 or a.shape_type == 13:
                    a.top=Inches(1.98+(y-1.40)*.86)
                    a.height=int(a.height*.86)
                    if a.shape_type == 13:
                        old_width=a.width
                        a.width=int(a.width*.86)
                        a.left+=(old_width-a.width)//2
                    if a.has_text_frame:
                        for p in a.text_frame.paragraphs:
                            if p.font.size:p.font.size=int(p.font.size*.86)
                            for r in p.runs:
                                if r.font.size:r.font.size=int(r.font.size*.86)
                elif y > .15:
                    a.top=Inches(.96 if a.has_text_frame else 1.59)
                    if not a.has_text_frame:a.height=Inches(.25)
            elif n == 27:
                if y < 1.0:
                    a.top=Inches(.94 if not a.has_text_frame else 1.02)
                    a.height=Inches(.67)
                elif y < 1.90:a.top+=Inches(.30)
            elif n == 30:
                if y < 1.2:a.top+=Inches(.48)
                elif y < 1.8:a.top+=Inches(.26)
                elif y < 2.5:a.top+=Inches(.10)
            elif n == 31:
                if y < 1.4:
                    a.top=Inches(.93 if not a.has_text_frame else 1.00)
                    a.height=Inches(.73 if not a.has_text_frame else .65)
            elif y < 1.80:
                if a.has_text_frame and a.text:
                    a.top=Inches(.98);a.height=Inches(.60)
                elif a.height/914400 > .60:
                    a.top=Inches(.92);a.height=Inches(.72)
                else:
                    a.top=Inches(1.66);a.height=Inches(.22 if a.height else 0)
            if a.has_text_frame and a.text == TITLES[n-1]:
                for p in a.text_frame.paragraphs:
                    p.font.size=Pt(32)
                    for r in p.runs:r.font.size=Pt(32)
        # Source translucent dome and rotated side fins go behind the existing body.
        if n in GLASS_PAGES:
            additions=[]
            for idx,x,y,w,h in [(1,.46,1.91,12.41,4.90),(26,.46,6.83,12.41,.20)]:
                additions.append(clone(s,11,idx,x,y,w,h))
            for idx,x in [(18,-1.86),(20,10.21)]:
                additions.append(clone(s,11,idx,x,4.14,4.98,.60))
            anchor=list(s.shapes)[0]._element
            for a in additions:
                a._element.getparent().remove(a._element)
                anchor.addnext(a._element);anchor=a._element
            # Rounded translucent cards replace solid strips on sparse comparison pages.
            if n in {17,18,28,29}:
                # Preserve native card effects and put the editable wording above them.
                for a in list(s.shapes):
                    if a.shape_type == 1 and .43 < a.height/914400 < .48 and a.top/914400 > 1.9:
                        e=clone(s,11,24,a.left/914400,a.top/914400,a.width/914400,a.height/914400)
                        e._element.getparent().remove(e._element);a._element.addprevious(e._element)
                        a._element.getparent().remove(a._element)
        chapter,tabs=next((c,t) for c,t in NAV_GROUPS if any(n in pages for _,pages in t))
        clone(s,3,2,.65,.12,12.10,.01)
        clone(s,3,3,.48,.07,1.85,.08)
        clone(s,3,4,.20,.65,2.10,.08)
        clone(s,3,5,2.38,.23,.18,.37)
        arttext(s,chapter,.45,.23,1.9,.44,25,PP_ALIGN.LEFT)
        for i,(t,pages) in enumerate(tabs):
            x=2.78+i*1.61
            clone(s,3,6,x,.22,1.49,.42)
            active=n in pages
            if active:
                a=shape(s,x+.02,.24,1.45,.38,BLUE,S.ROUNDED_RECTANGLE,None,33000)
                line(s,x+.23,.66,x+1.26,.66,C,1.5)
            nav_label=center(s,t.replace('，','，\n'),x+.03,.23 if '，' in t else .29,1.43,.43 if '，' in t else .29,10 if '，' in t else 15,C if active else WHITE,active)
        for a in s.shapes:
            if a.has_text_frame and a.top/914400 < .8 and '，\n' in a.text:
                for p in a.text_frame.paragraphs:p.space_after=Pt(0);p.line_spacing=1.0
        manifest['slides'][n-1]['navigation']={'chapter':chapter,'tabs':[t for t,_ in tabs],'active':next(t for t,pages in tabs if n in pages)}
    # Restore quiet page numbers without bringing back production footnotes.
    txt(s,f'{n:02}',12.02,7.19,.72,.22,11,PALE,False,PP_ALIGN.RIGHT)

# Normalize all copied IDs and remove template-only metadata before saving.
for s in prs.slides:
    for i,e in enumerate(s._element.xpath('.//p:cNvPr'),1): e.set('id',str(i))
prs.core_properties.title='PIXIU·貔貅：面向麒麟OS Agent的去中心化记忆系统设计与实现'
prs.core_properties.subject='项目报告 · 科技风格试作版'
prs.core_properties.author='PIXIU'
prs.core_properties.last_modified_by='PIXIU'
prs.core_properties.keywords='PIXIU, OS Agent, 持续记忆'
prs.save(OUT/'PIXIU项目报告-科技风试作版.pptx')
manifest['inputs']=[{'path':str(p.relative_to(ROOT)), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(inputs)]
manifest['output_sha256']=hashlib.sha256((OUT/'PIXIU项目报告-科技风试作版.pptx').read_bytes()).hexdigest()
(WORK/'review/abc-trial-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'slides':len(prs.slides),'file':str(OUT/'PIXIU项目报告-科技风试作版.pptx')},ensure_ascii=False))
