#!/usr/bin/env python3
"""Verify fixed bookends, original captions, voice rates and render source hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--reference', default='49e463c')
p.add_argument('--snapshot', required=True, type=Path)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def original(path):
    return subprocess.check_output(['git', 'show', a.reference + ':submission/video-production/' + path], cwd=ROOT)

def matches(path):
    value = original(path)
    if value.startswith(b'version https://git-lfs.github.com/spec/v1'):
        expected = next(line.split(b'sha256:')[1].decode() for line in value.splitlines() if line.startswith(b'oid '))
        return digest(ROOT / path) == expected
    return (ROOT / path).read_bytes() == value

timeline = json.loads((ROOT / 'src/timeline.json').read_text())
prior = json.loads(original('src/timeline.json'))
scenes = json.loads((ROOT / 'src/directed-scenes.json').read_text())
files = ['src/SceneOutro.tsx', 'src/brandCopy.ts', 'src/NarratedChapter.tsx']
files += [str(f.relative_to(ROOT)) for f in (ROOT / 'public/current').glob('outro-*.png')]
assert all(matches(f) for f in files)
rows = []
for shot in timeline['shots']:
    assert ''.join(c['text'] for c in shot['captions']) == shot['narration']
    source = ROOT / shot['audio_source']
    meta = json.loads(source.with_suffix('.json').read_text())
    assert digest(source) == meta['audio_sha256']
    assert meta['request']['text'] == shot['narration']
    if shot['id'] in ('s01', 's30'):
        old = next(s for s in prior['shots'] if s['id'] == shot['id'])
        assert all(shot[k] == old[k] for k in ['narration', 'duration', 'audio', 'audio_source', 'captions'])
        assert matches(shot['audio_source'])
    else:
        assert meta['request']['rate'] == '0%'
    anchors = []
    for row in scenes['scenes'].get(shot['id'], []):
        anchor = 0 if row['cue'] is None else next(c['from'] for c in shot['captions'] if c['text'].startswith(row['cue']))
        anchors.append(anchor)
    assert all(x < y for x, y in zip(anchors, anchors[1:]))
    rows.append({'shot': shot['id'], 'rate': meta['request']['rate'],
                 'audio_sha256': digest(source), 'duration_frames': shot['duration'], 'visual_anchors': anchors})
report = {'reference_commit': a.reference, 'identical_files': files, 'shots': rows,
          'caption_text_matches_narration': True,
          'cover_sha256': digest(ROOT / 'raw/cover/approved-cover.png'), 'result': 'passed'}
a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
paths = sorted(f for directory in ['src', 'storyboard', 'public'] for f in (ROOT / directory).rglob('*') if f.is_file())
a.snapshot.write_text(json.dumps({'files': [{'path': str(f.relative_to(ROOT)), 'sha256': digest(f)} for f in paths]}, indent=2) + '\n')
print('PASS: fixed bookends, original caption component, 28 original-speed voices and', len(paths), 'source hashes')
