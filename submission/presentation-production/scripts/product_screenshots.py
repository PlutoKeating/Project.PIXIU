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
PAGES={7,10,11,12,13,15,16,17,18,19,20,21,22,23,24,25,26,27,28,30}
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
        path=name if isinstance(name,Path) else CAP/name if name.startswith('device-') else VIDEO/name
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

# Every crop below is the complete application window, never a text fragment.
RAW=ROOT/'submission/video-production/raw/current-0.1.12'
FULL=WORK/'source/full-window-captures'
APP=(120,0,1200,838)
SOURCES={
 'bill':(FULL/'bill.png',APP,[(470,320,760,280)],'账单明细、合计与来源'),
 'task':(FULL/'task.png',APP,[(465,185,755,325)],'工具完成记录与记忆保存结果'),
 'stage':(FULL/'stage.png',APP,[(285,215,1025,570)],'短期记录与阶段记忆'),
 'keyword':(FULL/'keyword.png',APP,[(307,118,992,50),(630,322,650,66)],'查询条件、结果与来源入口'),
 'settings':(FULL/'settings.png',APP,[(300,220,740,210)],'记忆授权与共享范围'),
 'directory':(FULL/'directory.png',APP,[(285,165,1030,290)],'授权目录与采集设置'),
 'recall':(RAW/'01-directory-recall.png',APP,[(470,320,775,220)],'跨会话回答与来源链接'),
 'source':(RAW/'02-directory-source.png',APP,[(347,210,726,395)],'来源窗口中的知识与原始资料'),
 'dreaming':(RAW/'03-dreaming-review.png',APP,[(280,357,857,285),(880,674,255,44)],'新旧内容对照与审批按钮'),
 'updated':(RAW/'04-updated-recall.png',APP,[(470,320,775,260)],'更新后的安排与引用依据'),
 'devices':(CAP/'device-sharing-controls.png',APP,[(145,200,755,390)],'共享范围与可信设备列表'),
 'service':(FULL/'service.png',APP,[(298,214,720,225)],'版本与系统能力状态'),
}

NOTES={7: [('自动记忆，持续整合', '理解授权资料，关联既有记忆，\n形成新建、更正与合并方案。'), ('记忆共享，分布互连', '可信设备按范围共享记忆，\n新会话可继续查询与核对。'), ('结果可以核对', '回答列出明细与合计，\n点击来源回到原始依据。')], 12: [('01  理解资料', '逐块读取已授权资料，\n保留原始内容与来源。'), ('02  关联记忆', '对照原记录，形成新建、\n更正或合并方案。'), ('03  整合更新', '新建按授权保存；\n更正与合并经批准生效。')], 13: [('用户做什么', '保存清单后，在新会话提问。'), ('系统完成什么', '召回明细、核算合计，\n并提供可点击的来源。'), ('得到什么价值', '无需重新翻文件与逐项抄录，\n答案与原始记录可以核对。')], 15: [('文档与图片', '选择目录或添加附件，\n只处理获得授权的内容。'), ('对话与工具', '保留用户原话、任务结果，\n减少下一次重复交代。'), ('统一接入', '清洗、标准化与质量校验，\n记录来源和授权范围。')], 16: [('Evidence → Knowledge', '来源证据与知识关联，\n可回看，不只保留摘要。'), ('状态 · 范围 · 版本', '明确何时有效、谁可以读，\n以及当前记录是哪一版。'), ('实体 · 关系 · 索引', '支持关键词、语义与关系检索，\n让结论能够回到原始依据。')], 17: [('关键词 FTS5', '标题与词面精确匹配。'), ('向量 · 系统 SDK', '找回语义相近的记忆。'), ('实体关系 Graph', '沿实体、类目与关系召回。')], 18: [('短期 · 当前任务', '保留本轮问题与处理要点，\n服务当前任务上下文。'), ('中期 · 阶段状态', '压缩、切换或会话结束后，\n保留阶段内容与到期时间。'), ('长期 · 持久知识', '选择长期保留的内容，\n进入知识与检索管线。')], 19: [('副本层：收敛同一知识', '版本向量判断因果；LWW\n选择确定的并发胜者。'), ('业务层：处理内容矛盾', '比较实体与字段，选择更新、\n合并或人工确认。'), ('更正计划先审批', '冻结目标版本，用户核对后\n保存正文、版本与来源。')], 20: [('在线：传播更新', '签名操作 → Gossip 推送\n接收确认 → 本地物化'), ('重连：补齐差异', '交换摘要 → 发现缺失\n补齐操作 → CRDT 合并'), ('各端继续独立使用', '重建索引后继续本地检索。\n设备列表不等于实时送达证明。')], 21: [('采集授权', '未授权不采集，\n只读取已选目录与来源。'), ('范围与敏感过滤', '个人与共享分开；召回时\n复核范围，拦截敏感共享。'), ('精准遗忘', '先预览目标和范围，再确认。\n共享删除经墓碑传播到各端。')], 23: [('从任务到可复用记忆', '工具核算并写入文件后，\n保存结果供后续会话使用。'), ('上下文注入边界', '保留实际使用的来源记录；\n按预算注入，记忆文本\n不升级为系统指令。')], 25: [('本例记录什么', '11 月 8 日 19:00\n社区天文台三层\n器材预算 2680 元'), ('保留可复用流程', '领取手册、检查器材、\n分组记录、结束归还。')], 26: [('不用再交代背景', '新会话询问活动安排，\n不必再次上传同一份资料。'), ('答案保留来源', '时间、地点、预算逐项列出，\n点击链接可回看原始内容。')], 27: [('核对发生的变化', '11 月 8 日 → 11 月 15 日\n三层 → 二层'), ('保留没有变化的内容', '预算与准备流程继续保留。'), ('由用户确认', '核对后批准更正，\n也可以保留原内容。')], 28: [('更新真正进入后续使用', '11 月 15 日 19:30\n社区天文台二层'), ('保留未改变的事实', '器材预算仍为 2680 元，\n避免把整条资料重新交代。'), ('答案有据可核对', '回答同时引用旧安排与更新\n通知，方便核对变化原因。')]}

