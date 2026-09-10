#!/usr/bin/env python3
"""Build the editable 18-slide project report from current product evidence.

Uses python-pptx, ffmpeg and repository screenshots/recordings. Diagrams and
text stay editable; original-speed desktop excerpts are embedded as frame animations.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / 'docs/delivery/assets'
IMAGES = ASSETS / 'operations/03-current-workflows'
RAW = ROOT / 'submission/video-production/raw/current-0.1.12'
BLUE, INK, MUTED = '1456B8', '172033', '526477'
PALE, PAPER, LINE, WHITE = 'EAF2FF', 'F6F7F9', 'DCE2EA', 'FFFFFF'
FONT = 'Noto Sans CJK SC'
W, H = 13.333333, 7.5
prs = Presentation()
prs.slide_width, prs.slide_height = Inches(W), Inches(H)
prs.core_properties.title = 'PIXIU 项目报告'
prs.core_properties.subject = '资料自动整理与可信设备记忆协作'
prs.core_properties.author = 'PIXIU'
prs.core_properties.last_modified_by = 'PIXIU'
prs.core_properties.keywords = 'PIXIU,目录监控,Dreaming,多设备协作'
inputs: set[Path] = {Path(__file__).resolve()}
slide_records = []


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rect(s, x, y, w, h, fill=WHITE, line=None, radius=True):
    a = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                           Inches(x), Inches(y), Inches(w), Inches(h))
    if radius:
        a.adjustments[0] = 0.12
    a.fill.solid()
    a.fill.fore_color.rgb = RGBColor.from_string(fill)
    a._element.spPr.append(OxmlElement('a:effectLst'))
    if line:
        a.line.color.rgb = RGBColor.from_string(line)
    else:
        a.line.fill.background()
    return a


def text(s, value, x, y, w, h, size=20, color=INK, bold=False, align=None):
    a = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = a.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.01)
    tf.margin_top = tf.margin_bottom = 0
    for i, line in enumerate(value.split('\n')):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.font.name = FONT
        p.font.size = Pt(size)
        p.font.bold = bold
        p.font.color.rgb = RGBColor.from_string(color)
        p.space_after = Pt(7)
        p.line_spacing = 1.12
        if align is not None:
            p.alignment = align
        for r in p.runs:
            rpr = r._r.get_or_add_rPr()
            ea = OxmlElement('a:ea')
            ea.set('typeface', FONT)
            rpr.append(ea)
    return a


def arrow(s, x1, y1, x2, y2, color=BLUE, width=2):
    a = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1),
                               Inches(x2), Inches(y2))
    a.line.color.rgb = RGBColor.from_string(color)
    a.line.width = Pt(width)
    end = OxmlElement('a:tailEnd')
    end.set('type', 'triangle')
    a.line._get_or_add_ln().append(end)


def image(s, name, x, y, w, h, caption=None):
    p = IMAGES / name
    inputs.add(p)
    iw, ih = Image.open(p).size
    scale = min(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    rect(s, x - .05, y - .05, w + .1, h + .1, WHITE, LINE)
    s.shapes.add_picture(str(p), Inches(x + (w-dw)/2), Inches(y + (h-dh)/2),
                         width=Inches(dw), height=Inches(dh))
    if caption:
        text(s, caption, x, y+h+.12, w, .4, 12, MUTED)


def card(s, title, body, x, y, w, h, accent=False, number=None):
    rect(s, x, y, w, h, PALE if accent else WHITE, LINE)
    if number:
        text(s, number, x+.2, y+.17, .6, .45, 22, BLUE, True)
    tx = x + (.8 if number else .2)
    text(s, title, tx, y+.18, w-(tx-x)-.15, .55, 21, BLUE, True)
    text(s, body, x+.2, y+.83, w-.4, h-.93, 17, INK)


def slide(title, sub, chapter, shots, takeaway):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = RGBColor.from_string(PAPER)
    n = len(prs.slides)
    text(s, 'PIXIU', .5, .25, 1.4, .4, 19, BLUE, True)
    text(s, chapter, 9.0, .29, 3.8, .3, 12, MUTED, align=PP_ALIGN.RIGHT)
    text(s, title, .6, .83, 12.1, .65, 30, INK, True)
    text(s, sub, .62, 1.57, 12, .55, 17, MUTED)
    rect(s, .62, 6.67, 12.08, .04, BLUE, radius=False)
    text(s, takeaway, .64, 6.85, 11.5, .4, 16, BLUE, True)
    text(s, f'{n:02d}', 12.18, 6.85, .5, .35, 14, MUTED, align=PP_ALIGN.RIGHT)
    # A short whole-slide fade keeps navigation calm. Live demonstrations use
    # the standard embedded media player, started when the slide appears.
    tr = OxmlElement('p:transition')
    tr.set('spd', 'med')
    tr.append(OxmlElement('p:fade'))
    s._element.append(tr)
    s.notes_slide.notes_text_frame.text = (
        f'{title}\n讲解要点：{takeaway}\n对应宣传视频：{shots}\n'
        '实拍版本：0.1.12；银河麒麟 V11 amd64；2026-09-10；公开合成资料。'
        '\n设备协作为同一宿主上的独立虚拟机。图形用于解释工作过程。'
    )
    slide_records.append({'page': n, 'title': title, 'video_shots': shots})
    return s


def movie(s, name, poster, x, y, w, h):
    p = (ASSETS / 'presentation-clips' / name).with_suffix('.gif')
    inputs.add(p)
    iw, ih = Image.open(p).size
    scale = min(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    rect(s, x-.05, y-.05, w+.1, h+.1, WHITE, LINE)
    s.shapes.add_picture(str(p), Inches(x+(w-dw)/2), Inches(y+(h-dh)/2), Inches(dw), Inches(dh))
    text(s, '▶ 进入本页自动播放 · 真实操作原速片段', x, y+h+.12, w, .4, 12, BLUE)


def prepare_clips():
    out = ASSETS / 'presentation-clips'
    out.mkdir(exist_ok=True)
    edits = [
        ('dreaming-approve-01.mp4', 'dreaming-approval.mp4', 0, 4, '880:620:270:108'),
        ('shared-recall-01.mp4', 'shared-recall.mp4', 48, 14, '900:596:410:96'),
        ('shared-source-01.mp4', 'shared-source.mp4', 0, 8, '760:640:330:98'),
    ]
    records = []
    for source, target, start, duration, crop in edits:
        src, dst = RAW / source, out / target
        inputs.add(src)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(start), '-i', str(src),
                        '-t', str(duration), '-vf', 'crop='+crop, '-an', '-c:v', 'libx264',
                        '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(dst)],
                       check=True)
        animation = dst.with_suffix('.gif')
        animation_input = ['-i', str(dst)]
        animation_filter = 'fps=4,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer'
        result_record = {}
        expected_duration = duration
        if target == 'dreaming-approval.mp4':
            result_image = IMAGES / 'updated-recall.png'
            inputs.add(result_image)
            animation_input += ['-loop', '1', '-t', '3', '-i', str(result_image)]
            animation_filter = ('[1:v]scale=880:620:force_original_aspect_ratio=decrease,'
                                'pad=880:620:(ow-iw)/2:(oh-ih)/2:color=0xf6f7f9,setsar=1[v1];'
                                '[0:v][v1]concat=n=2:v=1:a=0,' + animation_filter)
            expected_duration += 3
            result_record = {'result_image':result_image.relative_to(ROOT).as_posix(),
                             'result_image_sha256':digest(result_image), 'result_hold_seconds':3}
        subprocess.run(['ffmpeg', '-v', 'error', '-y', *animation_input,
                        '-filter_complex', animation_filter, '-loop', '-1', str(animation)], check=True)
        with Image.open(animation) as frames:
            animation_duration = sum((frames.seek(i) or frames.info.get('duration', 0))
                                     for i in range(frames.n_frames)) / 1000
        assert abs(animation_duration - expected_duration) < 0.05
        records.append({**result_record, 'animation':animation.name, 'animation_sha256':digest(animation),
                        'animation_duration_seconds':animation_duration, 'animation_fps':4,
                        'animation_plays':1, 'source': src.relative_to(ROOT).as_posix(), 'source_sha256': digest(src),
                        'file': target, 'start_seconds': start, 'duration_seconds': duration,
                        'crop': crop, 'speed': 1, 'sha256': digest(dst)})
    (out / 'manifest.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n')
    inputs.add(out / 'manifest.json')


def build():
    prepare_clips()
    s = slide('让每一台设备的记忆，彼此相通', 'PIXIU · 个人记忆助手',
              '项目报告 / 0.1.12', 's01', '自动积累知识，让经验随任务和设备继续使用。')
    text(s, '日常资料\n成为长期经验', .75, 2.43, 4.2, 1.55, 36, BLUE, True)
    text(s, '目录监控与 Dreaming\n去中心化多设备协作', .78, 4.45, 4.1, 1.1, 22)
    image(s, 'shared-workspace.png', 5.2, 2.2, 7.4, 4.1)

    s = slide('从一份资料，到下一次任务', '日常保存文件，逐步积累可查询、可更新、可共享的知识。',
              '01 / 使用全景', 's02–s03', '资料持续积累，经验反复使用。')
    for i, (a,b) in enumerate([('保存资料','放入授权目录\n或在对话中记录'),('自动整理','阅读内容\n联系已有知识'),('随时复用','新会话提问\n点击来源核对'),('可信协作','选择共享空间\n另一端接着使用')]):
        card(s,a,b,.7+3.17*i,2.58,2.45,2.55,accent=i in (1,3),number=f'0{i+1}')
        if i<3:arrow(s,3.2+3.17*i,3.9,3.75+3.17*i,3.9)
    text(s,'活动安排     ·     会议资料     ·     家庭账单     ·     工作交接',1.1,5.65,11.3,.55,22,BLUE,align=PP_ALIGN.CENTER)

    s = slide('一个窗口，完成任务与记忆协作', '会话、记忆、设备和设置，串起完整的日常工作。',
              '01 / 统一桌面', 's04、s06', '从提出任务到查看来源，操作集中在同一桌面。')
    image(s,'shared-workspace.png',.72,2.17,7.75,4.15)
    for i,(a,b) in enumerate([('会话','提出任务，查看工具过程'),('记忆','查资料、看偏好与简报'),('设备','建立信任，管理共享'),('设置','配置模型、采集和升级')]):
        text(s,a,8.9,2.32+i*.95,3.4,.4,22,BLUE,True)
        text(s,b,8.9,2.78+i*.95,3.6,.4,16)

    s = slide('授权一个目录，接住日常资料', '文件新增或更新后，后台自动接续整理。',
              '02 / 自动积累', 's11', '照常保存文件，知识库持续积累。')
    image(s,'directory-folder.png',.72,2.48,7.25,2.12,'实拍：选择演示目录并保存设置')
    for i,(a,b) in enumerate([('选择目录','授权需要整理的资料位置'),('保存文件','新建、修改或移入文档'),('后台整理','等待写入稳定，逐份处理')]):
        text(s,f'0{i+1}',8.5,2.45+i*1.08,.65,.5,25,BLUE,True)
        text(s,a,9.23,2.46+i*1.08,3.3,.4,21,INK,True)
        text(s,b,9.23,2.96+i*1.08,3.3,.45,15)
    rect(s,.8,5.15,7.2,.9,PALE)
    text(s,'例：星河观测活动安排.md',1.06,5.39,6.7,.4,22,BLUE,True)

    s = slide('Dreaming：把资料联系成知识', '阅读文档，寻找关联，保存内容与来源。',
              '02 / 自动整理', 's11', '在新会话里，直接找回活动安排和原文。')
    image(s,'directory-recall.png',.72,2.15,7.1,4.42)
    for i,(a,b) in enumerate([('阅读','理解日期、地点与预算'),('联系','查找已有活动及相关记录'),('保存','新知识进入个人记忆'),('使用','回答带上对应资料来源')]):
        text(s,a,8.3,2.36+i*.95,3.8,.4,22,BLUE,True)
        text(s,b,8.3,2.85+i*.95,4.1,.4,17)

    s = slide('资料更新，先对照，再保存', 'Dreaming 提出更正方案，用户批准后形成新版本。',
              '02 / 更新审批', 's11b', '11月15日 19:30 · 社区天文台二层 · 预算2680元')
    movie(s,'dreaming-approval.mp4','dreaming-review.png',.72,2.2,7.55,4.0)
    card(s,'对照', '查看原内容与整理后内容',8.62,2.22,3.98,1.22,True)
    card(s,'批准', '确认时间与地点的更新',8.62,3.62,3.98,1.22)
    card(s,'再次查询', '新会话使用更新后的安排',8.62,5.02,3.98,1.22)

    s = slide('换个会话，继续核对家庭账单', '按月份和支出类别提问，明细与来源一起返回。',
              '03 / 知识复用', 's07–s08', '从答案回到记录，让金额有据可查。')
    image(s,'bill-recall.png',.72,2.14,7.35,4.45)
    text(s,'434.50',8.62,2.5,3.9,.9,48,BLUE,True)
    text(s,'元 · 九月合计',8.65,3.48,3.7,.45,23)
    for i,(a,b) in enumerate([('电费','210.00 元'),('水费','68.50 元'),('燃气费','156.00 元')]):
        text(s,a,8.68,4.2+i*.65,1.6,.4,20,MUTED)
        text(s,b,10.42,4.2+i*.65,2.05,.4,20,INK,True,PP_ALIGN.RIGHT)

    s = slide('多种来源，共同积累经验', '按授权接入日常活动，让资料带着出处进入记忆。',
              '03 / 多源接入', 's09–s12', '对话、工具、文档和行为，汇入同一套记忆服务。')
    for i,(a,b) in enumerate([('对话与工具','用户表达\n任务执行结果'),('文件与附件','授权目录\n会话中的资料'),('手动记录','明确保存内容\n选择使用范围'),('应用行为','授权后的应用统计\n按日期查看简报')]):
        x=.75+(i%2)*3.7;y=2.2+(i//2)*1.98
        card(s,a,b,x,y,3.25,1.75,accent=i==1)
        arrow(s,x+3.25,y+.87,8.4,4.05,LINE,1.3)
    rect(s,8.55,2.92,3.95,2.3,BLUE)
    text(s,'统一记忆',8.86,3.27,3.3,.55,30,WHITE,True)
    text(s,'来源 · 范围 · 版本\n按需查询与复用',8.88,4.07,3.3,.9,20,WHITE)

    s = slide('回答方式，随偏好更新', '从用户表达中提取偏好，保留当前值与版本历史。',
              '03 / 个性化', 's15', '让下一次任务沿用合适的表达方式。')
    image(s,'preference-history.png',.72,2.13,7.45,4.45)
    for i,(a,b) in enumerate([('操作习惯','记录常用的处理方式'),('输出风格','调整简洁或详细的表达'),('安全策略','按用户设置使用资料')]):
        text(s,a,8.67,2.5+i*1.17,3.8,.5,24,BLUE,True)
        text(s,b,8.67,3.07+i*1.17,3.8,.55,17)

    s = slide('把事实和经验，留给以后的任务', '知识按用途组织；当前任务、阶段状态与长期经验相互衔接。',
              '03 / 记忆组织', 's14、s16–s17', '既能记住一件事，也能复用一套做法。')
    for i,(a,b) in enumerate([('事实','活动的时间与地点'),('流程','核对、分类、登记'),('案例','问题与处理经验'),('模板','事项、负责人、时间')]):
        card(s,a,b,.73+i*3.18,2.23,2.87,1.65,accent=i%2==0)
    for i,(a,b) in enumerate([('当前任务','保存本轮要点'),('阶段记忆','衔接会话与项目'),('长期知识','反复查询和复用')]):
        x=.9+i*4.2
        rect(s,x,4.58,3.2,1.36,WHITE,LINE)
        text(s,a,x+.2,4.77,2.8,.4,23,BLUE,True)
        text(s,b,x+.2,5.36,2.8,.4,17)
        if i<2:arrow(s,x+3.25,5.27,x+4.0,5.27)

    s = slide('可信设备之间，共享知识与经验', '每台设备保存本地副本，通过共享空间交换更新。',
              '04 / 多设备协作', 's18–s19', '完成配对与授权，让多台设备共同记忆。')
    nodes=[(.8,2.3,'书房设备'),(4.6,4.6,'随身设备'),(8.4,2.3,'客厅设备')]
    arrow(s,3.85,3.27,8.4,3.27)
    arrow(s,2.55,3.95,5.72,4.6)
    arrow(s,9.68,3.95,7.06,4.6)
    for x,y,name in nodes:card(s,name,'本地记忆副本\n授权读写共享资料',x,y,3.05,1.65,True)
    text(s,'配对建立信任',4.44,2.7,3.4,.4,19,BLUE,True,PP_ALIGN.CENTER)
    text(s,'共享空间传递更新',4.06,3.64,4.2,.4,20,BLUE,True,PP_ALIGN.CENTER)
    text(s,'实测：同一宿主上的三台独立 V11 虚拟机',.83,6.22,10.4,.3,12,MUTED)

    s = slide('这里记住，那里接着使用', '书房保存共享约定，客厅助手查回时间、步骤和来源。',
              '04 / 跨端实录', 's20', '每周六 9:00 · 按主题分类 · 更新借阅登记')
    movie(s,'shared-recall.mp4','shared-recall.png',.73,2.2,7.3,4.0)
    card(s,'发送端', '选择家庭共享空间\n保存整理书房的约定',8.47,2.2,4.1,1.7,True)
    card(s,'接收端', '在新会话中提问\n打开同一条记忆来源',8.47,4.16,4.1,1.7)
    s.notes_slide.notes_text_frame.text += '\n两端核对：同一记忆编号、正文、版本1、证据编号一致。'

    s = slide('离线继续工作，重连补齐更新', '本地记忆持续读写，连接恢复后交换并合并更新。',
              '04 / 连续协作', 's21–s22', '断连与并发实测：恢复后，三端正文、版本和来源一致。')
    for i,(a,b) in enumerate([('连接中断','每台设备使用\n自己的本地副本'),('分别修改','记录版本关系\n保存新的操作'),('恢复连接','比较缺少的记录\n补齐并合并更新')]):
        card(s,a,b,.8+i*4.25,2.45,3.72,2.36,accent=i==2,number=f'0{i+1}')
        if i<2:arrow(s,4.55+i*4.25,3.65,4.94+i*4.25,3.65)
    rect(s,.86,5.25,11.65,.84,PALE)
    text(s,'0.1.12 · 三台 V11 虚拟机 · 本次恢复约30.5秒',1.1,5.43,11.1,.48,23,BLUE,True,PP_ALIGN.CENTER)
    s.notes_slide.notes_text_frame.text += '\n机制：CRDT合并版本；Gossip传播新操作；反熵对账补齐记录。30.5秒为该次场景观测。'

    s = slide('共享与遗忘，由用户掌握', '选择读取范围和保存位置，查看目标后确认遗忘。',
              '04 / 用户控制', 's23–s24', '采集、共享、更新与遗忘，都有明确的用户操作。')
    image(s,'shared-settings.png',.74,2.28,7.24,3.07,'实拍：读取范围与新记忆保存位置分别设置')
    for i,(a,b) in enumerate([('选择范围','个人资料与可信共享空间'),('掌握变更','对照更新建议，审批保存'),('确认遗忘','预览目标，确认后移出检索')]):
        text(s,a,8.47,2.33+i*1.15,4.1,.5,23,BLUE,True)
        text(s,b,8.47,2.94+i*1.15,4.1,.46,17)
    text(s,'共享知识的遗忘状态同步到可信设备',1.0,5.87,11.2,.5,23,BLUE,True)

    s = slide('四个模块，连成完整的记忆助手', '桌面负责交互，记忆服务积累经验，设备同步连接副本，系统适配融入麒麟。',
              '05 / 系统架构', 's05、s13', 'PIXIU 将完整智能体与可持续积累的记忆连接起来。')
    rect(s,.76,2.2,11.84,1.05,BLUE)
    text(s,'桌面助手',1.03,2.39,2.2,.45,24,WHITE,True)
    text(s,'会话与任务  /  工具执行  /  用户审批  /  四个统一入口',3.51,2.46,8.6,.5,20,WHITE)
    arrow(s,3.56,3.25,3.56,3.66)
    arrow(s,9.78,3.25,9.78,3.66)
    card(s,'记忆服务','资料整理与来源\n偏好、知识与检索\n更新、流转与遗忘',.76,3.68,5.6,2.15,True)
    card(s,'设备同步','可信配对与共享范围\n本地副本与操作日志\n重连补齐与版本合并',6.95,3.68,5.65,2.15)
    arrow(s,6.36,4.72,6.95,4.72)
    rect(s,.76,6.05,11.84,.43,PALE)
    text(s,'系统适配  ·  麒麟桌面  ·  文本向量  ·  向量存储  ·  用户服务与单包升级',1.02,6.1,11.4,.36,16,BLUE,True,PP_ALIGN.CENTER)
    s.notes_slide.notes_text_frame.text += '\nPIXIU原创：记忆引擎、检索、流转、同步、Provider、系统适配与管理界面。上游KylinAgent和Runtime提供会话、规划、工具及审批。'

    s = slide('一个安装包，融入麒麟桌面', '从安装、模型设置到后续升级，围绕日常使用组织。',
              '05 / 部署维护', 's04、s27', '银河麒麟 V11 优先适配，同时提供 Debian 兼容构建。')
    image(s,'sdk-version.png',.78,2.26,7.7,1.7,'实拍：0.1.12 桌面与后端版本、麒麟向量能力')
    for i,(a,b) in enumerate([('安装','桌面、后端与运行时随包交付'),('配置','选择模型，授权采集与共享'),('使用','快捷键唤起，任务与记忆协作'),('升级','校验签名，完成健康检查')]):
        text(s,f'0{i+1}',8.85,2.25+i*.92,.55,.4,21,BLUE,True)
        text(s,a,9.51,2.24+i*.92,2.9,.4,21,BLUE,True)
        text(s,b,8.85,2.74+i*.92,3.9,.42,15)
    rect(s,.86,4.8,7.45,1.25,PALE)
    text(s,'记忆服务 · 桌面助手 · 离线运行依赖',1.1,5.0,7,.45,21,BLUE,True)
    text(s,'版本、许可证与升级清单随包提供',1.1,5.59,7,.35,16)

    s = slide('用数据核对效果，用场景验证协作', '质量评测说明样本与环境；原生验证覆盖安装、记忆和多设备流程。',
              '05 / 效果验证', 's28', '版本、环境、样本与结果一起呈现，便于复核。')
    for i,(v,a,b) in enumerate([('100%','检索召回率','50组检索'),('100%','偏好准确率','15 / 15'),('96%','冲突处理正确率','24 / 25'),('115ms','检索P95延迟','1000次检索')]):
        x=.77+i*3.18
        rect(s,x,2.38,2.88,2.26,WHITE,LINE)
        text(s,v,x+.2,2.61,2.5,.73,37,BLUE,True)
        text(s,a,x+.2,3.51,2.5,.45,19,INK,True)
        text(s,b,x+.2,4.08,2.5,.35,16,MUTED)
    text(s,'历史评测：Debian portable · pixiu-family-expense-v1',.83,4.92,11.65,.4,16,MUTED)
    rect(s,.82,5.51,11.69,.65,PALE)
    text(s,'0.1.12 V11：双 SDK、全新安装、签名升级、三端共享与并发恢复通过',1.03,5.69,11.26,.36,18,BLUE,True,PP_ALIGN.CENTER)

    s = slide('自动积累，可信协作', '让今天的资料，成为下一次任务可用的经验。',
              '06 / 应用价值', 's26、s29–s30', 'PIXIU · 让每一台设备的记忆，彼此相通。')
    for i,(a,b) in enumerate([('资料自然积累','授权目录，后台持续整理'),('回答有据可查','找到知识，也找到对应来源'),('经验跨端复用','可信设备接续任务与资料')]):
        text(s,a,.82,2.46+i*1.15,5.3,.56,28,BLUE,True)
        text(s,b,.85,3.12+i*1.15,5.3,.44,18)
    image(s,'brief.png',6.72,2.2,5.8,3.95,'实拍：近期知识与当天采集简报')
    target = ASSETS / '项目报告.pptx'
    prs.save(str(target))
    manifest = {'schema':1,'version':(ROOT/'VERSION').read_text().strip(),
                'design':{'blue':'#'+BLUE,'ink':'#'+INK,'paper':'#'+PAPER,'font':FONT},
                'audience':'高层领导与评委','slides':slide_records,
                'inputs':[{'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p)} for p in sorted(inputs)],
                'output':{'path':target.relative_to(ROOT).as_posix(),'sha256':digest(target)}}
    (ASSETS/'presentation-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print('已生成18页项目报告：可编辑图表、当前实拍、2段嵌入演示')


if __name__ == '__main__':
    build()
