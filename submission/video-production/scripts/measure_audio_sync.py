#!/usr/bin/env python3
"""Measure source-to-render lag by normalized correlation, not listening."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np

RATE = 48000
FPS = 30


def decode(path):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path),
                                   '-vn', '-ac', '1', '-ar', str(RATE), '-f', 'f32le', '-'])
    return np.frombuffer(raw, dtype='<f4').astype(np.float64)


def measure(render, source, expected_frame):
    expected = round(expected_frame * RATE / FPS)
    lower = max(0, expected - RATE // 5)
    upper = min(len(render) - len(source), expected + RATE // 5)
    if upper < lower:
        raise ValueError('Source is not fully present in rendered audio')
    window = render[lower:upper + len(source)]
    size = 1 << (len(window) + len(source) - 2).bit_length()
    corr = np.fft.irfft(np.fft.rfft(window, size) *
                       np.conj(np.fft.rfft(source, size)), size)[:upper - lower + 1]
    energy = np.concatenate(([0.0], np.cumsum(window * window)))
    local_energy = energy[len(source):] - energy[:-len(source)]
    norm = corr / np.sqrt(np.maximum(1e-20, local_energy * np.sum(source * source)))
    best = int(np.argmax(norm))
    found = lower + best
    hop = RATE // 100
    complete = source[:len(source) // hop * hop].reshape(-1, hop)
    peak = int(np.argmax(np.mean(complete * complete, axis=1))) * hop + hop / 2
    return {'declared_start_frame': expected_frame,
            'measured_start_frame': found * FPS / RATE,
            'pipeline_offset_frames': (found - expected) * FPS / RATE,
            'normalized_correlation': float(norm[best]),
            'source_peak_frame': peak * FPS / RATE}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--probe', action='append', nargs=2, metavar=('SOURCE', 'START_FRAME'), required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; preserve previous measurements')
    rendered = decode(args.video)
    results = []
    for path, frame in args.probe:
        source = Path(path)
        result = measure(rendered, decode(source), float(frame))
        result.update(source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        results.append(result)
    report = {'method': 'normalized waveform correlation; not a listening review',
              'rate': RATE, 'fps': FPS, 'numpy': np.__version__,
              'video': str(args.video), 'video_sha256': hashlib.sha256(args.video.read_bytes()).hexdigest(),
              'peak_dbfs': float(20 * np.log10(max(1e-12, np.max(np.abs(rendered))))),
              'probes': results}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
