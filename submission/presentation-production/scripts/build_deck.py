"""Build a self-contained, editable roadshow deck from verified PIXIU evidence."""
from pathlib import Path
import json, math, hashlib
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE as S, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'submission/presentation-production'
ASSET=ROOT/'docs/delivery/assets/operations/03-current-workflows'
BLUE='1456B8'; INK='172D4D'; MUTED='536B89'; PALE='EAF2FF'; WHITE='FFFFFF'; CYAN='28B4CD'; LINE='C9DAF1'; DARK='102A50'
FONT='Noto Sans CJK SC'
prs=Presentation();prs.slide_width=Inches(13.333333);prs.slide_height=Inches(7.5)
prs.core_properties.title='PIXIU·貔貅：面向麒麟OS Agent的去中心化记忆系统设计与实现'
prs.core_properties.author='PIXIU';prs.core_properties.last_modified_by='PIXIU'
prs.core_properties.subject='竞赛路演项目报告 · 0.1.12'
inputs={Path(__file__).resolve(),WORK/'source/storyboard.md',ROOT/'build/release/scripts/build-presentation.py',ROOT/'build/release/requirements-docs.txt',WORK/'requirements.txt'}; records=[]

def xml(tag,**attrs):
 e=OxmlElement(tag)
 for k,v in attrs.items():e.set(k,str(v))
 return e

def shape(s,kind,x,y,w,h,fill=WHITE,line=LINE,width=1,shadow=False):
 a=s.shapes.add_shape(kind,Inches(x),Inches(y),Inches(w),Inches(h))
 if kind==S.ROUNDED_RECTANGLE:a.adjustments[0]=.1
 if fill:a.fill.solid();a.fill.fore_color.rgb=RGBColor.from_string(fill)
 else:a.fill.background()
 if line:a.line.color.rgb=RGBColor.from_string(line);a.line.width=Pt(width)
 else:a.line.fill.background()
 ef=xml('a:effectLst');a._element.spPr.append(ef)
 if shadow:
  sh=xml('a:outerShdw',blurRad=65000,dist=30000,dir=5400000,algn='ctr',rotWithShape='0');c=xml('a:srgbClr',val='173866');c.append(xml('a:alpha',val=13000));sh.append(c);ef.append(sh)
 return a

def box(s,x,y,w,h,fill=WHITE,line=LINE,shadow=False):return shape(s,S.ROUNDED_RECTANGLE,x,y,w,h,fill,line,shadow=shadow)
def text(s,t,x,y,w,h,size=18,color=INK,bold=False,align=None):
 a=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));tf=a.text_frame;tf.word_wrap=True
 tf.margin_left=tf.margin_right=Inches(.015);tf.margin_top=tf.margin_bottom=0
 for i,tline in enumerate(t.split('\n')):
  p=tf.paragraphs[0] if i==0 else tf.add_paragraph();p.text=tline;p.font.name=FONT;p.font.size=Pt(size);p.font.bold=bold;p.font.color.rgb=RGBColor.from_string(color);p.space_after=Pt(4);p.line_spacing=1.10
  if align is not None:p.alignment=align
  for r in p.runs:
   r._r.get_or_add_rPr().append(xml('a:ea',typeface=FONT))
 return a

def gradient(a,c1,c2):
 sp=a._element.spPr
 for ch in list(sp):
  if ch.tag.split('}')[-1] in ('solidFill','noFill','gradFill'):sp.remove(ch)
 gf=xml('a:gradFill',rotWithShape='1');ls=xml('a:gsLst')
 for pos,col in [(0,c1),(100000,c2)]:
  gs=xml('a:gs',pos=pos);gs.append(xml('a:srgbClr',val=col));ls.append(gs)
 gf.append(ls);gf.append(xml('a:lin',ang=2700000,scaled='1'));sp.append(gf)

def line(s,x1,y1,x2,y2,color=BLUE,width=1.6,arrow=False,dash=False):
 a=s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Inches(x1),Inches(y1),Inches(x2),Inches(y2));a.line.color.rgb=RGBColor.from_string(color);a.line.width=Pt(width);ln=a.line._get_or_add_ln()
 a._element.spPr.append(xml('a:effectLst'))
 if arrow:ln.append(xml('a:tailEnd',type='triangle'))
 if dash:ln.append(xml('a:prstDash',val='dash'))
 return a

def circle(s,x,y,d,fill=PALE,linecol=LINE):return shape(s,S.OVAL,x,y,d,d,fill,linecol)
def pill(s,t,x,y,w,color=BLUE):
 box(s,x,y,w,.34,PALE,None);text(s,t,x+.07,y+.055,w-.14,.25,11,color,True)

def mesh(s,dark=False):
 # Quiet contour field, not a flat empty canvas.
 c='25466F' if dark else 'E1EBF8'
 pts=[(10.25,.2),(11.25,.5),(12.45,.12),(12.85,1.1),(11.6,1.4),(10.9,2.0),(12.7,2.6)]
 for i,j in [(0,1),(1,2),(1,3),(2,3),(3,4),(4,5),(5,6),(4,6),(1,4),(0,5)]:line(s,*pts[i],*pts[j],c,.65)
 for x,y in pts:circle(s,x-.035,y-.035,.07,c,c)
 for i in range(4):
  a=shape(s,S.ARC,9.7+i*.17,3.35+i*.17,3.1,3.1,None,c,.7)
  a.rotation=18+i*8

