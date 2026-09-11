#!/usr/bin/env python3
"""Prepare narration-directed picture selections and native pointer excerpts."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / 'src/current-scenes.json').read_text())
out = ROOT / 'public/directed'
out.mkdir(exist_ok=True)


def clip(name, source, start, duration, crop):
    source = ROOT / 'raw' / ((source if '/' in source else 'directed-0.1.12/' + source) + '.mp4')
    target = out / (name + '.mp4')
    end = out / (name + '-end.png')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(start), '-i', str(source),
                    '-t', str(duration), '-vf', 'crop=' + crop, '-an', '-c:v', 'libx264',
                    '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(target)], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-sseof', '-0.04', '-i', str(target),
                    '-frames:v', '1', str(end)], check=True)
    width, height = map(int, crop.split(':')[:2])
    data['assets'][name] = {'kind': 'video', 'src': 'directed/' + target.name,
        'end': 'directed/' + end.name, 'width': width, 'height': height,
        'frames': round(duration * 30), 'playback_alignment': 'start', 'native_pointer': True,
        'source': str(source.relative_to(ROOT)), 'start_seconds': start, 'duration_seconds': duration,
        'crop': crop, 'speed': 1, 'capture_fps': 30,
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    meta = json.loads(source.with_suffix('.json').read_text()) if source.with_suffix('.json').exists() else {}
    if meta.get('timing_basis'):
        _, _, x, y = map(int, crop.split(':'))
        data['assets'][name]['clicks'] = [
            {'frame': round((a['actual_click']-start)*30), 'x': a['to'][0]-x, 'y': a['to'][1]-y}
            for a in meta['actions'] if a.get('actual_click') is not None
            and start <= a['actual_click'] < start+duration]


def montage(name, source, pieces, crop):
    parts = []
    clicks = []
    cursor = 0
    for index, (start, duration) in enumerate(pieces):
        key = name + '-part-' + str(index)
        clip(key, source, start, duration, crop)
        part = data['assets'].pop(key)
        parts.append(out / (key + '.mp4'))
        clicks.extend({**click, 'frame': click['frame'] + cursor} for click in part.get('clicks', []))
        cursor += round(duration * 30)
        (out / (key + '-end.png')).unlink()
    listing = out / (name + '.concat')
    listing.write_text(''.join("file '" + p.name + "'\n" for p in parts))
    target = out / (name + '.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(listing),
                    '-c', 'copy', '-movflags', '+faststart', str(target)], check=True)
    end = out / (name + '-end.png')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-sseof', '-0.04', '-i', str(target),
                    '-frames:v', '1', str(end)], check=True)
    for path in [listing, *parts]:
        path.unlink()
    width, height = map(int, crop.split(':')[:2])
    original = ROOT / 'raw/directed-0.1.12' / (source + '.mp4')
    data['assets'][name] = {'kind':'video','src':'directed/'+target.name,'end':'directed/'+end.name,
        'width':width,'height':height,'frames':cursor,'playback_alignment':'start','native_pointer':True,
        'capture_fps':30,'speed':1,'crop':crop,'source':str(original.relative_to(ROOT)),
        'pieces':[{'start_seconds':s,'duration_seconds':d} for s,d in pieces], 'clicks':clicks,
        'source_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
        'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}


for values in [
    ('navigation-conversation', 'navigation', 1, 5, '1200:56:120:38'),
    ('navigation-memory', 'navigation', 8, 5, '1200:56:120:38'),
    ('navigation-devices', 'navigation', 15, 5, '1200:56:120:38'),
    ('navigation-settings', 'navigation', 22, 5, '1200:56:120:38'),
    ('bill-amounts', 'bill', 7, 12, '820:286:480:190'),
    ('preferences', 'preferences-focus', 7, 15, '620:594:290:146'),
    ('brief-reading', 'preferences-brief', 21, 12, '984:244:290:410'),
    ('new-bill-answer', 'bill-full', 26, 4, '820:360:470:185'),
    ('new-bill-source', 'bill-full', 30, 10, '760:640:330:98'),
    ('workflow-source', 'workflow', 2.5, 10, '660:112:628:380'),
    ('pair-result', 'pairing-v2', 23.5, 2, '480:20:430:668'),
    ('pair-open', 'pairing-v2', 1, .85, '310:48:140:540'),
    ('pair-verify', 'pairing-v2', 20.9, 1.4, '560:44:430:630'),
    ('stage-result', 'stage-result', .4, 4, '660:58:628:324'),
    ('stage-open', 'stage-v2', 1, 6, '700:50:289:220'),
    ('stage-save', 'stage-v2', 13.7, 1.7, '560:50:520:758'),
    ('forget-action', 'current-0.1.12/current-forget-01', 20.5, 1.1, '650:48:470:730'),
    ('new-bill-source-detail', 'bill-full', 33, 8, '718:154:350:212'),
]:
    clip(*values)
montage('new-bill-actions', 'bill-full', [(2.5,.8),(9.7,.8),(15.5,.8)], '1200:740:120:38')

anchors = {
    's06': [None, '打开新会话'], 's07': [None, '助手找回账单'],
    's08': [None, '沿着回答'], 's10': [None, '立即查询'],
    's12': [None, '系统记录', '采集权限'],
    's11': [None, '助手开始后台', '完成后', '点击来源'],
    's11b': [None, '然后批准保存', '再次查询'],
    's16': [None, '修改时间', '查看版本二'],
    's20': [None, '换到客厅查询', '点击来源'],
    's23': [None, '再到设备页'], 's24': [None, '系统更新知识'],
    's27': [None, '在设置中', '也可以查看'],
}
for shot_id, cues in anchors.items():
    for row, cue in zip(data['scenes'][shot_id], cues):
        row['cue'] = cue
data['scenes']['s04'] = [
    {'asset': name, 'label': label, 'cue': cue, 'fraction': i / 5}
    for i, (name, label, cue) in enumerate([
        ('navigation-conversation', '会话 · 交代任务', None),
        ('navigation-memory', '记忆 · 管理资料', '记忆页'),
        ('navigation-devices', '设备 · 连接协作电脑', '设备页'),
        ('navigation-settings', '设置 · 管理授权', '设置页'),
        ('sdk-version', '银河麒麟 V11 · 系统能力接入', '软件运行在'),
    ])]
data['scenes']['s07'] = [
    {'asset':'bill-recall','label':'已保存的九月家庭账单','cue':None,'fraction':0},
    {'asset':'new-bill-actions','label':'新建会话，输入问题并发送','cue':'打开新会话','fraction':.62},
    {'asset':'new-bill-answer','label':'找回三项费用与合计','cue':'助手找回账单','fraction':.76},
]
data['scenes']['s08'] = [
    {'asset':'new-bill-answer','label':'合计 434.50 元','cue':None,'fraction':0},
    {'asset':'new-bill-source','label':'点击回答中的来源链接','cue':'沿着回答','fraction':.4},
    {'asset':'new-bill-source-detail','label':'账单原记录 · 合计 434.50 元','cue':'再逐项查看金额','fraction':.65},
]
data['scenes']['s15'][0]['asset'] = 'preferences'
data['scenes']['s15'][0]['label'] = '当前回答方式：详细说明 · 支持查看历史版本'
data['assets']['pair-verify']['result_asset'] = 'pair-result'
data['assets']['pair-verify']['result_from'] = 45
data['scenes']['s19'] = [
    {'asset':'device-controls','label':'查看参与协作的电脑','cue':None,'fraction':0},
    {'asset':'pair-open','label':'打开设备配对入口','cue':'在设备页','fraction':.28},
    {'asset':'pair-verify','label':'交换配对信息后，验证可信设备','cue':'双方交换','fraction':.42},
    {'asset':'device-controls','label':'在设备列表查看可信电脑','cue':'回到设备列表','fraction':.63},
]
data['scenes']['s17'] = [
    {'asset':'stage-open','label':'社区图书角 · 阶段记录','cue':None,'fraction':0},
    {'asset':'stage-save','label':'点击保存为长期记忆','cue':'选择长期保留','fraction':.78},
    {'asset':'stage-result','label':'长期知识检索结果 · 社区图书角','cue':'后续任务','fraction':.86},
]
data['scenes']['s24'].insert(1, {'asset':'forget-action','label':'核对目标后确认遗忘','cue':'再点击确认','fraction':.49})
data['scenes']['s26'] = [
    {'asset':'brief','label':'近期知识线索','cue':None,'fraction':0},
    {'asset':'brief-reading','label':'按日期查看采集汇总','cue':'再按日期','fraction':.5},
]
# Preserve the exact top-half insight crop already used by the approved bookends.
data['assets']['brief'] = {**data['assets']['outro-insight']}
for name in ['keyword-results', 'agent-tools-completed', 'behavior-demo-window', 'dreaming-review', 'stage-record', 'shared-settings', 'edit-version-two']:
    data['assets'][name]['native_pointer'] = True
data['direction'] = 'Narration-led framing; source-speed playback; guided reading on still photographs'
(ROOT / 'src/directed-scenes.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
print('Prepared native pointer excerpts and narration anchors')
