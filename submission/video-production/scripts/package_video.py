#!/usr/bin/env python3
"""Place one verified video in the frozen submission layout, preserving other works."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--video', type=Path, required=True)
parser.add_argument('--technical', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'build/release/scripts'))
from submission_layout import paths, validate

if args.report.exists():
    parser.error('Preserve previous packaging report; choose a new path')
video = args.video.resolve()
digest = hashlib.sha256(video.read_bytes()).hexdigest()
technical = json.loads(args.technical.read_text())
if technical['sha256'] != digest or technical['complete_decode'] != 'passed':
    raise RuntimeError('Video does not match its successful complete-decode report')
duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
    'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(video)]))
if not 300 <= duration <= 600:
    raise RuntimeError('Video must be between five and ten minutes')
validate(root)
outer, materials, _ = paths(root)
archive_path = materials / '演示视频.zip'
if archive_path.exists():
    raise RuntimeError('Submission video already exists; do not overwrite reviewed work')
others = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in outer.rglob('*') if p.is_file()}
# Video is already compressed. Store it once, without additional files or folders.
with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_STORED) as archive:
    archive.write(video, '演示视频.mp4')
validate(root, require_video=True)
with zipfile.ZipFile(archive_path) as archive:
    assert archive.namelist() == ['演示视频.mp4'] and archive.testzip() is None
    assert hashlib.sha256(archive.read('演示视频.mp4')).hexdigest() == digest
assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == before
           for name, before in others.items())
report = {'archive': str(archive_path.relative_to(root)), 'bytes': archive_path.stat().st_size,
          'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
          'member': '演示视频.mp4', 'video_sha256': digest, 'duration_seconds': duration,
          'crc_and_member_digest': 'passed', 'frozen_layout': 'passed',
          'other_submission_files_unchanged': True,
          'boundary': 'Packaging and technical verification only; actual listening review remains pending.'}
args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