def window(c,key,x,y,w,h,caption):
    path,crop,rects,label=SOURCES[key]
    c.pic(path,x,y,w,h,crop)
    im=c.images[-1];px,py,dw,dh=im['box_inches'];l,t,cw,ch=crop
    im['context']='complete desktop' if crop==(0,0,3840,2160) else 'complete application window';im['caption']=caption;im['annotations']=[]
    for rx,ry,rw,rh in rects:
        assert l<=rx and t<=ry and rx+rw<=l+cw and ry+rh<=t+ch,(key,rects)
        shape=c.slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(px+(rx-l)*dw/cw),Inches(py+(ry-t)*dh/ch),Inches(rw*dw/cw),Inches(rh*dh/ch))
        shape.fill.background();shape.line.color.rgb=RGBColor.from_string('EF4444');shape.line.width=Pt(1.6)
        im['annotations'].append({'rect_pixels':[rx,ry,rw,rh],'label':label})
    c.text(caption+'（红框：'+label+'）',x,y+h+.10,w,.52,12,'C4DDED',center=True)


def compose(page):
    c=Canvas()
    if page!=24:c.box(.65,1.98,12.03,4.92)
    if page in {11,30}:
        intro='配对可信设备并授权共享范围后，各端保留本地副本；断连可独立使用，重连后补齐差异。' if page==11 else '两端并发更新、第三端离线的原验证已完成；下图分别展示三台虚拟机当前的查询与来源。'
        c.text(intro,.9,2.16,11.5,.67,18)
        for i,(key,domain) in enumerate([('a','kylin-v11'),('b','pixiu-video-b'),('c','pixiu-release-c')]):
            x=.88+i*4.0
            c.text('设备 '+key.upper(),x,2.93,3.6,.35,22,C,True,True)
            c.text(domain,x,3.35,3.6,.3,13,'C4DDED',center=True)
            crop=(0,0,3840,2160)
            rect=(1520,875,1100,100) if key=='c' else (1770,1035,1150,105)
            SOURCES[key]=(CAP/('device-'+key+'-memory.png'),crop,[rect],'共享记录正文')
            window(c,key,x,3.87,3.6,2.025,'图 '+str(i+1)+'：设备 '+key.upper()+' 的完整记忆窗口')
        c.text('三端一致：11 月 10 日下午三点 · 三楼档案室',.9,6.48,11.5,.34,20,GOLD,True,True)
    elif page==10:
        for i,(key,title,cap,body) in enumerate([
            ('devices','记忆共享，分布互连','可信设备与共享设置','授权共享 · 本地副本 · 重连补齐'),
            ('dreaming','自动记忆，持续整合','后台整合与更正审批','后台理解 · 关联记忆 · 更正审批')]):
            x=.9+i*6.0;c.text(title,x,2.24,5.45,.45,24,C,True)
            window(c,key,x,2.96,5.45,3.14,'图 '+str(i+1)+'：'+cap)
            c.text(body,x,6.45,5.45,.35,18,GOLD,True,True)
    elif page==24:
        window(c,'recall',7.08,2.4,5.60,3.9,'图 1：星河活动的实际查询窗口')
    elif page==23:
        for i,(t,b) in enumerate([('任务开始','召回有效记忆'),('上下文注入','范围、来源与预算'),('规划与工具','工具执行与审批'),('结果沉淀','对话、工具与阶段内容')]):
            x=.85+i*2.99;c.box(x,2.18,2.66,.43);c.text(t,x,2.23,2.66,.31,19,C,True,True);c.text(b,x,2.73,2.66,.32,14,center=True)
            if i<3:c.line(x+2.73,2.40,x+2.91,2.40)
        window(c,'task',.9,3.2,7.6,3.12,'图 1：工具任务完成后的会话窗口')
        c.notes(NOTES[page],x=8.85,y=3.25,w=3.48,gap=1.45)
    else:
        configs={
          7:('bill','保存资料、持续整合、跨设备共享，让 Agent 的每次任务都能接续已有记忆。','桌面助手的完整会话窗口'),
          12:('dreaming','授权资料变化后，后台理解内容并关联旧记忆；更正与合并交由用户审批。','自动记忆生成的更正方案'),
          13:('bill','家庭开销核对：清单已交给助手，换个会话询问明细、合计与来源。','新会话中的账单检索结果'),
          15:('directory','用户通过会话、附件或授权目录交付资料；工具结果与授权记录进入统一记忆管线。','采集与隐私设置完整窗口'),
          16:('source','知识保留结论及其原文、图片或文档块；点击来源即可回看原始依据。','知识与来源的关联展示'),
          17:('keyword','只记得关键词或大意时，三路召回找回知识，经过 RRF 融合、重排和范围过滤，附上来源。','关键词查询与来源入口'),
          18:('stage','当前任务形成短期记录，阶段内容可继续保留，并按需要转入长期知识。','短期与阶段记忆的完整窗口'),
          19:('dreaming','同一知识的多端修改，与不同记录之间的内容矛盾，需要分别处理。','内容更正的核对与审批窗口'),
          20:('devices','共享记忆向在线节点传播；离线节点重连时发现缺失，再补齐操作。','设备共享与同步控制窗口'),
          21:('settings','由用户决定助手可用哪些记忆、哪些内容可以共享；采集和使用均受授权约束。','助手记忆权限与共享范围设置'),
          22:('service','麒麟 V11 优先使用系统能力；Debian 提供基本记忆读写与检索的兼容路径。','服务与能力的完整设置窗口'),
          25:('source','示例资料：用户将星河观测活动安排放入授权目录，助手读取并保存来源。','活动知识与原始文件内容'),
          26:('recall','资料保存后，在新会话直接提问；助手召回时间、地点和预算，并提供来源链接。','新会话召回已保存的活动资料'),
          27:('dreaming','活动通知发生变化：用户核对新旧内容，批准后，后续查询使用更新结果。','更正前后对照与批准操作'),
          28:('updated','更正后的安排进入后续查询，未变化的预算与准备流程继续保留。','批准更正后的查询结果'),
        }
        key,intro,caption=configs[page]
        c.text(intro,.9,2.15,11.5,.67,18)
        window(c,key,.9,2.85,7.6,3.55,'图 1：'+caption)
        if page==22:
            items=[('银河麒麟 V11','Embedding / Vector Engine\n优先调用已接入的系统能力。'),('Debian 兼容','缺少专有 SDK 时，\n基本记忆读写与检索可用。'),('签名升级与恢复','原验证：47 条记忆\n升级与恢复前后摘要一致。')]
        else:items=NOTES[page]
        c.notes(items,x=8.86,y=2.96,w=3.47,gap=1.23)
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
