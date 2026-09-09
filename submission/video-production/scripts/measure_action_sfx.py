#!/usr/bin/env python3
"""Measure new action sounds against the preceding render with unchanged narration."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from measure_audio_sync import RATE, FPS, decode, measure

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--video', type=Path, required=True)
parser.add_argument('--baseline', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    parser.error('Preserve previous results; choose a new output')
root = Path(__file__).resolve().parents[1]
timeline = json.loads((root / 'src/timeline.json').read_text())
shots = {s['id']: s for s in timeline['shots']}
history = next(c['from'] for c in shots['s15']['captions'] if c['text'].startswith('提取后查看'))
assets = json.loads((root / 'review/action-sfx-assets-01.json').read_text())['assets']
peaks = {Path(a['action']).stem: a['peak_frame'] for a in assets}
cues = [('s13', t, 'typewriter-hit-' + ('soft' if i % 2 else 'hard') + '-action')
        for i, t in enumerate([10, 13, 16, 19])]
cues += [('s13', 350, 'switch-click-quick-action')]
cues += [('s15', history + t, 'paper-slide-action') for t in [28, 40, 52]]
cues += [('s26', t, 'typewriter-hit-' + ('soft' if i else 'hard') + '-action')
         for i, t in enumerate([6, 9.5])]
render = decode(args.video)
baseline = decode(args.baseline)
if len(render) != len(baseline):
    raise RuntimeError('Baseline and candidate audio lengths differ; inspect alignment first')
difference = render - baseline
results = []
for shot, target, name in cues:
    source = root / 'public/audio' / (name + '.wav')
    data = decode(source)
    peak = peaks[name]
    sequence = max(0, math.floor(target - peak - 1.28 + 0.5))
    expected = shots[shot]['from'] + sequence + 1.28
    # Restrict search to +/-2 frames to avoid selecting the next repeated key.
    lower = max(0, round((expected - 2) * RATE / FPS))
    upper = min(len(render), round((expected + 2) * RATE / FPS) + len(data))
    estimates = {}
    for label, track in [('mixed', render), ('candidate_minus_baseline', difference)]:
        found = measure(track[lower:upper], data, expected - lower * FPS / RATE)
        start = found['measured_start_frame'] + lower * FPS / RATE
        estimates[label] = {'source_start_frame': start,
                            'peak_frame': start + peak,
                            'target_error_frames': start + peak - shots[shot]['from'] - target,
                            'correlation': found['normalized_correlation']}
    results.append({'shot': shot, 'target_frame': shots[shot]['from'] + target,
                    'source': str(source.relative_to(root)), 'estimates': estimates})
args.output.write_text(json.dumps({
    'method': 'Waveform correlation in +/-2-frame window; decoded candidate minus previous render isolates added sounds approximately. Not listening or proof of perceptual audibility.',
    'video': str(args.video), 'video_sha256': hashlib.sha256(args.video.read_bytes()).hexdigest(),
    'baseline': str(args.baseline), 'baseline_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
    'probes': results,
}, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(results, ensure_ascii=False, indent=2))
