#!/usr/bin/env python3
"""Build the editable roadshow candidate and mirror it to the maintained asset."""
from pathlib import Path
import hashlib
import json
import runpy
import shutil

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'submission/presentation-production'

def build():
    runpy.run_path(str(WORK / 'scripts/build_deck.py'), run_name='__main__')
    manifest = json.loads((WORK / 'review/build-manifest.json').read_text())
    candidate = ROOT / manifest['output']['path']
    target = ROOT / 'docs/delivery/assets/项目报告.pptx'
    shutil.copyfile(candidate, target)
    manifest['output'] = {'path': target.relative_to(ROOT).as_posix(),
                          'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    (target.parent / 'presentation-manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print('34页宣传片对齐路演稿已生成；替换正式提交材料前须完成整页渲染复核。')

if __name__ == '__main__':
    build()
