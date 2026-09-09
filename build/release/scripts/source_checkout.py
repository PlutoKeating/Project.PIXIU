#!/usr/bin/env python3
"""Read pinned upstream sources from either Git or a delivered source snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def snapshot(root: Path) -> dict:
    return json.loads((root / 'SOURCE-MANIFEST.json').read_text())


def check(root: Path, relative: str, expected: str) -> None:
    source = root / relative
    if (source / '.git').exists():
        actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'])
        if actual != expected or dirty:
            raise ValueError(f'Upstream must be clean and pinned: {relative}')
        return
    manifest = snapshot(root)
    if manifest['submodules'].get(relative) != expected:
        raise ValueError(f'Unexpected upstream snapshot: {relative}')
    entries = [e for e in manifest['files'] if e['path'].startswith(relative + '/')]
    if not entries:
        raise ValueError(f'Empty upstream snapshot: {relative}')
    for entry in entries:
        path = root / entry['path']
        data = path.readlink().as_posix().encode() if path.is_symlink() else path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError(f'Source digest mismatch: {entry["path"]}')


def export(root: Path, relative: str, expected: str, destination: Path) -> None:
    check(root, relative, expected)
    if any(destination.iterdir()):
        raise ValueError('Source destination must be empty')
    source = root / relative
    if (source / '.git').exists():
        with subprocess.Popen(['git', '-C', str(source), 'archive', '--format=tar', 'HEAD'], stdout=subprocess.PIPE) as archive:
            subprocess.run(['tar', '-xf', '-', '-C', str(destination)], stdin=archive.stdout, check=True)
            if archive.wait():
                raise ValueError('Cannot export upstream')
    else:
        # Copy only manifest entries; do not pick up local caches or generated files.
        for entry in snapshot(root)['files']:
            if not entry['path'].startswith(relative + '/'):
                continue
            original = root / entry['path']
            target = destination / Path(entry['path']).relative_to(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            if entry['mode'] == '120000':
                target.symlink_to(original.readlink())
            else:
                shutil.copyfile(original, target)
                target.chmod(0o755 if entry['mode'] == '100755' else 0o644)


def epoch(root: Path, relative: str) -> int:
    source = root / relative
    if (source / '.git').exists():
        return int(subprocess.check_output(['git', '-C', str(source), 'show', '-s', '--format=%ct', 'HEAD']))
    return int(snapshot(root)['submoduleEpochs'][relative])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'export', 'epoch'])
    parser.add_argument('root', type=Path)
    parser.add_argument('relative')
    parser.add_argument('expected', nargs='?')
    parser.add_argument('destination', type=Path, nargs='?')
    args = parser.parse_args()
    if args.action == 'epoch':
        print(epoch(args.root, args.relative))
    elif args.action == 'check':
        check(args.root, args.relative, args.expected)
    else:
        export(args.root, args.relative, args.expected, args.destination)


if __name__ == '__main__':
    main()
