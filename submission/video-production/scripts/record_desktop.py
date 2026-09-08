#!/usr/bin/env python3
"""Record actual libvirt pixels with measured frame times (default four fps).

Keeps every original PNG and timing manifest. Encoding duplicates those frames
to 30 fps; it does not invent animation or change the elapsed action duration.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--domain', required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--seconds', type=float, required=True)
parser.add_argument('--fps', type=float, default=4)
args = parser.parse_args()
if args.seconds <= 0 or not 0 < args.fps <= 15:
    parser.error('Positive duration and frame rate up to 15 required')
args.output.mkdir(parents=True, exist_ok=False)
start = time.monotonic()
frames = []
while time.monotonic() - start < args.seconds:
    name = f'{len(frames):05d}.png'
    before = time.monotonic() - start
    subprocess.run(['virsh', 'screenshot', args.domain, str(args.output / name)],
                   check=True, stdout=subprocess.DEVNULL)
    after = time.monotonic() - start
    frames.append({'file': name, 'started_seconds': before, 'finished_seconds': after})
    time.sleep(max(0, len(frames) / args.fps - (time.monotonic() - start)))
elapsed = time.monotonic() - start
(args.output / 'timing.json').write_text(json.dumps({
    'capture': '真实虚拟机像素；采样时刻范围已记录，编码为每秒三十帧',
    'elapsed_seconds': elapsed, 'requested_fps': args.fps, 'frames': frames,
}, ensure_ascii=False, indent=2) + '\n')
concat = []
for i, frame in enumerate(frames):
    next_time = frames[i+1]['started_seconds'] if i+1 < len(frames) else elapsed
    concat += ["file '" + frame['file'] + "'", f"duration {next_time-frame['started_seconds']:.6f}"]
concat.append("file '" + frames[-1]['file'] + "'")
(args.output / 'frames.ffconcat').write_text('\n'.join(concat) + '\n')
subprocess.run(['ffmpeg', '-v', 'error', '-n', '-f', 'concat', '-safe', '1',
                '-i', str(args.output / 'frames.ffconcat'), '-t', str(elapsed),
                '-vf', 'fps=30', '-c:v', 'libx264', '-crf', '18',
                '-pix_fmt', 'yuv420p', str(args.output / '原始录屏.mp4')], check=True)
print(f'已保存 {len(frames)} 帧，实际 {elapsed:.3f} 秒', flush=True)
