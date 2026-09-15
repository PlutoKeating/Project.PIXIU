"""Place authentic UI pixels with native PowerPoint crops and editable explanations.

Never redraw UI or upsample source files. Each image placement records its source,
SHA-256, crop rectangle and displayed scale for review at slide size.
"""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import hashlib
import zipfile
from lxml import etree as ET
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'submission/presentation-production'
VIDEO=ROOT/'submission/video-production/public/current'
CAP=WORK/'source/product-captures'
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
REL='http://schemas.openxmlformats.org/package/2006/relationships'
EMU=914400
PAGES={7,10,11,12,13,15,16,17,18,19,20,21,23,24,25,26,27,28,30}
C='57F1FF'; GOLD='FFDCAB'

class Canvas:
    def __init__(self):
        self.prs=Presentation();self.prs.slide_width=Inches(13.333333);self.prs.slide_height=Inches(7.5)
        self.slide=self.prs.slides.add_slide(self.prs.slide_layouts[6]);self.images=[]
    def text(self,value,x,y,w,h,size=19,color='FFFFFF',bold=False,center=False):
        shape=self.slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));tf=shape.text_frame
        tf.word_wrap=True;tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0
        for i,line in enumerate(value.split('\n')):
            p=tf.paragraphs[0] if i==0 else tf.add_paragraph();p.text=line
            p.font.name='Microsoft YaHei';p.font.size=Pt(size);p.font.bold=bold;p.font.color.rgb=RGBColor.from_string(color)
            p.line_spacing=1.13;p.space_after=Pt(0)
            if center:p.alignment=PP_ALIGN.CENTER
        return shape
    def box(self,x,y,w,h):
        s=self.slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(x),Inches(y),Inches(w),Inches(h))
        s.adjustments[0]=.06;s.fill.solid();s.fill.fore_color.rgb=RGBColor.from_string('075079');s.line.color.rgb=RGBColor.from_string('278BA9');s.line.width=Pt(.7)
        solid=s._element.find('p:spPr/a:solidFill/a:srgbClr',NS);ET.SubElement(solid,'{'+NS['a']+'}alpha',val='47000')
        return s
    def line(self,x,y,x2,y2):
        s=self.slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Inches(x),Inches(y),Inches(x2),Inches(y2));s.line.color.rgb=RGBColor.from_string(C);s.line.width=Pt(1.6)
    def pic(self,name,x,y,w,h,crop=None,role='primary'):
        path=CAP/name if name.startswith('device-') else VIDEO/name
        iw,ih=Image.open(path).size
        l,t,cw,ch=crop or (0,0,iw,ih)
        assert l>=0 and t>=0 and l+cw<=iw and t+ch<=ih,(name,crop,(iw,ih))
        scale=min(w/cw,h/ch);dw,dh=cw*scale,ch*scale
        px,py=x+(w-dw)/2,y+(h-dh)/2
        s=self.slide.shapes.add_picture(str(path),Inches(px),Inches(py),Inches(dw),Inches(dh))
        s.crop_left=l/iw;s.crop_top=t/ih;s.crop_right=(iw-l-cw)/iw;s.crop_bottom=(ih-t-ch)/ih
        s.line.color.rgb=RGBColor.from_string(C);s.line.width=Pt(.65)
        self.images.append({'shape_id':s.shape_id,'source':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'native_size':[iw,ih],'crop_pixels':[l,t,cw,ch],'box_inches':[px,py,dw,dh],'role':role,'pixel_scale_at_1600':round(dw*120/cw,3)})
    def notes(self,items,x=8.55,y=2.9,w=3.95,gap=1.16):
        gap=max(gap,1.22) if len(items)==3 and gap>1 else gap
        for i,(title,body) in enumerate(items):
            self.text(title,x,y+i*gap,w,.35,20,GOLD,True)
            self.text(body,x,y+i*gap+.45,w,.77,16)

