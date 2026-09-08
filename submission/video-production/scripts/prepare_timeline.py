#!/usr/bin/env python3
"""Build frame-aligned Chinese captions from preserved speech word boundaries.

Only metadata whose text matches the current storyboard is selected. This is a
mechanical alignment draft; listening and picture inspection remain required.
"""
import html
import hashlib
import json
import math
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
story = json.loads((ROOT / 'storyboard/shots.json').read_text())
fps = story['fps']
start = 0
timeline = []
measurements = []
for shot in story['shots']:
    matches = []
    for path in (ROOT / 'raw/audio' / shot['id']).glob('*.json'):
        meta = json.loads(path.read_text())
        if meta['request']['text'] == shot['narration']:
            matches.append((path, meta))
    if len(matches) != 1:
        raise RuntimeError(shot['id'] + ': need one matching narration, got ' + str(len(matches)))
    path, meta = matches[0]
    if hashlib.sha256(path.with_suffix('.mp3').read_bytes()).hexdigest() != meta['audio_sha256']:
        raise RuntimeError(shot['id'] + ': audio checksum changed')
    words = []
    cursor = 0
    text = shot['narration']
    for boundary in meta['boundaries']:
        word = html.unescape(boundary['text'])
        at = text.find(word, cursor)
        if at < 0:
            raise RuntimeError(shot['id'] + ': unmatched speech token ' + word)
        words.append({**boundary, 'at': at, 'end': at + len(word)})
        cursor = at + len(word)
    captions = []
    for part in re.finditer(r'[^，。；！？]+[，。；！？]?', text):
        selected = [w for w in words if part.start() <= w['at'] < part.end()]
        if not selected:
            raise RuntimeError('Caption has no timing: ' + part.group())
        # Avoid long lines: split on the actual word boundary, never split a word.
        groups = [[]]
        for word in selected:
            if groups[-1] and word['end'] - groups[-1][0]['at'] > 24:
                groups.append([])
            groups[-1].append(word)
        for group in groups:
            first, last = group[0], group[-1]
            end = part.end() if last is selected[-1] else last['end']
            captions.append({'text': text[first['at']:end],
                             'from': 15 + math.floor(first['offset'] / 1e7 * fps),
                             'to': 15 + math.ceil((last['offset'] + last['duration']) / 1e7 * fps) + 3})
    for i in range(len(captions) - 1):
        captions[i]['to'] = min(captions[i]['to'], captions[i+1]['from'])
    duration = max(round(shot['planned_duration_seconds'] * fps),
                   math.ceil((meta['duration_seconds'] + 1.2) * fps))
    assert all(0 <= cue['from'] < cue['to'] <= duration for cue in captions)
    output = ROOT / 'public/audio' / (shot['id'] + '.mp3')
    shutil.copyfile(path.with_suffix('.mp3'), output)
    timeline.append({**shot, 'from': start, 'duration': duration,
                     'audio': 'audio/' + output.name, 'audio_from': 15,
                     'audio_source': str(path.with_suffix('.mp3').relative_to(ROOT)),
                     'captions': captions})
    measurements.append({'shot': shot['id'], 'seconds': meta['duration_seconds'],
                         'audio': str(path.with_suffix('.mp3').relative_to(ROOT))})
    start += duration
(ROOT / 'src/timeline.json').write_text(json.dumps({
    'status': '按语音时间生成，待逐段试听和画面校准', 'fps': fps,
    'duration': start, 'seconds': start / fps, 'shots': timeline,
}, ensure_ascii=False, indent=2) + '\n')
(ROOT / 'review/narration-durations.json').write_text(json.dumps({
    'count': len(measurements), 'total_seconds': sum(row['seconds'] for row in measurements),
    'status': '当前稿对应音频已核对摘要，未逐段试听校准', 'shots': measurements,
}, ensure_ascii=False, indent=2) + '\n')
print(f'{len(timeline)} 镜，{start/fps:.3f} 秒；字幕不重叠', flush=True)
