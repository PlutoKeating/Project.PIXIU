"""Exclude development artifacts from both Runtime builds and source delivery."""
from pathlib import Path, PurePosixPath
import sys


def retained(name: str) -> bool:
    parts = PurePosixPath(name).parts
    if any(p in {'.git', '.github', '.gitlab', 'website', 'tests', 'test',
                 '__pycache__', '.pytest_cache', '.curator_backups', 'node_modules'} for p in parts):
        return False
    if parts[-1] in {'.gitignore', '.gitkeep', '.curator_state', '.usage.json', '.usage.json.lock'}:
        return False
    if parts[0] == 'plugins' and 'docs' in parts:
        return False
    return True


def prune(root: Path) -> None:
    for path in sorted(root.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        if not retained(path.relative_to(root).as_posix()):
            if path.is_dir() and not path.is_symlink():
                path.rmdir()
            else:
                path.unlink()


if __name__ == '__main__':
    prune(Path(sys.argv[1]))