def base(title,sub,section,note='',dark=False):
 s=prs.slides.add_slide(prs.slide_layouts[6]);bg=shape(s,S.RECTANGLE,0,0,13.33333,7.5,None,None);gradient(bg,DARK if dark else 'FFFFFF','153F75' if dark else 'F1F6FE');mesh(s,dark)
 n=len(prs.slides);text(s,'PIXIU / 貔貅',.52,.28,2,.35,15,'FFFFFF' if dark else BLUE,True)
 text(s,section,8,.3,4.75,.28,11,'A9C7ED' if dark else MUTED,align=PP_ALIGN.RIGHT)
 text(s,title,.62,.91,12.05,.66,29,WHITE if dark else INK,True)
 if sub:text(s,sub,.65,1.66,11.95,.58,16,'C3D8F3' if dark else MUTED)
 line(s,.65,7.02,12.65,7.02,'43658A' if dark else LINE,.7)
 text(s,'PIXIU 0.1.12 · 银河麒麟 V11 · 图示为机制说明，实拍使用公开合成资料',.67,7.16,11.3,.21,9,'A9C7ED' if dark else MUTED)
 text(s,f'{n:02d}',12.05,7.1,.6,.3,13,'A9C7ED' if dark else BLUE,True,PP_ALIGN.RIGHT)
 s.notes_slide.notes_text_frame.text=title+'\n'+note+'\n截图：0.1.12，银河麒麟V11 amd64，2026-09-10。测试场景使用公开合成资料。'
 records.append({'page':n,'title':title,'section':section,'notes':note,'screenshots':[]})
 return s

def takeaway(s,t):
 a=box(s,.65,6.43,12.02,.42,PALE,None);text(s,t,.83,6.50,11.65,.3,14 if len(t)>57 else 15,BLUE,True)

def node(s,title,body,x,y,w=2.5,h=1.3,color=BLUE,number=None):
 box(s,x+.055,y+.055,w,h,'DFEAF9',None);box(s,x,y,w,h,WHITE,LINE,True)
 shape(s,S.RECTANGLE,x+.02,y+.18,.035,h-.36,color,None)
 dx=.2
 if number:
  circle(s,x+.18,y+.16,.4,PALE,None);text(s,str(number),x+.18,y+.225,.4,.25,12,color,True,PP_ALIGN.CENTER);dx=.7
 text(s,title,x+dx,y+(.11 if h<1.2 else .16),w-dx-.15,.42,17 if h<1.2 else 19,color,True)
 text(s,body,x+.2,y+(.53 if h<1.2 else .68),w-.4,max(.32,h-.73),14 if h<1.2 else 16,INK)

