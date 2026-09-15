"""Reproduce full recording frames without cropping, scaling or UI alteration.

Live VM captures are retained as original PNGs and verified, not recreated.
"""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / 'submission/presentation-production/source/full-window-captures/manifest.json'

for entry in json.loads(MANIFEST.read_text()):
    target = ROOT / entry['image']
    if 'recording' in entry:
        recording = ROOT / entry['recording']
        assert hashlib.sha256(recording.read_bytes()).hexdigest() == entry['recording_sha256']
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', str(entry['second']),
                        '-i', str(recording), '-frames:v', '1', str(target)], check=True)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == entry['image_sha256'], target
print('Verified all original full-window captures.')
