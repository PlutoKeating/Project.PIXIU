#!/usr/bin/env python3
"""Verify a rendered promo, preserving technical results and sampled image evidence."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np
from measure_audio_sync import RATE, decode, measure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    args.output.mkdir(exist_ok=False, parents=True)
    frames = args.output / 'frames'
    frames.mkdir()
    timeline = json.loads(Path('src/timeline.json').read_text())
    snapshot = json.loads(args.snapshot.read_text())
    assert all(hashlib.sha256(Path(f['path']).read_bytes()).hexdigest() == f['sha256']
               for f in snapshot['files']), 'Rendering sources changed since snapshot'
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(args.video), '-f', 'null', '-'], check=True)
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format',
                                              '-show_streams', '-of', 'json', str(args.video)]))
    audio = decode(args.video)
    correlations = []
    for shot in timeline['shots']:
        # Final file intentionally trims source silence. Correlate an initial phrase.
        source = decode(Path('public') / shot['audio'])
        source = source[:round(min(5, (shot['duration'] - 13) / 30 - .1) * RATE)]
        row = measure(audio, source, shot['from'] + 13)
        row.update(shot=shot['id'], target_start_frame=shot['from'] + shot['audio_from'])
        row['target_error_frames'] = row['measured_start_frame'] - row['target_start_frame']
        correlations.append(row)
    native = np.frombuffer(subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(args.video),
                                                   '-vn', '-f', 'f32le', '-']), dtype='<f4')
    report = {'sha256': hashlib.sha256(args.video.read_bytes()).hexdigest(),
              'complete_decode': 'passed', 'bytes': args.video.stat().st_size,
              'source_snapshot': 'matched', 'probe': probe, 'shots': len(timeline['shots']),
              'timeline_seconds': timeline['seconds'],
              'maximum_tail_frames': max(s['tail_frames'] for s in timeline['shots']),
              'all_last_captions_reach_cut': all(s['captions'][-1]['to'] == s['duration']
                                               for s in timeline['shots']),
              'peak_dbfs': float(20 * np.log10(max(1e-12, np.max(np.abs(native))))),
              'audio_probes': correlations, 'numpy_version': np.__version__,
              'method': 'Full decode, first-phrase waveform correlation and sampled OCR; not listening.'}
    assert report['peak_dbfs'] < 0 and report['all_last_captions_reach_cut']
    assert all(abs(r['target_error_frames']) < 1 for r in correlations)
    (args.output / 'technical.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(args.video), '-vf', 'fps=1/2',
                    '-q:v', '3', str(frames / 'sample-%03d.jpg')], check=True)
    for shot in timeline['shots']:
        for label, local in [('middle', shot['duration'] // 2), ('tail', shot['duration'] - 12)]:
            subprocess.run(['ffmpeg', '-v', 'error', '-ss', str((shot['from'] + local) / 30),
                            '-i', str(args.video), '-frames:v', '1', '-q:v', '2',
                            str(frames / f"{shot['id']}-{label}.jpg")], check=True)
    def ocr(path):
        result = subprocess.run(['tesseract', str(path), 'stdout', '-l', 'chi_sim+eng', '--psm', '11'],
                                capture_output=True, text=True, check=True,
                                env=os.environ | {'OMP_THREAD_LIMIT': '1'})
        return {'file': path.name, 'text': result.stdout}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(ocr, sorted(frames.glob('*.jpg'))))
    words = ['尚未', '不代表', '不承诺', '不等于', '不是', '不证明', '不表示', '不保证',
             '缺陷', '未实现', '物理删除', '物理擦除', '验收']
    hits = [r for r in records if any(w in ''.join(r['text'].split()) for w in words)]
    (args.output / 'ocr.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
    (args.output / 'ocr-hits.json').write_text(json.dumps(hits, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'video_sha256': report['sha256'], 'ocr_samples': len(records),
                      'ocr_hits_requiring_review': len(hits)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