def shot(s,name,x,y,w,h,caption=None):
 p=ASSET/name
 if p.read_bytes().startswith(b'version https://git-lfs'):p=WORK/'assets'/name
 if caption:h=min(h,6.0-y)
 inputs.add(p);im=Image.open(p);iw,ih=im.size;scale=min(w/iw,h/ih);dw,dh=iw*scale,ih*scale
 # Picture mat, recessed border, subtle shadow; source image bytes remain untouched.
 box(s,x+(w-dw)/2-.07,y+(h-dh)/2-.07,dw+.14,dh+.14,WHITE,LINE,True)
 s.shapes.add_picture(str(p),Inches(x+(w-dw)/2),Inches(y+(h-dh)/2),Inches(dw),Inches(dh))
 records[-1]['screenshots'].append({'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 if caption:text(s,caption,x,y+h+.09,w,.30,11,MUTED)

def device(s,x,y,label,w=2.4):
 a=box(s,x,y,w,1.35,'F5F9FF',BLUE);box(s,x+.09,y+.09,w-.18,1.06,WHITE,LINE)
 for i in range(3):line(s,x+.27,y+.34+i*.22,x+w-.28,y+.34+i*.22,LINE,2)
 shape(s,S.TRAPEZOID,x-.13,y+1.35,w+.26,.19,PALE,BLUE)
 text(s,label,x-.12,y+1.68,w+.24,.4,17,BLUE,True,PP_ALIGN.CENTER)

def flow(s,items,y=3.4,x=.8,w=2.65,gap=.38,h=1.45):
 for i,(t,b) in enumerate(items):
  xx=x+i*(w+gap);node(s,t,b,xx,y,w,h,number=i+1)
  if i<len(items)-1:line(s,xx+w,y+h/2,xx+w+gap-.06,y+h/2,BLUE,1.8,True)

# 01: a genuine opening cover, not a feature page.
s=base('','', '项目报告 / ROADSHOW',dark=True)
text(s,'让经验跨越\n会话与设备',.72,1.35,7.1,1.8,44,WHITE,True)
text(s,'PIXIU · 貔貅',.77,3.5,6.3,.7,31,WHITE,True)
text(s,'面向麒麟 OS Agent 的去中心化记忆系统\n设计与实现',.8,4.42,6.25,1.05,22,'C7DCF5')
for i,t in enumerate(['持续积累','有据可查','可信协作']):
 box(s,.82+i*1.9,6.05,1.67,.45,'214D82','4978AD');text(s,t,.94+i*1.9,6.14,1.43,.26,14,WHITE,True)
# Abstract distributed memory constellation with layered device screens.
for i,(x,y) in enumerate([(8.1,2.0),(10.25,3.3),(8.15,4.75)]):
 circle(s,x-.13,y-.13,1.57,None,'396597');circle(s,x,y,1.31,'214D82','6BA5DC');text(s,['资料','记忆','任务'][i],x+.1,y+.44,1.1,.38,21,WHITE,True,PP_ALIGN.CENTER)
line(s,9.45,2.8,10.35,3.7,'61B6E1',2,True);line(s,10.4,4.5,9.25,5.1,'61B6E1',2,True);line(s,8.63,4.74,8.63,3.34,'61B6E1',2,True)

# 02: Explicit six-part agenda and slogan endpoint.
s=base('从真实需求出发，解释每一层价值','先理解用户为什么需要记忆，再看功能如何落地，以及价值如何被验证。','目录')
agenda=[('01','场景与需求','资料分散、经验中断、版本失控'),('02','方案与架构','为 OS Agent 提供持续记忆服务'),('03','功能亮点','自动积累、追溯、偏好、跨端'),('04','功能与技术实现','数据、算法、同步、安全与部署'),('05','完整用户案例','活动资料从保存到更正复用'),('06','商业模式探索','从小范围试点验证持续服务价值')]
for i,(n,t,b) in enumerate(agenda):
 x=.78+(i%3)*4.21;y=2.5+(i//3)*1.68;node(s,t,b,x,y,3.85,1.4,number=n)
text(s,'需求缺口',1,6.22,1.6,.35,15,BLUE,True);line(s,2.55,6.4,4.3,6.4,BLUE,1.2,True);text(s,'可用方案',4.45,6.22,1.6,.35,15,BLUE,True);line(s,6.1,6.4,7.8,6.4,BLUE,1.2,True);text(s,'证据与价值',7.95,6.22,2,.35,15,BLUE,True);text(s,'→ 一句话收束',10.4,6.22,2.2,.35,15,MUTED)

# 03
s=base('同一个人，常常要向设备重新解释自己','林先生在书房、客厅与随身设备之间处理家庭账单，却常常需要反复交代已经说过的信息。','01 / 场景与需求', '用户需求来自README典型应用背景与赛题附录A。林先生为场景人物；四月434.50元、更正燃气156到186、遗忘清单是需求叙事，不宣称这整条同一记录已全程实测。当前九月账单实拍另见第10页。')
for i,(t,b,lab) in enumerate([('书房保存账单','收到家庭支出清单\n希望助手记住并供以后核对','资料难以沉淀'),('客厅核对账单','只记得模糊片段\n要翻记录和核算明细','答案难以追溯'),('更正与遗忘','账单有误需要修正\n不再需要时希望停止使用','控制难以贯穿')]):
 x=.85+i*4.18;device(s,x+.58,2.5,t,2.65);text(s,b,x+.1,4.64,3.65,.91,18,INK,align=PP_ALIGN.CENTER);pill(s,lab,x+.65,5.86,2.5)
line(s,3.8,3.18,5.32,3.18,LINE,2,True,True);line(s,8,3.18,9.5,3.18,LINE,2,True,True)
takeaway(s,'用户真正需要的，是不必反复解释、能够核对、能够接着使用的经验。')

# 04
s=base('难点不在保存更多，而在维持可用的记忆','赛题聚焦多源质量、偏好版本、新旧冲突与关联检索；跨设备工作进一步放大这些问题。','01 / 需求缺口','依据：赛题背景、七项功能要求；跨设备是团队扩展创新。')
for i,(t,b) in enumerate([('来源不一致','文档、工具与行为格式不同'),('知识会变化','新旧通知、偏好与事实矛盾'),('使用跨边界','换会话、换设备、换授权范围')]):
 y=2.45+i*1.16;node(s,t,b,.85,y,3.8,.98)
line(s,4.75,2.94,6,3.85,BLUE,1.5,True);line(s,4.75,4.1,6,4.1,BLUE,1.5,True);line(s,4.75,5.26,6,4.35,BLUE,1.5,True)
shape(s,S.HEXAGON,5.85,3.05,2.15,2.05,PALE,BLUE,2);text(s,'记忆质量\n与可控性',6.2,3.56,1.48,.95,22,BLUE,True,PP_ALIGN.CENTER)
for i,(t,b) in enumerate([('可信','保留出处与当前有效版本'),('连续','按任务召回，授权后跨端'),('可控','采集授权、审批、更正与遗忘')]):
 y=2.45+i*1.16;line(s,8,4.05,8.6,y+.49,CYAN,1.3,True);node(s,t,b,8.65,y,3.8,.98)
takeaway(s,'因此，方案必须同时管理内容、来源、版本、使用范围和记忆生命周期。')

# 05
s=base('PIXIU：嵌入桌面智能体的持续记忆服务','让助手在新任务里找回已授权的知识与偏好，并把新的有效经验继续沉淀。','02 / 服务定位','上游会话、规划、工具和审批来自openKylin宿主/Runtime；PIXIU贡献记忆业务与集成。')
shot(s,'shared-workspace.png',.83,2.42,7.0,3.57,'真实界面：会话、记忆、设备与设置集成在同一应用')
for i,(t,b) in enumerate([('面向用户','日常保存资料，后续按需使用'),('面向智能体','按当前问题注入有来源的记忆'),('面向设备','本机可读写，可信副本最终一致')]):node(s,t,b,8.32,2.43+i*1.18,4.12,1.03)
takeaway(s,'记忆留在可信设备；联网模型负责理解与表达，本地检索负责找回依据。')

# 06
s=base('总架构：智能体、记忆引擎与可信设备协同','明确上游基础能力、自有记忆能力和麒麟系统能力，建立可以落地的服务边界。','02 / 总体架构','依据 docs/ARCHITECTURE.md、docs/API.md、ADR-0001及正式目录迁移记录。')
box(s,.8,2.33,11.72,.72,BLUE,BLUE);text(s,'用户桌面  ·  会话 / 记忆 / 设备 / 设置',1,2.5,11.2,.36,22,WHITE,True,PP_ALIGN.CENTER)
node(s,'openKylin 基座','宿主 + Runtime\n会话、规划、工具、审批',.8,3.43,3.22,1.63)
node(s,'PIXIU 原创记忆能力','Provider → 公共 API\n接入 / 偏好 / 知识 / 检索 / 流转',4.37,3.43,4.38,1.63)
node(s,'可信对等设备','各自保存记忆副本\n授权共享 / CRDT / 反熵',9.12,3.43,3.4,1.63)
line(s,2.4,3.05,2.4,3.4,BLUE,1.8,True);line(s,6.5,3.05,6.5,3.4,BLUE,1.8,True);line(s,10.8,3.05,10.8,3.4,BLUE,1.8,True);line(s,4.02,4.22,4.34,4.22,BLUE,1.8,True);line(s,8.75,4.22,9.09,4.22,BLUE,1.8,True)
for i,(t,b) in enumerate([('结构化存储','SQLite · 来源/版本/关系/审计'),('系统双 SDK','Embedding · Vector Engine'),('平台与模型适配','用户服务 · 单包升级 · 模型连接')]):node(s,t,b,.8+i*4.02,5.44,3.68,.91)
# Bottom row is a foundation inventory, not a one-to-one dependency mapping.

# 07
s=base('四项亮点，形成经验复用的持续循环','每一轮使用都连接资料、可信答案、当前版本与下一次任务；积累价值来自可复用的有效内容。','03 / 功能亮点')
for i,(t,b,x,y) in enumerate([('自动积累','授权目录与多源接入',1.0,2.46),('有据可查','回答可回到记忆来源',8.75,2.46),('保持有效','偏好版本与更正审批',8.75,4.76),('可信协作','跨会话、跨设备复用',1.0,4.76)]):node(s,t,b,x,y,3.53,1.22,number=i+1)
circle(s,5.04,2.76,3.2,None,LINE);circle(s,5.31,3.03,2.66,None,BLUE);shape(s,S.HEXAGON,5.64,3.43,2.0,1.78,BLUE,None);text(s,'可持续\n使用的经验',5.88,3.83,1.54,.9,21,WHITE,True,PP_ALIGN.CENTER)
for coords in [(4.55,3.05,8.57,3.05),(10.45,3.73,10.45,4.62),(8.54,5.38,4.65,5.38),(2.75,4.61,2.75,3.81)]:line(s,*coords,CYAN,2.2,True)
takeaway(s,'功能的共同目标：降低反复说明和核对成本，让经验在用户控制下持续可用。')

# 08
s=base('亮点一：照常保存文件，后台接续整理','活动安排或会议资料进入授权目录后，后台读取文档、联系既有知识，并报告处理进度。','03 / 自动积累','0.1.12目录场景：保存1条记忆，新会话查回成功。授权非递归目录；新增和更新等待文件稳定。')
shot(s,'directory-folder.png',.85,2.44,6.25,1.55,'实拍：用户选择要整理的目录；采集需先授权')
for i,(t,b) in enumerate([('保存资料','文件进入目录'),('稳定后读取','分块提取内容'),('形成知识','保留文档出处')]):
 node(s,t,b,.87+i*2.13,4.78,1.92,1.02)
 if i<2:line(s,2.82+i*2.13,5.28,2.98+i*2.13,5.28,CYAN,1.4,True)
for i,(t,b) in enumerate([('先授权','选择目录并保存采集设置'),('再读取','等待文件稳定，按内容块处理'),('后复用','知识与来源进入个人记忆')]):node(s,t,b,7.59,2.45+i*1.19,4.79,1.0,number=i+1)
takeaway(s,'用户维护熟悉的文件，PIXIU 接续知识整理；关闭采集不会自动删除已有记忆。')

# 09
s=base('亮点二：新通知到来，先对照再更正','“记住了”还不够：当活动时间发生变化，用户需要看见修改依据，掌握最终保存决定。','03 / 更新可控')
shot(s,'dreaming-review.png',.85,2.35,7.35,3.92,'真实审批窗口：原内容、整理后内容与“批准更正”')
node(s,'提出方案','新资料触发 Dreaming\n冻结待更正的目标版本',8.68,2.48,3.7,1.48)
node(s,'用户核对','批准后保存；版本变化\n则重新读取，避免误覆盖',8.68,4.27,3.7,1.48)
line(s,10.52,3.98,10.52,4.23,BLUE,1.6,True)
takeaway(s,'自动化负责提出更正，用户负责确认实质变化。')

# 10
s=base('亮点三：得到答案，也能找到依据','模糊记忆常常只剩“水电燃气花了多少”；需要定位正确月份、明细与可核对的来源。','03 / 追溯检索','当前实拍为2026年9月公开合成账单；与赛题附录4月样例不是同一笔真实家庭消费。')
shot(s,'bill-recall.png',.85,2.4,7.5,3.88,'实拍：新会话找回九月账单，回答附来源入口')
text(s,'434.50',8.9,2.65,3.3,.86,43,BLUE,True);text(s,'元 · 本例水电燃气合计',8.9,3.52,3.4,.4,16,MUTED)
for i,(t,v) in enumerate([('电费','210.00'),('水费','68.50'),('燃气费','156.00')]):
 line(s,8.87,4.17+i*.54,12.38,4.17+i*.54,LINE,.8);text(s,t,8.93,4.3+i*.54,1.5,.35,18,INK);text(s,v,10.58,4.3+i*.54,1.7,.35,18,BLUE,True,PP_ALIGN.RIGHT)
takeaway(s,'检索找到相关知识，结构化数据支持核算；来源帮助用户判断答案是否可用。')

# 11
s=base('亮点四：理解现在的偏好，保留变化的来路','从“请简洁回答”到“这次需要详细步骤”，偏好应能更新，并在后续会话按范围使用。','03 / 个性化')
shot(s,'preference-history.png',.85,2.42,7.1,3.8,'实拍：当前输出风格与三次版本历史')
for i,(t,b) in enumerate([('捕捉','从用户原话提取偏好'),('版本化','稳定标识、当前值与历史快照'),('适配','注入当前有效偏好和授权范围')]):node(s,t,b,8.5,2.44+i*1.21,3.88,1.03,number=i+1)
takeaway(s,'偏好需要可追溯的更新规则；安全设置由明确授权管理，不能由模型随意放宽。')

# 12
s=base('可信设备，接着使用同一份经验','书房记下整理书籍的约定，客厅的新会话查回时间、步骤与来源。','03 / 跨端协作','0.1.12实拍：同宿主独立V11虚拟机；两端公共API核对知识ID、正文、版本与证据ID一致。')
shot(s,'shared-workspace.png',.85,2.38,7.66,3.81,'接收端实拍：每周六 9:00，按主题分类并更新借阅登记')
device(s,9.24,2.55,'发送端 → 接收端',2.5)
text(s,'配对建立信任\n选择共享空间\n新会话继续使用',9.23,4.74,3.07,1.37,19,INK)
takeaway(s,'共享的是授权记忆与来源；各设备独立保存副本，连接恢复后补齐差异。')

# 13
s=base('多源接入：把杂乱输入变成带出处的知识','内容先经过授权、格式与质量处理，再进入统一证据模型；写入与后续检索共用范围和版本信息。','04 / 接入实现','据公共API与现有接入服务。图片知识为当前多模态模型理解和用户确认；不宣称自动截图/剪贴板已实现。')
for i,(t,b) in enumerate([('对话与工具','原话 / 执行结果'),('文档与图片','附件 / 授权目录'),('行为与配置','授权统计 / 手动记录')]):node(s,t,b,.82,2.45+i*1.12,3.1,.95)
for yy in [2.9,4.02,5.14]:line(s,3.96,yy,4.57,4.06,BLUE,1.25,True)
node(s,'统一接入门','格式清洗与标准化\n质量校验 / 敏感识别\n来源、幂等键和范围',4.65,3.02,3.48,2.2)
line(s,8.17,4.08,8.5,4.08,BLUE,1.5)
line(s,8.5,2.925,8.5,5.165,BLUE,1.5)
for yy in [2.925,4.045,5.165]:line(s,8.5,yy,8.83,yy,BLUE,1.5,True)
for i,(t,b) in enumerate([('Evidence','内容、原始依据、发生位置'),('Knowledge','结构化正文、状态、版本'),('Preference','类别、当前值、历史快照')]):node(s,t,b,8.9,2.45+i*1.12,3.62,.95)
takeaway(s,'同一套数据约束贯穿接入、检索、更新与同步，避免“不同入口、不同规则”。')

# 14
s=base('混合检索：语义找到，结构算清，来源可追','把关键词、向量相似与实体关系组合起来，再按范围和时间过滤、融合排序。','04 / 检索实现','当前实现为FTS5、VectorStore和Graph并行；RRF融合、词法/年月重排，未加载神经网络reranker。')
node(s,'用户问题','“九月水电燃气花了多少？”',.85,2.39,4.1,1.0)
node(s,'上下文边界','授权范围 / 时间 / 当前有效状态',7.38,2.39,5.03,1.0)
for i,(t,b) in enumerate([('关键词 · FTS5','精确标题与词面匹配'),('向量 · 系统 SDK','找回语义相近的记忆'),('实体关系 · Graph','沿类目关联商户与事实')]):
 x=.85+i*4.2;node(s,t,b,x,3.94,3.63,1.0);line(s,x+1.81,3.64,x+1.81,3.9,BLUE,1.3,True)
line(s,2.9,3.4,2.9,3.64,BLUE,1.3);line(s,9.81,3.4,9.81,3.64,BLUE,1.3);line(s,2.66,3.64,11.06,3.64,BLUE,1.3)
for x in [2.68,6.88,11.08]:line(s,x,4.96,x,5.3,BLUE,1.3,True)
box(s,.84,5.34,11.72,.83,BLUE,None);text(s,'RRF 融合 → 词法与年月重排 → 明细过滤 / 聚合 → 附知识与证据引用',1.04,5.59,11.3,.37,20,WHITE,True,PP_ALIGN.CENTER)
takeaway(s,'检索子路径不额外调用生成式 LLM；完整助手的规划与回答生成仍可使用模型。')

# 15
s=base('知识组织：一条事实，连着来源与可复用经验','区分知识的用途与证据的出处，让查询结果能够解释，也能在未来任务中复用。','04 / 知识结构')
for i,(t,b) in enumerate([('事实 FACT','时间、地点、金额'),('流程 WORKFLOW','先做什么、后做什么'),('案例 CASE','问题、处理与结果'),('模板 TEMPLATE','反复使用的结构')]):node(s,t,b,.84+i*3.14,2.39,2.86,1.05)
shape(s,S.CAN,.92,4.3,2.85,1.55,PALE,BLUE);text(s,'Evidence\n原文 / 原图 / 文档块',1.14,4.78,2.4,.86,17,BLUE,True,PP_ALIGN.CENTER)
shape(s,S.HEXAGON,5.02,3.85,3.28,2.12,BLUE,BLUE);text(s,'Knowledge\n状态 · 范围 · 版本',5.5,4.48,2.33,.85,17,WHITE,True,PP_ALIGN.CENTER)
line(s,3.8,5.03,5.0,5.03,BLUE,1.8,True);text(s,'依据',4.04,4.57,.84,.3,13,MUTED)
for i,(t,x,y) in enumerate([('实体',9.1,4.04),('关系',10.9,4.6),('检索索引',9.2,5.28)]):
 circle(s,x,y,1.05,PALE,BLUE);text(s,t,x+.04,y+.38,.98,.35,14,BLUE,True,PP_ALIGN.CENTER);line(s,8.28,4.9,x,y+.5,CYAN,1.1,True)
takeaway(s,'来源与知识分离保存，通过关联保持追溯；更新知识时同步维护索引。')

# 16
s=base('偏好版本：把“现在怎么做”与历史分开','偏好从用户表达中提取，稳定标识记录同一偏好的变化；当前值用于适配，旧值用于回溯。','04 / 偏好实现')
for i,(t,b) in enumerate([('操作习惯','常用工具与处理方式'),('输出风格','简洁程度、表达形式'),('安全策略','用户明确配置的边界')]):pill(s,t+' / '+b,.83+i*4.22,2.36,3.91)
line(s,1.37,4.06,11.85,4.06,BLUE,2.7,True)
for i,(v,t,b) in enumerate([('v1','简洁回答','初始表达被提取'),('v2','仍然简洁','保留更新历史'),('v3','详细说明','当前值用于后续会话')]):
 x=1.1+i*4.08;circle(s,x,3.7,.74,BLUE,None);text(s,v,x+.08,3.9,.59,.34,19,WHITE,True,PP_ALIGN.CENTER);node(s,t,b,x-.25,4.72,3.24,1.13);line(s,x+.36,4.45,x+.36,4.7,BLUE,1.2)
text(s,'从用户原话提取，避免用助手自身的回答反向猜测用户偏好',1,3.05,11.3,.43,20,INK,True,PP_ALIGN.CENTER)
takeaway(s,'按作用域读取偏好；记忆读取设置与共享写入设置分别保存，不自动迁移旧数据。')

# 17
s=base('短、中、长期记忆，接住不同时间尺度的任务','本轮上下文服务当下，阶段状态接续项目，有价值的内容通过明确晋升进入长期知识。','04 / 记忆流转','生命周期API：TURN事件短期；压缩/切换/结束/委派事件中期。桌面可选长期保留；TTL清理；并非全部会话永久化。')
for i,(t,b) in enumerate([('短期 · 当前任务','轮次开始 / 结束\n保留当前任务上下文'),('中期 · 阶段状态','压缩前 / 切换 / 结束\n保存阶段内容与到期时间'),('长期 · 持久知识','选择长期保留\n复用统一接入与知识管线')]):node(s,t,b,.87+i*4.18,2.82,3.58,1.8,number=i+1)
line(s,4.48,3.71,5.01,3.71,BLUE,2,True);line(s,8.66,3.71,9.19,3.71,BLUE,2,True)
line(s,11.03,4.66,11.03,5.57,CYAN,1.8);line(s,11.03,5.57,2.63,5.57,CYAN,1.8);line(s,2.63,5.57,2.63,4.67,CYAN,1.8,True)
text(s,'长期记忆按新问题召回，再注入当前会话',3.53,5.14,6.5,.39,20,BLUE,True,PP_ALIGN.CENTER)
takeaway(s,'阶段记忆有到期与清理规则；长期知识仍受当前授权、状态及遗忘控制。')

# 18
s=base('两类冲突，两层处理，避免把“收敛”当成“正确”','同一条记忆的并发副本需要确定性合并；不同记录的业务矛盾需要语义规则与人工核对。','04 / 更正与冲突')
node(s,'副本层：同一知识 ID','版本向量判断因果\nLWW 提供确定性的并发胜者',.86,2.45,5.53,1.59)
node(s,'业务层：不同记录相互矛盾','实体 / 字段比较\nNEW_WINS · MERGE · MANUAL',6.94,2.45,5.53,1.59)
for x in [3.61,9.69]:line(s,x,4.08,x,4.52,BLUE,1.7,True)
node(s,'物化业务状态','把胜出正文、版本和来源落库\n重建图与向量索引',.86,4.58,5.53,1.45)
node(s,'保留审计与审批','更正方案先冻结目标版本\n用户批准后再写入',6.94,4.58,5.53,1.45)
takeaway(s,'确定性协议解决副本一致；业务规则和审批帮助判断内容应如何变化。')

# 19
s=base('对等同步：在线扩散，离线累积，重连对账','每个可信节点独立工作；操作日志、签名传输和反熵共同推进最终一致。','04 / 同步时序','三设备现有实测为同一宿主上的独立V11虚拟机。30.5秒来自一次0.1.12断连并发恢复。')
xs=[1.47,5.36,9.58]
for x,t in zip(xs,['设备 A · 本地写入','设备 B · 在线','设备 C · 暂时离线']):
 pill(s,t,x-.48,2.37,3.2);line(s,x+.97,2.87,x+.97,6.1,LINE,1.3,False,True)
for y,x1,x2,t in [(3.16,2.44,6.33,'追加签名操作 → Gossip 推送'),(3.85,6.33,2.44,'确认收到 / 本地物化'),(4.62,2.44,10.55,'C 重连：交换摘要，发现缺失'),(5.42,6.33,10.55,'补齐操作 → CRDT 合并 → 重建索引')]:
 line(s,x1,y,x2,y,BLUE,1.8,True);text(s,t,min(x1,x2)+.1,y-.44,abs(x2-x1)-.15,.34,15,BLUE,True,PP_ALIGN.CENTER)
text(s,'私人范围不入同步队列；仅授权 shared 范围传播',.99,6.15,11.4,.29,14,MUTED,align=PP_ALIGN.CENTER)
takeaway(s,'配对身份 + TLS 1.3 双向认证 + 操作签名；设备断连期间不承诺即时一致。')

# 20
s=base('安全边界贯穿采集、使用、共享与遗忘','资料能否进入、被谁使用、如何退出，需要分别受控，而不是用一个总开关代替。','04 / 隐私与遗忘')
for i,(t,b) in enumerate([('采集授权','未授权不采集\n只读已选目录与来源'),('敏感过滤','规则识别与敏感标记\n敏感共享写入拒绝'),('范围控制','个人 / 共享分别管理\n召回再次检查范围'),('精准遗忘','目标与范围预览\n确认后失效并删除向量')]):node(s,t,b,.84+i*3.14,2.55,2.86,1.8,number=i+1)
for i in range(3):line(s,3.72+i*3.14,3.48,3.91+i*3.14,3.48,BLUE,1.5,True)
box(s,.85,4.88,11.7,1.14,PALE,LINE);text(s,'共享遗忘 → 传播墓碑 → 远端隐藏并删除向量',1.12,5.04,11.13,.42,22,BLUE,True,PP_ALIGN.CENTER)
text(s,'当前保留部分证据、关系及全文载荷；不等同于对所有介质进行物理擦除。',1.15,5.63,11.05,.3,14,MUTED,align=PP_ALIGN.CENTER)
takeaway(s,'本地记忆存储与检索可离线；选择云模型理解内容时，推理链路仍涉及外部模型服务。')

# 21
s=base('Agent 生命周期：让记忆真正进入任务执行','Provider 连接上游运行时与公共 API，把召回、工具结果和阶段状态接到同一个任务循环。','04 / Agent 接入','不能把检索API当作聊天API；上游负责通用规划和工具循环。Module E通过公共HTTP契约访问PIXIU。')
for i,(t,b) in enumerate([('任务开始','按问题召回有效记忆'),('上下文注入','范围 / 来源 / 字符预算'),('规划与工具','执行工具与审批'),('结果沉淀','对话、工具与阶段内容')]):node(s,t,b,.85+i*3.14,2.62,2.86,1.26,number=i+1)
for i in range(3):line(s,3.74+i*3.14,3.26,3.94+i*3.14,3.26,BLUE,1.5,True)
shot(s,'agent-tools-completed.png',.91,4.37,5.4,1.5,'实拍：同一助手中可观察工具执行过程')
node(s,'记忆是带边界的外部内容','保留来源与消费记录；按预算注入\n记忆文本不升级为系统指令',6.87,4.32,5.48,1.47)
takeaway(s,'PIXIU 创新集中在持续记忆与对等协作；通用会话、规划和工具能力复用上游。')

# 22
s=base('端侧部署：麒麟原生优先，兼容路径清晰','桌面、记忆服务、Provider 和运行时随单一安装包部署；系统专有能力通过适配层接入。','04 / 平台与维护','0.1.12正式包为amd64；不能声称ARM已完成相同验收。部署实测见TEST_REPORT。')
shot(s,'sdk-version.png',.85,2.4,7.3,1.59,'实拍：0.1.12 与系统 Embedding / Vector Engine 能力')
node(s,'银河麒麟 V11 · 原生路径','实际调用系统双 SDK\n严格画像缺失能力即失败',8.62,2.42,3.82,1.49)
node(s,'Debian · 兼容路径','软件适配保证基本读写检索\n质量、时延结果独立报告',8.62,4.2,3.82,1.49)
flow(s,[('安装','用户服务与依赖'),('升级','签名与版本校验'),('恢复','健康失败时恢复')],y=4.65,x=.88,w=2.12,gap=.37,h=1.32)
takeaway(s,'0.1.12 升级与故障恢复实测：47 条记忆摘要保持一致；常驻资源仍需专项测量。')

# 23
s=base('四项量化结果：说明样本，也说明适用环境','历史开发评测：Debian portable · pixiu-family-expense-v1 · 团队合成资料。','04 / 量化评测','数值来源 docs/acceptance/acceptance-baseline-2026-08-24.json；日期2026-08-24。50组检索、15组偏好、25组冲突、1000次检索。不是0.1.12最终V11双SDK性能报告。')
metrics=[('偏好准确率','100%','15 / 15','目标 ≥85%',1,.85),('知识召回率','100%','50组检索均值','目标 ≥85%',1,.85),('冲突正确率','96%','24 / 25','目标 ≥88%',.96,.88)]
for i,(t,v,b,g,val,target) in enumerate(metrics):
 x=.85+i*3.16;node(s,t,'',x,2.47,2.88,2.86);text(s,v,x+.18,3.18,2.5,.7,37,BLUE,True);text(s,b,x+.19,4.07,2.5,.33,16,MUTED);box(s,x+.2,4.68,2.43,.13,'D6E4F7',None);box(s,x+.2,4.68,2.43*val,.13,BLUE,None);line(s,x+.2+2.43*target,4.59,x+.2+2.43*target,4.9,CYAN,2);text(s,g,x+.19,5.05,2.5,.31,15,BLUE,True)
x=10.33;node(s,'检索 P95','',x,2.47,2.17,2.86);text(s,'115',x+.17,3.18,1.8,.7,37,BLUE,True);text(s,'ms / 1000次',x+.17,4.07,1.8,.34,16,MUTED);text(s,'目标 ≤500ms',x+.17,5.05,1.8,.31,14,BLUE,True)
text(s,'统计口径：偏好与冲突按预期结果核对；召回按每例指定 top-k；P95 为第950个排序耗时。',.91,5.72,11.57,.4,14,MUTED)
takeaway(s,'上述结果证明该合成集上的开发基线；最终 V11 双 SDK 质量、时延及泛化能力仍需同版验证。')

# 24
s=base('原生实测与未覆盖项，分别呈现','功能真实性由安装版、真实模型操作和记录核对支撑；局部测试通过不能推出全部赛题验收通过。','04 / 证据边界')
for i,t in enumerate(['双 SDK 增删查','目录与审批','安装与签名升级','47条恢复一致']):pill(s,t,.88+i*3.15,2.37,2.89)
text(s,'三端断连并发实测 · 云杉资料移交',.9,2.98,8.0,.4,21,BLUE,True)
for i,(t,b) in enumerate([('设备 A · v2','11/9 10:00\n二楼档案室'),('设备 B · v2','11/10 15:00\n三楼档案室'),('设备 C · v1','11/8 09:00\n一楼档案室')]):
 x=.9+i*2.63;node(s,t,b,x,3.58,2.35,1.46)
 line(s,x+1.17,5.09,x+1.17,5.45,CYAN,1.4,True)
box(s,.9,5.49,7.61,.62,BLUE,None);text(s,'重连后均为 v2 · 11/10 15:00 · 三楼档案室',1.08,5.65,7.23,.34,19,WHITE,True)
node(s,'仍需专项验证','同版四项量化指标\n更多真实业务数据\n常驻资源与索引增长\n物理设备与复杂网络',9.0,3.0,3.42,2.95)
text(s,'同宿主独立V11虚拟机；约30.5秒为本次恢复观测值。',.96,6.18,11.6,.23,12,MUTED)
takeaway(s,'证据来源：0.1.12 测试报告、真实操作截图和三端检查点；不同版本记录不合并冒充同版结果。')

# 25
s=base('完整案例：社区活动资料，怎样变成可靠行动依据','一位活动组织者需要安排集合、器材与预算。资料会更新，沟通跨会话，旧通知容易被继续使用。','05 / 完整用户案例','人物为场景化叙事；活动资料是公开合成演示数据。后续三页使用同一0.1.12 V11真实录制链路，不宣称真实客户试点。')
shot(s,'directory-source.png',.9,2.43,5.05,3.62,'实拍原文：星河观测活动安排与器材流程')
node(s,'初始任务','11月8日 19:00 / 社区天文台三层\n器材预算 2680元\n领手册、检查支架、分组、归还器材',6.54,2.45,5.85,1.95)
node(s,'用户真正担心的事','换会话还能查到吗？\n通知更新后，会不会仍然照旧执行？',6.54,4.64,5.85,1.4)
takeaway(s,'案例目标：把“散落的活动通知”转为“有来源、可更正、后续可用的行动依据”。')

# 26
s=base('第一段：保存资料 → 自动整理 → 新会话找回','组织者授权目录并放入活动文档；后台保存知识，下一次直接询问集合时间、地点和预算。','05 / 案例 · 积累与复用')
shot(s,'directory-recall.png',.86,2.4,7.4,3.81,'真实新会话：11月8日 19:00、社区天文台三层、2680元')
for i,(t,b) in enumerate([('保存','文件进入已授权的目录'),('沉淀','整理完成，保存1条记忆'),('核对','从回答来源打开对应原文')]):node(s,t,b,8.77,2.43+i*1.2,3.61,1.03,number=i+1)
takeaway(s,'直接价值：不必重新粘贴整份通知，仍能查回安排并核对依据。')

# 27
s=base('第二段：通知更正 → 用户审批 → 新答案生效','活动改到11月15日19:30、社区天文台二层。Dreaming 提出对照方案，批准后新会话使用更新结果。','05 / 案例 · 更新闭环')
shot(s,'dreaming-review.png',.85,2.43,5.65,3.35,'① 对照原安排与更正内容，点击“批准更正”')
shot(s,'updated-recall.png',7.02,2.43,5.44,3.35,'② 新会话返回新时间、新地点和原有预算')
line(s,6.53,4.01,6.92,4.01,CYAN,2,True)
text(s,'日期与地点变化',1.06,6.13,4.74,.29,16,BLUE,True,PP_ALIGN.CENTER);text(s,'预算 2680元保持，回答附更新依据',7.09,6.13,5.31,.29,16,BLUE,True,PP_ALIGN.CENTER)
takeaway(s,'直接价值：让更新到达实际回答，同时保留人工核对环节，降低继续使用旧安排的风险。')

# 28
s=base('从一份通知，看到可重复使用的服务价值','同一案例覆盖积累、召回、来源、更正、审批与跨会话复用；价值来自行动依据的连续维护。','05 / 价值分析','下面为基于已展示功能的定性价值分析，未测量节省时间比例、用户留存或实际活动差错率。')
rows=[('保存资料','需要再次说明文档背景','目录资料进入记忆，后续按需提问'),('核对安排','在多个文件和对话间查找','回答与来源相连，能核对原文'),('接收变更','新旧通知混用，内容容易遗漏','先对照审批，再在新会话使用'),('延续经验','任务完成后，流程继续散落','知识与阶段保留支持后续复用')]
for i,(t,b,c) in enumerate(rows):
 y=2.48+i*.86;circle(s,.9,y,.48,BLUE,None);text(s,str(i+1),.97,y+.105,.34,.28,15,WHITE,True,PP_ALIGN.CENTER);text(s,t,1.64,y+.055,1.69,.34,18,BLUE,True);text(s,b,3.57,y+.055,3.93,.42,17,MUTED);line(s,7.55,y+.24,8.03,y+.24,CYAN,1.6,True);text(s,c,8.23,y+.055,4.1,.55,17,INK)
text(s,'改善方向：少重复说明 · 更便于核对 · 更正更有序 · 经验可接续',1.01,6.06,11.45,.35,19,BLUE,True,PP_ALIGN.CENTER)
takeaway(s,'以上是功能支持的定性价值；尚未用真实用户对照实验量化节省时间或错误减少比例。')

# 29
s=base('商业探索：围绕部署与持续服务验证付费价值','商业模式为待验证设想。优先面向已有麒麟桌面环境、存在重复资料整理与协作需求的小型组织。','06 / 商业模式探索','不是既有客户、订单或营收。生态渠道事实来自麒麟软件伙伴指南和适配申请页面，2026-09-14访问；不代表PIXIU已获认证或已成为伙伴。')
for i,(t,b,c) in enumerate([('组织部署服务','需求访谈 / 环境适配\n资料范围与使用培训','按项目实施工作量讨论服务费'),('持续维护服务','兼容更新 / 故障处理\n资料流程与使用支持','按约定支持范围讨论年度服务'),('生态集成服务','与应用或解决方案方\n共同适配真实业务流程','按集成与维护范围评估报价')]):
 x=.86+i*4.19;node(s,t,b,x,2.55,3.65,2.2,number=i+1);text(s,c,x+.16,5.15,3.33,.82,17,BLUE,True)
takeaway(s,'收费假设围绕交付和维护；尚无付费客户、定价或盈利数据，不推算市场份额与营收。')

# 30
s=base('先验证客户价值，再讨论规模化运营','用小范围试点检验是否值得持续采购，同时记录真实成本与使用结果。','06 / 运营验证','外部依据仅证明麒麟生态存在适配与伙伴申请渠道；试点流程和商业判断为团队推演。https://www.kylinos.cn/eco/vipPartner/partnerGuide/index.html ; https://www.kylinos.cn/eco/ecoPartner/partnerApply/')
flow(s,[('需求确认','访谈角色与高频任务'),('有限试点','约定资料与支持范围'),('效果复核','成功率 / 耗时 / 差错'),('续用判断','成本 / 使用意愿 / 续费')],y=2.56,x=.87,w=2.66,gap=.39,h=1.58)
node(s,'必须记录的成本','部署与培训人时、兼容维护、问题支持\n模型推理费用与承担方单独说明',.87,4.65,5.55,1.35)
node(s,'可考虑的合作入口','麒麟公开提供适配与伙伴申请渠道\nPIXIU 尚未据此取得认证或合作',6.92,4.65,5.54,1.35)
text(s,'来源：麒麟软件《伙伴指南》《适配申请》公开页面；完整链接见本页备注。',.98,6.33,11.7,.31,12,MUTED)

# 31
s=base('','','07 / SLOGAN',dark=True)
text(s,'让每一台设备的记忆，\n彼此相通。',1.12,2.55,11.08,1.93,43,WHITE,True,PP_ALIGN.CENTER)
text(s,'PIXIU · 貔貅',4.8,5.35,3.7,.58,25,'BED8F7',True,PP_ALIGN.CENTER)
for x,y in [(1.5,1.87),(10.95,1.97),(2.85,5.6),(10.72,5.78)]:circle(s,x,y,.17,'69B6DE',None)
line(s,1.65,1.94,10.93,2.04,'38628E',1);line(s,3.04,5.69,10.69,5.87,'38628E',1)

# Manifest includes every external input; generation does not write delivery artifacts.
for p in [ROOT/'README.md',ROOT/'docs/delivery/TEST_REPORT.md',ROOT/'docs/delivery/APPLICATION_CASES.md',ROOT/'docs/API.md',ROOT/'docs/ARCHITECTURE.md',ROOT/'docs/DELIVERY_PLAN.md',ROOT/'docs/acceptance/acceptance-baseline-2026-08-24.json',ROOT/'submission/video-production/src/sync-trace.json']:
 inputs.add(p)
output=WORK/'render/项目报告.pptx';output.parent.mkdir(parents=True,exist_ok=True);prs.save(output)
manifest={'schema':2,'version':'0.1.12','slides':records,'inputs':[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(inputs)],'output':{'path':output.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}}
(WORK/'review/build-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(f'Built {len(prs.slides)} editable slides: {output.relative_to(ROOT)}')
