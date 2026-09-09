#!/usr/bin/env python3
"""Check voice provenance, approved text, subtitles and frame-aligned cut breaths."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--approved-commit', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
settings = json.loads((ROOT/'storyboard/narration.json').read_text())
story = json.loads((ROOT/'storyboard/shots.json').read_text())
approved = json.loads(subprocess.check_output(['git', 'show', f'{args.approved_commit}:submission/video-production/storyboard/shots.json'], cwd=ROOT))
assert story == approved, 'Approved storyboard changed'
timeline = json.loads((ROOT/'src/timeline.json').read_text())
assert len(timeline['shots']) == len(story['shots'])
rows = []
cursor = 0
for shot, original in zip(timeline['shots'], story['shots']):
    assert all(shot[k] == v for k,v in original.items())
    assert shot['from'] == cursor
    cursor += shot['duration']
    source = ROOT / shot['audio_source']
    meta = json.loads(source.with_suffix('.json').read_text())
    assert meta['request']['text'] == shot['narration']
    assert all(meta['request'].get(k) == v for k,v in settings.items())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == meta['audio_sha256']
    assert (ROOT/'public'/shot['audio']).read_bytes() == source.read_bytes()
    assert ''.join(c['text'] for c in shot['captions']) == shot['narration']
    assert shot['tail_frames'] == (15 if shot['id'] in ('s01','s30') else 8)
    assert shot['captions'][-1]['to'] == shot['duration']
    assert all(a['to'] <= b['from'] for a,b in zip(shot['captions'],shot['captions'][1:]))
    rows.append({'shot': shot['id'], 'audio_sha256': digest, 'duration_frames': shot['duration'],
                 'tail_frames': shot['tail_frames'], 'words': len(meta['boundaries'])})
assert cursor == timeline['duration']
args.output.write_text(json.dumps({'approved_commit':args.approved_commit,'storyboard_unchanged':True,
    'narration':settings,'shots':rows,'duration_seconds':cursor/timeline['fps'],
    'result':'passed; metadata and timeline verification, not listening'},ensure_ascii=False,indent=2)+'\n')
print('PASS',len(rows),'shots; approved text, voice, hashes, captions and cut breaths')
