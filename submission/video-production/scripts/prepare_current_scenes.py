#!/usr/bin/env python3
"""Prepare measured, original-speed 0.1.12 desktop excerpts and scene metadata."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import struct
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
IMAGES = REPO / 'docs/delivery/assets/operations/03-current-workflows'
RAW = ROOT / 'raw/current-0.1.12'
OUT = ROOT / 'public/current'
OUT.mkdir(exist_ok=True)
assets = {}


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def still(name, folder=IMAGES):
    src = folder / (name+'.png')
    dst = OUT / src.name
    shutil.copyfile(src, dst)
    w, h = struct.unpack('>II', src.read_bytes()[16:24])
    assets[name] = {'kind':'image','src':'current/'+dst.name,'width':w,'height':h,
                    'source':src.relative_to(REPO).as_posix(),'sha256':digest(dst)}


def detail(name, source, box, prefix="outro-"):
    src = IMAGES / (source+'.png')
    dst = OUT / (prefix+name+'.png')
    Image.open(src).crop(box).save(dst)
    assets[prefix+name] = {'kind':'image','src':'current/'+dst.name,
        'width':box[2]-box[0],'height':box[3]-box[1], 'crop_box':box,
        'source':src.relative_to(REPO).as_posix(),'source_sha256':digest(src),'sha256':digest(dst)}


def clip(name, source, start, duration, crop):
    src = RAW / (source+'.mp4')
    dst = OUT / (name+'.mp4')
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(start),'-i',str(src),'-t',str(duration),
                    '-vf','crop='+crop,'-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',
                    '-movflags','+faststart',str(dst)],check=True)
    end = OUT / (name+'-end.png')
    subprocess.run(['ffmpeg','-v','error','-y','-sseof','-0.04','-i',str(dst),'-frames:v','1',str(end)],check=True)
    w,h = map(int,crop.split(':')[:2])
    assets[name] = {'kind':'video','src':'current/'+dst.name,'end':'current/'+end.name,
                    'width':w,'height':h,'frames':round(duration*30),'source':src.relative_to(REPO).as_posix(),
                    'start_seconds':start,'duration_seconds':duration,'speed':1,'crop':crop,
                    'source_sha256':digest(src),'sha256':digest(dst),'end_sha256':digest(end)}


for name in ['shared-workspace','sdk-version','directory-folder','directory-recall','directory-source',
             'dreaming-review','updated-recall','bill-recall','bill-source','preference-history',
             'shared-settings','shared-recall','shared-source','brief','device-controls','desktop-shortcut',
             'manual-entry','manual-recalled-body','edit-version-one','edit-version-two','stage-record',
             'forget-target','forget-completed','agent-task-result','agent-tools-completed','agent-task-recall',
             'keyword-result','keyword-source-body','knowledge-workflow-body',
             'behavior-enabled','behavior-demo-window','behavior-source-body']:
    still(name)
for args in [
    ('bill-query','current-bill-recall-01',14,10,'900:596:410:96'),
    ('bill-citation','current-bill-recall-01',47,10,'760:640:330:98'),
    ('directory-progress','directory-dreaming-02',16,9,'600:96:120:38'),
    ('directory-query','directory-recall-01',13,11,'850:300:460:310'),
    ('directory-approval','dreaming-approve-01',0,4,'880:620:270:108'),
    ('updated-query','dreaming-updated-recall-01',38,10,'850:300:460:310'),
    ('shared-query','shared-recall-01',48,14,'850:300:460:310'),
    ('shared-citation','shared-source-01',0,8,'740:150:340:138'),
    ('manual-form','current-manual-01',35,5,'550:328:434:220'),
    ('edit-change','current-edit-01',24,9,'620:398:399:187'),
]:
    clip(*args)

assets['directory-approval']['playback_alignment'] = 'start'
still('model-options', RAW)
still('update-panel', RAW)
detail('keyword-results', 'keyword-result', (0,0,976,135), prefix='')
detail('directory-original', 'directory-source', (0,0,760,185), prefix='')

for args in [
    ('nav','shared-workspace',(0,0,1200,56)),
    ('task','bill-recall',(60,215,840,515)),
    ('memory','directory-recall',(60,225,850,500)),
    ('capture','directory-folder',(0,0,1024,270)),
    ('preference','preference-history',(0,394,1024,650)),
    ('approval','dreaming-review',(0,210,880,620)),
    ('shared','shared-recall',(60,210,860,390)),
    ('insight','brief',(0,0,1024,309)),
    ('devices','device-controls',(0,0,1044,181)),
]:
    detail(*args)

detail('forget-confirmed','forget-completed',(0,0,148,26),prefix='')

# Each phrase anchors a visual change to the measured narration. Fractions are
# used by the separate silent visual review until matching speech is prepared.
scenes = {
 's06':[('agent-tools-completed','核算采购明细，写入文件并保存记忆',None,0),('agent-task-recall','新会话再次找回采购单 · 合计496元','打开新会话',.63)],
 's04':[('shared-workspace','统一桌面',None,0),('sdk-version','0.1.12 · 麒麟系统向量能力','服务与能力页',.56)],
 's07':[('bill-query','新会话查询账单',None,0),('bill-recall','电费、水费、燃气费明细','保存之后',.66)],
 's08':[('bill-recall','合计 434.50 元',None,0),('bill-citation','打开对应记忆的来源','点击回答',.32)],
 's10':[('manual-form','填写标题、正文与范围',None,0),('manual-recalled-body','保存后，检索并核对正文','保存后',.72)],
 's12':[('behavior-demo-window','公开资料整理 · 实际应用窗口',None,0),('behavior-source-body','本次记录：窗口标题与28秒使用时长','这里的记录',.28),('behavior-enabled','在采集与隐私中管理授权','你可以',.7)],
 's13':[('keyword-results','用内容关键词，找回活动资料',None,0),('keyword-source-body','核对原始安排与准备步骤','打开来源',.7)],
 's11':[('directory-folder','选择目录并保存',None,0),('directory-progress','主窗口显示整理进度与保存数量','貔貅自动开始整理',.22),('directory-query','后台整理后，新会话找回安排','完成后',.5),('directory-original','查看活动资料原文','点击来源',.82)],
 's11b':[('dreaming-review','对照原内容与更正建议',None,0),('directory-approval','批准更正，保存新版本','批准后',.37),('updated-query','新会话使用更新后的安排','下次询问',.56)],
 's15':[('preference-history','当前偏好与版本历史',None,0)],
 's16':[('edit-version-one','读取版本 1',None,0),('edit-change','整理时间更新为周五 17:00','保存后',.2),('edit-version-two','重新读取版本 2','每次编辑',.65)],
 's17':[('stage-record','从当前任务，衔接阶段与长期记忆',None,0)],
 's19':[('device-controls','查看可信设备与配对入口',None,0)],
 's20':[('shared-settings','选择家庭共享空间',None,0),('shared-query','换一台设备，继续查询约定','换到客厅',.26),('shared-citation','打开同一条记忆的来源','它找回',.73)],
 's23':[('shared-settings','读取范围与保存位置分别设置',None,0),('device-controls','选择参与协作的设备','通过共享设置',.56)],
 's24':[('forget-target','预览并核对目标与版本',None,0),('forget-confirmed','确认遗忘 1 条演示知识','系统让知识',.48)],
 's26':[('brief','近期知识与当天采集简报',None,0)],
 's27':[('sdk-version','桌面与后端版本一致',None,0),('model-options','选择模型并配置连接','打开设置',.35),('update-panel','查看当前版本与更新入口','查看更新信息',.55)],
}
data = {'version':'0.1.12','capture_date':'2026-09-10','assets':assets,
        'scenes':{k:[{'asset':a,'label':b,'cue':c,'fraction':f} for a,b,c,f in rows] for k,rows in scenes.items()}}
deck_names = ['bill-recall','directory-recall','dreaming-review','updated-recall',
              'shared-recall','shared-source','manual-entry','edit-version-two',
              'preference-history','brief']
deck = []
for name in deck_names:
    a = assets[name]
    w = min(a['width'], a['height'] * 357.328125 / 312)
    h = w * 312 / 357.328125
    deck.append({'src':a['src'],'source':a['source'],'imageWidth':a['width'],
                 'imageHeight':a['height'],'crop':{'x':(a['width']-w)/2,
                 'y':(a['height']-h)/2,'w':w,'h':h},'sha256':a['sha256']})
(ROOT/'src/deck-assets.json').write_text(json.dumps(deck,ensure_ascii=False,indent=2)+'\n')
(ROOT/'src/current-scenes.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(f'{len(scenes)}个新版场景，{len(assets)}项实拍素材')