def compose(page):
    c=Canvas()
    # Body canvas follows the accepted blue, translucent panel language.
    if page!=24:c.box(.65,1.98,12.03,4.92)
    if page==7:
        c.pic('bill-recall.png',.9,2.3,7.65,4.2,(55,90,800,430))
        c.notes([('自动记忆，持续整合','理解授权资料，关联既有记忆，\n形成新建、更正与合并方案。'),('记忆共享，分布互连','可信设备按范围共享记忆，\n新会话可继续查询与核对。'),('结果可以核对','回答列出明细与合计，\n点击来源回到原始依据。')],x=8.82,y=2.55,w=3.5,gap=1.25)
    elif page==10:
        for x,title,sub in [(.9,'记忆共享，分布互连','三台设备，读取同一条共享记忆'),(6.9,'自动记忆，持续整合','资料变化，先核对再更新记忆')]:
            c.text(title,x,2.24,5.45,.45,24,C,True);c.text(sub,x,2.83,5.45,.4,17)
        c.pic('device-b-memory.png',.9,3.44,5.45,1.92,(1734,596,1324,634))
        c.pic('dreaming-review.png',6.9,3.44,5.45,1.92,(0,220,880,190))
        c.text('授权共享 · 本地副本 · 重连补齐',.9,5.68,5.45,.45,19,GOLD,True)
        c.text('后台理解 · 关联记忆 · 更正审批',6.9,5.68,5.45,.45,19,GOLD,True)
        c.text('一次交付资料，持续使用；跨设备接续任务，减少重复交代。',.9,6.28,11.5,.3,17,center=True)
    elif page==11:
        c.text('配对可信设备并选择共享范围后，已保存的内容与来源可在其他设备继续使用。\n各端保留本地副本；断连期间独立使用，重连后补齐差异。',.88,2.17,11.7,.8,18)
        # Native source excerpts remain legible inside the three-device mesh.
        for x,y,x2,y2 in [(6.66,3.7,3.60,5.35),(6.66,3.7,9.73,5.35),(3.60,5.35,9.73,5.35)]:c.line(x,y,x2,y2)
        for key,x,y in [('a',3.94,3.08),('b',.86,4.82),('c',7.00,4.82)]:
            c.box(x-.04,y-.04,5.5,1.30);c.text('设备 '+key.upper()+' · 记忆来源',x,y,5.42,.28,16,C,True,True)
            header=(1479,438,900,90) if key=='c' else (1734,596,900,90)
            detail=(1530,895,1010,44) if key=='c' else (1785,1052,1010,44)
            c.pic('device-'+key+'-memory.png',x+.08,y+.38,5.26,.42,header,'detail')
            c.pic('device-'+key+'-memory.png',x+.08,y+.88,5.26,.28,detail,'detail')
        c.text('三端使用同一条共享记录，并保留可核对的来源',.9,6.48,11.5,.35,20,GOLD,True,True)
    elif page==12:
        c.text('授权资料变化后，后台理解内容并关联旧记忆；更正与合并交由用户审批。',.9,2.17,11.6,.5,18)
        c.pic('dreaming-review.png',.9,3.00,7.8,1.76,(0,220,880,190))
        c.pic('dreaming-review.png',.9,5.06,7.8,.75,(0,540,880,80),'detail')
        c.notes([('01  理解资料','逐块读取已授权资料，\n保留原始内容与来源。'),('02  关联记忆','对照原记录，形成新建、\n更正或合并方案。'),('03  整合更新','新建按授权保存；\n更正与合并经批准生效。')],x=9.0,y=2.96,w=3.25,gap=1.16)
        c.text('本例：活动时间、地点更正；预算与准备流程保留',.9,6.28,11.6,.35,18,C,True)
    elif page==13:
        c.text('家庭开销核对：清单已交给助手，换个会话询问明细、合计与来源。',.9,2.17,11.6,.4,18)
        c.pic('bill-recall.png',.9,2.88,7.8,3.67,(55,95,800,415))
        c.notes([('用户做什么','保存清单后，在新会话提问。'),('系统完成什么','召回明细、核算合计，\n并提供可点击的来源。'),('得到什么价值','无需重新翻文件与逐项抄录，\n答案与原始记录可以核对。')],x=9.0,y=2.92,w=3.22,gap=1.15)
    elif page==15:
        c.text('用户通过会话、附件或授权目录交付资料；工具结果与授权记录进入统一记忆管线。',.9,2.17,11.5,.55,18)
        c.pic('directory-folder.png',.9,3.04,6.9,.95,(0,0,700,90))
        c.pic('directory-folder.png',.9,4.1,6.9,.65,(200,186,620,80),'detail')
        c.pic('agent-tools-completed.png',.9,5.07,6.9,1.35,(0,120,816,185))
        c.notes([('文档与图片','选择目录或添加附件，\n只处理获得授权的内容。'),('对话与工具','保留用户原话、任务结果，\n减少下一次重复交代。'),('统一接入','清洗、标准化与质量校验，\n记录来源和授权范围。')],x=8.5,y=2.96,w=3.8,gap=1.18)
    elif page==16:
        c.text('知识不仅保存结论，也保留原文、图片或文档块；点击来源即可核对依据。',.9,2.17,11.6,.5,18)
        c.pic('directory-original.png',.9,2.99,7.35,1.85)
        for i,t in enumerate(['事实 FACT','流程 WORKFLOW','案例 CASE','模板 TEMPLATE']):
            x=.9+(i%2)*3.75;y=5.06+(i//2)*.72;c.box(x,y,3.52,.53);c.text(t,x+.15,y+.1,3.2,.3,16,C,True)
        c.notes([('Evidence → Knowledge','来源证据与知识关联，\n可回看，不只保留摘要。'),('状态 · 范围 · 版本','明确何时有效、谁可以读，\n以及当前记录是哪一版。'),('实体 · 关系 · 索引','支持关键词、语义与关系检索，\n让结论能够回到原始依据。')],x=8.7,y=3.0,w=3.65,gap=1.12)
    elif page==17:
        c.text('只记得关键词或大意时，三路召回共同找回知识，再过滤、融合并附上来源。',.9,2.17,11.6,.5,18)
        c.pic('keyword-result.png',.9,3.0,7.3,1.4,(0,0,650,145))
        c.pic('directory-original.png',.9,4.65,7.3,1.79)
        c.notes([('关键词 FTS5','标题与词面精确匹配。'),('向量 · 系统 SDK','找回语义相近的记忆。'),('实体关系 Graph','沿实体、类目与关系召回。')],x=8.7,y=2.98,w=3.65,gap=.88)
        c.text('RRF 融合 → 重排\n范围、时间与有效状态过滤\n附来源引用',8.7,5.82,3.65,.85,17,C,True)
    elif page==18:
        c.text('短期记录',.9,2.5,7.6,.35,19,C,True)
        c.pic('stage-record.png',.9,2.97,7.6,1.5,(0,0,650,150))
        c.text('阶段记忆',.9,4.7,7.6,.35,19,C,True)
        c.pic('stage-record.png',.9,5.15,7.6,1.4,(0,275,650,145))
        c.notes([('短期 · 当前任务','保留本轮问题与处理要点，\n服务当前任务上下文。'),('中期 · 阶段状态','压缩、切换或会话结束后，\n保留阶段内容与到期时间。'),('长期 · 持久知识','选择长期保留的内容，\n进入知识与检索管线。')],x=8.85,y=2.69,w=3.4,gap=1.2)
    elif page==19:
        c.text('同一知识的多端修改，与不同记录之间的内容矛盾，需要分别处理。',.9,2.17,11.6,.5,18)
        c.pic('dreaming-review.png',.9,3.18,7.7,1.67,(0,220,880,190))
        c.pic('dreaming-review.png',.9,5.1,7.7,.7,(0,540,880,80),'detail')
        c.notes([('副本层：收敛同一知识','版本向量判断因果；LWW\n选择确定的并发胜者。'),('业务层：处理内容矛盾','比较实体与字段，选择更新、\n合并或人工确认。'),('更正计划先审批','冻结目标版本，用户核对后\n保存正文、版本与来源。')],x=8.94,y=2.97,w=3.4,gap=1.18)
    elif page==20:
        c.text('设备写入共享记忆后向在线节点传播；离线节点重连时发现缺失并补齐操作。',.9,2.17,11.6,.5,18)
        c.pic('device-sharing-controls.png',.9,2.98,7.35,3.47,(144,198,760,390))
        c.notes([('在线：传播更新','签名操作 → Gossip 推送\n接收确认 → 本地物化'),('重连：补齐差异','交换摘要 → 发现缺失\n补齐操作 → CRDT 合并'),('各端继续独立使用','重建索引后继续本地检索。\n设备列表不等于实时送达证明。')],x=8.7,y=3.0,w=3.62,gap=1.15)
    elif page==21:
        c.pic('shared-settings.png',.9,2.55,7.25,3.03)
        c.notes([('采集授权','未授权不采集，\n只读取已选目录与来源。'),('范围与敏感过滤','个人与共享分开；召回时\n复核范围，拦截敏感共享。'),('精准遗忘','先预览目标和范围，再确认。\n共享删除经墓碑传播到各端。')],x=8.66,y=2.61,w=3.65,gap=1.15)
        c.text('用户决定助手可用哪些记忆、哪些内容可以共享',.9,6.22,11.5,.4,19,C,True)
    elif page==23:
        for i,(t,b) in enumerate([('任务开始','召回有效记忆'),('上下文注入','范围、来源与预算'),('规划与工具','工具执行与审批'),('结果沉淀','对话、工具与阶段内容')]):
            x=.85+i*2.99;c.box(x,2.20,2.66,.43);c.text(t,x,2.25,2.66,.31,19,C,True,True);c.text(b,x,2.79,2.66,.32,14,center=True)
            if i<3:c.line(x+2.73,2.42,x+2.91,2.42)
        c.pic('agent-tools-completed.png',.9,3.48,7.7,2.95)
        c.notes([('从任务到可复用记忆','工具核算并写入文件后，\n保存结果供后续会话使用。'),('上下文注入边界','保留实际使用的来源记录；\n按预算注入，记忆文本\n不升级为系统指令。')],x=8.96,y=3.63,w=3.35,gap=1.37)
    elif page==24:
        c.pic('directory-recall.png',7.05,2.45,5.7,3.95,(55,215,800,210))
    elif page==25:
        c.text('真实案例示例：用户将星河观测活动资料放入已授权目录，助手读取并保存。',.9,2.17,11.5,.5,18)
        c.pic('directory-original.png',.9,2.96,8.0,1.95)
        c.pic('directory-folder.png',.9,5.2,8.0,1.05,(200,186,620,80))
        c.notes([('本例记录什么','11 月 8 日 19:00\n社区天文台三层\n器材预算 2680 元'),('保留可复用流程','领取手册、检查器材、\n分组记录、结束归还。')],x=9.22,y=3.01,w=3.02,gap=1.58)
    elif page==26:
        c.text('资料保存后，在新会话直接提问；助手召回时间、地点和预算，并提供来源链接。',.9,2.17,11.6,.5,18)
        c.pic('directory-recall.png',.9,2.9,7.85,3.7,(55,90,800,330))
        c.notes([('不用再交代背景','新会话询问活动安排，\n不必再次上传同一份资料。'),('答案保留来源','时间、地点、预算逐项列出，\n点击链接可回看原始内容。')],x=9.05,y=3.0,w=3.2,gap=1.42)
        c.pic('directory-original.png',9.05,5.8,3.15,.75,role='overview')
    elif page==27:
        c.text('活动通知发生变化：用户对照新旧内容，批准更正后，后续查询使用更新结果。',.9,2.17,11.6,.5,18)
        c.pic('dreaming-review.png',.9,3.16,8.05,1.8,(0,220,880,190))
        c.notes([('核对发生的变化','11 月 8 日 → 11 月 15 日\n三层 → 二层'),('保留没有变化的内容','预算与准备流程继续保留。'),('由用户确认','核对后批准更正，\n也可以保留原内容。')],x=9.25,y=3.1,w=3.03,gap=1.23)
        c.pic('dreaming-review.png',.9,5.4,8.05,.77,(0,540,880,80),'detail')
    elif page==28:
        c.pic('updated-recall.png',.9,2.5,7.85,4.0,(55,90,800,375))
        c.notes([('更新真正进入后续使用','11 月 15 日 19:30\n社区天文台二层'),('保留未改变的事实','器材预算仍为 2680 元，\n避免把整条资料重新交代。'),('答案有据可核对','回答同时引用旧安排与更新\n通知，方便核对变化原因。')],x=9.08,y=2.64,w=3.2,gap=1.22)
    elif page==30:
        c.text('原验证中两端并发更新、第三端离线；重连后正文、版本与来源收敛。\n下方为三台虚拟机当前查询同一共享记录的实际来源界面。',.9,2.17,11.6,.8,18)
        for i,key in enumerate('abc'):
            y=3.22+i*1.0
            c.text('设备 '+key.upper(),.95,y,1.4,.4,22,C,True)
            crop=(1530,895,1010,44) if key=='c' else (1785,1052,1010,44)
            c.pic('device-'+key+'-memory.png',2.52,y,9.6,.52,crop,'detail')
            c.line(.95,y+.78,12.28,y+.78)
        c.text('三端一致：11 月 10 日下午三点 · 三楼档案室',.9,6.4,11.5,.4,21,GOLD,True,True)
    else:raise ValueError(page)
    return c

def enrich(blobs,parts,order):
    result={};rtag='{'+NS['r']+'}embed'
    for page in sorted(PAGES):
        source=order[page-1];part=parts[source];root=ET.fromstring(blobs[part]);tree=root.find('p:cSld/p:spTree',NS)
        removed=[]
        for node in list(tree):
            offsets=node.xpath('./p:spPr/a:xfrm/a:off | ./p:grpSpPr/a:xfrm/a:off',namespaces=NS)
            if not offsets:continue
            x,y=[int(offsets[0].get(k))/EMU for k in ('x','y')]
            ids=node.xpath('.//p:cNvPr/@id',namespaces=NS)
            delete=(1.85<=y<=7.1) if page!=24 else bool(node.xpath('.//a:blip',namespaces=NS)) and x>6
            if delete:
                removed.extend(ids);tree.remove(node)
        canvas=compose(page);buf=BytesIO();canvas.prs.save(buf)
        rpart=str(Path(part).parent/'_rels'/(Path(part).name+'.rels'))
        rels=ET.fromstring(blobs[rpart]);existing={r.get('Id') for r in rels}
        id_base=max(int(v) for v in root.xpath('.//p:cNvPr/@id',namespaces=NS))+1
        with zipfile.ZipFile(buf) as z:
            newroot=ET.fromstring(z.read('ppt/slides/slide1.xml'));newrels=ET.fromstring(z.read('ppt/slides/_rels/slide1.xml.rels'))
            remap={}
            for rel in newrels:
                if not rel.get('Type').endswith('/image'):continue
                oldrid=rel.get('Id');rid=f'rIdProductShot{page}_{oldrid}'
                assert rid not in existing
                raw=z.read('ppt/'+rel.get('Target').replace('../',''))
                filename='product-'+hashlib.sha256(raw).hexdigest()[:20]+'.png'
                blobs['ppt/media/'+filename]=raw
                ET.SubElement(rels,'{'+REL+'}Relationship',Id=rid,Type=NS['r']+'/image',Target='../media/'+filename)
                remap[oldrid]=rid
            for node in newroot.find('p:cSld/p:spTree',NS):
                ids=node.xpath('.//p:cNvPr',namespaces=NS)
                if not ids:continue
                oldid=int(ids[0].get('id'));newid=id_base+oldid
                ids[0].set('id',str(newid));ids[0].set('name','Product evidence '+str(newid))
                for image in canvas.images:
                    if image['shape_id']==oldid:image['native_shape_id']=newid
                for blip in node.xpath('.//a:blip',namespaces=NS):blip.set(rtag,remap[blip.get(rtag)])
                tree.append(deepcopy(node))
        blobs[part]=ET.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
        blobs[rpart]=ET.tostring(rels,xml_declaration=True,encoding='UTF-8',standalone=True)
        result[page]={'source_page':source,'removed_shape_ids':removed,'screenshots':canvas.images}
    return result
