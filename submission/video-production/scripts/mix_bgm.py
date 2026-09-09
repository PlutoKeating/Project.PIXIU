#!/usr/bin/env python3
"""Mix configured music into an approved no-music export without reencoding pictures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--video', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
if args.output.exists() or args.report.exists():
    parser.error('Choose new output and report paths to preserve existing exports')
cfg = json.loads(Path('src/bgm.json').read_text())
timeline = json.loads(Path('src/timeline.json').read_text())
duration = timeline['duration'] / timeline['fps']
source = Path('public') / cfg['source']
stem = Path('public') / cfg['prepared']
start = cfg['source_start_seconds']
fade = cfg['fade_out_seconds']
assert 0 < fade <= duration and start >= 0 and 0 <= cfg['volume'] <= 1
length = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(source)]))
assert length >= start + duration, 'Music is shorter than the requested excerpt'
def ff(*items):
    return subprocess.check_output(['ffmpeg', '-v', 'error', '-nostdin', *map(str, items)])
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
# Stem contains trim and fade only. Both preview and export apply the gain once.
ff('-i', source, '-af', f'atrim=start={start}:duration={duration},asetpts=PTS-STARTPTS,aresample=48000,afade=t=out:st={duration-fade}:d={fade},atrim=end_sample={round(duration*48000)}', '-ac', 2, '-c:a', 'pcm_s16le', '-y', stem)
graph = f'[0:a]atrim=duration={duration},asetpts=PTS-STARTPTS[a];[1:a]volume={cfg["volume"]}[b];[a][b]amix=inputs=2:normalize=0:duration=longest,atrim=duration={duration}[mix]'
inputs = ['-i', args.video, '-i', stem, '-filter_complex', graph]
pcm = np.frombuffer(ff(*inputs, '-map', '[mix]', '-ar', 48000, '-ac', 2, '-f', 'f32le', '-'), dtype='<f4')
peak = float(np.max(np.abs(pcm)))
print(f'Linear mix peak: {20*np.log10(peak):.3f} dBFS', flush=True)
assert peak < 1, 'Exact requested mix clips; no automatic gain change applied'
del pcm
ff(*inputs, '-map', '0:v:0', '-map', '[mix]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '320k', '-ar', 48000, '-t', duration, '-movflags', '+faststart', args.output)
ff('-i', args.output, '-f', 'null', '-')
def picture_hash(path):
    return ff('-i', path, '-map', '0:v:0', '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-').decode().strip()
original_picture = picture_hash(args.video)
assert picture_hash(args.output) == original_picture
encoded = np.frombuffer(ff('-i', args.output, '-vn', '-ar', 48000, '-ac', 2, '-f', 'f32le', '-'), dtype='<f4')
encoded_peak = float(np.max(np.abs(encoded)))
assert encoded_peak < 1, 'Encoded audio exceeds full scale'
report = {'sha256': sha(args.output), 'complete_decode': 'passed', 'source_video': str(args.video), 'source_video_sha256': sha(args.video), 'source_music_sha256': sha(source), 'stem_sha256': sha(stem), 'settings': cfg, 'duration_seconds': duration, 'mix_peak_dbfs': float(20*np.log10(peak)), 'encoded_peak_dbfs': float(20*np.log10(encoded_peak)), 'picture_bitstream_unchanged': True, 'video_bitstream_hash': original_picture, 'method': f'{start}s source trim; {cfg["volume"]*100:g}% linear gain; last {fade}s linear fade on music only; picture stream copied; no normalization or ducking.'}
args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(report, ensure_ascii=False), flush=True)
