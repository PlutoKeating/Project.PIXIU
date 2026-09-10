#!/usr/bin/env python3
"""Place one verified video in the frozen submission layout, preserving other works."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
import subprocess
import sys
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--video', type=Path, required=True)
parser.add_argument('--technical', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
parser.add_argument('--previous-sha256', help='Expected digest of the archive being replaced')
parser.add_argument('--archive-previous', type=Path, help='New path preserving the previous archive')
args = parser.parse_args()
if bool(args.previous_sha256) != bool(args.archive_previous):
    parser.error('Replacement requires both previous digest and preservation path')
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
previous = None
if archive_path.exists():
    previous = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if previous != args.previous_sha256 or not args.archive_previous:
        raise RuntimeError('Replacement requires the exact previous archive digest and a preservation path')
    if args.archive_previous.exists() or args.archive_previous.resolve().is_relative_to(outer):
        raise RuntimeError('Preserve previous archive at a new path outside the formal submission')
    with args.archive_previous.open('xb') as backup, archive_path.open('rb') as original:
        shutil.copyfileobj(original, backup)
    assert hashlib.sha256(args.archive_previous.read_bytes()).hexdigest() == previous
elif args.previous_sha256:
    raise RuntimeError('Expected previous archive is missing')
others = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in outer.rglob('*') if p.is_file() and p != archive_path}
# Video is already compressed. Store it once, without additional files or folders.
staged = args.report.with_suffix('.zip')
with zipfile.ZipFile(staged, 'x', compression=zipfile.ZIP_STORED) as archive:
    archive.write(video, '演示视频.mp4')
if staged.stat().st_size > 200_000_000:
    raise RuntimeError('Archive exceeds 200 MB')
with zipfile.ZipFile(staged) as archive:
    assert archive.namelist() == ['演示视频.mp4'] and archive.testzip() is None
    assert hashlib.sha256(archive.read('演示视频.mp4')).hexdigest() == digest
assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == before
           for name, before in others.items())
staged.replace(archive_path)
validate(root, require_video=True)
report = {'previous_archive_sha256': previous, 'archive': str(archive_path.relative_to(root)), 'bytes': archive_path.stat().st_size,
          'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
          'member': '演示视频.mp4', 'video_sha256': digest, 'duration_seconds': duration,
          'crc_and_member_digest': 'passed', 'frozen_layout': 'passed',
          'other_submission_files_unchanged': True,
          'verification_scope': 'Archive CRC, member digest, format, duration and frozen submission layout.'}
args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
