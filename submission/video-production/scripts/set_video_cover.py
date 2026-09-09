#!/usr/bin/env python3
"""Replace frame zero and embed an MP4 cover; preserve audio and later GOPs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--video', type=Path, required=True)
p.add_argument('--cover', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
p.add_argument('--verify-only', action='store_true')
a = p.parse_args()
def ff(*args):
    return subprocess.check_output(['ffmpeg', '-v', 'error', '-nostdin', *map(str, args)])
def probe(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
source = probe(a.video)
v = source['streams'][0]
assert v['r_frame_rate'] == '30/1' and v['codec_name'] == 'h264'
# The first subsequent keyframe bounds the only GOP that needs encoding.
keys = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_packets', '-show_entries', 'packet=pts_time,flags', '-of', 'json', str(a.video)]))['packets']
cut = next(float(x['pts_time']) for x in keys if 'K' in x['flags'] and float(x['pts_time']) > 0)
frames = round(cut * 30)
if not a.verify_only:
    assert not a.output.exists() and not a.report.exists()
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        head, tail = root/'head.mp4', root/'tail.mp4'
        graph = f'[1:v]scale={v["width"]}:{v["height"]}:flags=lanczos,setsar=1,format=yuvj420p,setpts=PTS-STARTPTS[c];[0:v]trim=start_frame=1:end_frame={frames},setpts=PTS-STARTPTS[r];[c][r]concat=n=2:v=1:a=0[v]'
        ff('-i', a.video, '-framerate', 30, '-i', a.cover, '-filter_complex', graph, '-map', '[v]', '-an', '-c:v', 'libx264', '-crf', 18, '-preset', 'medium', '-pix_fmt', 'yuvj420p', '-video_track_timescale', 90000, '-frames:v', frames, head)
        ff('-ss', cut, '-i', a.video, '-map', '0:v:0', '-an', '-c', 'copy', tail)
        listing = root/'concat.txt'
        listing.write_text("file 'head.mp4'\nfile 'tail.mp4'\n")
        ff('-f', 'concat', '-safe', 0, '-i', listing, '-i', a.video, '-i', a.cover, '-map', '0:v:0', '-map', '1:a:0', '-map', '2:v:0', '-c', 'copy', '-disposition:v:1', 'attached_pic', '-movflags', '+faststart', a.output)
result = probe(a.output)
assert result['streams'][0]['nb_frames'] == v['nb_frames']
assert result['format']['duration'] == source['format']['duration']
assert result['streams'][2]['disposition']['attached_pic'] == 1
assert ff('-i', a.output, '-map', '0:v:1', '-c', 'copy', '-f', 'image2pipe', '-') == a.cover.read_bytes()
def audio_hash(path):
    return ff('-i', path, '-map', '0:a:0', '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-').decode().strip()
assert audio_hash(a.video) == audio_hash(a.output)
def frame_hashes(path):
    data = ff('-i', path, '-map', '0:v:0', '-f', 'framemd5', '-').decode()
    return [line.split(',')[-1].strip() for line in data.splitlines() if not line.startswith('#')]
with ThreadPoolExecutor(2) as pool:
    original, updated = list(pool.map(frame_hashes, [a.video, a.output]))
assert len(original) == len(updated) == int(v['nb_frames'])
assert original[frames:] == updated[frames:], 'Decoded pictures after the first GOP must be identical'
ff('-i', a.output, '-f', 'null', '-')
report = {'sha256': sha(a.output), 'complete_decode': 'passed', 'source_sha256': sha(a.video), 'cover_sha256': sha(a.cover), 'duration_seconds': float(result['format']['duration']), 'frames': len(updated), 'audio_bitstream_identical': True, 'embedded_cover_identical': True, 'copied_video_from_frame': frames, 'later_decoded_frames_identical': True, 'method': 'Replace frame zero with supplied cover; encode first GOP only; copy remaining GOPs and entire audio; embed original PNG as attached cover.'}
a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(report, ensure_ascii=False))
