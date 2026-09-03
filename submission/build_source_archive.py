#!/usr/bin/env python3
"""Build the complete, deterministic D-03 source archive with submodules."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Iterable


ARCHIVE_PREFIX = "Project.PIXIU-source"


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(root), *args], stderr=subprocess.STDOUT
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tracked_paths(root: Path) -> list[Path]:
    raw = git(root, "ls-files", "--recurse-submodules", "-z")
    paths = [Path(value.decode("utf-8")) for value in raw.split(b"\0") if value]
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("tracked source list is empty or contains duplicates")
    for relative in paths:
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("tracked source path escapes repository")
        path = root / relative
        if not path.is_file() and not path.is_symlink():
            raise ValueError(f"tracked source is unavailable: {relative.as_posix()}")
    return sorted(paths, key=lambda item: item.as_posix())


def submodule_commits(root: Path) -> dict[str, str]:
    lines = git(root, "submodule", "status", "--recursive").decode().splitlines()
    result: dict[str, str] = {}
    for line in lines:
        if not line or line[0] in "-+U":
            raise ValueError("all submodules must be initialized at clean gitlinks")
        fields = line[1:].split()
        if len(fields) < 2:
            raise ValueError("cannot parse submodule status")
        result[fields[1]] = fields[0]
    if not result:
        raise ValueError("source archive requires initialized submodules")
    return dict(sorted(result.items()))


def source_manifest(
    root: Path, paths: Iterable[Path], evidence_dir: Path, epoch: int
) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for relative in paths:
        path = root / relative
        if path.is_symlink():
            target = os.readlink(path)
            digest = sha256_bytes(target.encode("utf-8"))
            kind = "symlink"
        else:
            digest = sha256_file(path)
            kind = "file"
        files.append(
            {
                "path": relative.as_posix(),
                "type": kind,
                "sha256": digest,
            }
        )
    evidence = [
        {
            "path": path.relative_to(evidence_dir).as_posix(),
            "sha256": sha256_file(path),
        }
        for path in sorted(evidence_dir.rglob("*"))
        if path.is_file() and not path.is_symlink()
    ]
    return {
        "schema_version": 1,
        "archive_prefix": ARCHIVE_PREFIX,
        "release_commit": git(root, "rev-parse", "HEAD").decode().strip(),
        "source_date_epoch": epoch,
        "submodules": submodule_commits(root),
        "tracked_files": files,
        "agent_supply_chain_evidence": evidence,
    }


def tar_info(name: str, size: int, mode: int, epoch: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mode = mode
    info.mtime = epoch
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    return info


def add_bytes(archive: tarfile.TarFile, name: str, value: bytes, mode: int, epoch: int) -> None:
    import io

    archive.addfile(tar_info(name, len(value), mode, epoch), io.BytesIO(value))


def create_archive(
    root: Path, output: Path, evidence_dir: Path, paths: list[Path], epoch: int
) -> dict[str, Any]:
    if output.exists():
        raise ValueError("refusing to overwrite an existing source archive")
    manifest = source_manifest(root, paths, evidence_dir, epoch)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".pixiu-source-", suffix=".tar.gz", dir=output.parent
    )
    os.close(descriptor)
    temporary_output = Path(temporary_name)
    try:
        with temporary_output.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=epoch) as compressed:
                with tarfile.open(fileobj=compressed, mode="w") as archive:
                    for relative in paths:
                        path = root / relative
                        name = f"{ARCHIVE_PREFIX}/{relative.as_posix()}"
                        if path.is_symlink():
                            info = tar_info(name, 0, 0o777, epoch)
                            info.type = tarfile.SYMTYPE
                            info.linkname = os.readlink(path)
                            archive.addfile(info)
                        else:
                            mode = 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644
                            with path.open("rb") as stream:
                                archive.addfile(
                                    tar_info(name, path.stat().st_size, mode, epoch), stream
                                )
                    for path in sorted(evidence_dir.rglob("*")):
                        if path.is_symlink():
                            raise ValueError("Agent evidence must not contain symlinks")
                        if path.is_file():
                            relative = path.relative_to(evidence_dir).as_posix()
                            with path.open("rb") as stream:
                                archive.addfile(
                                    tar_info(
                                        f"{ARCHIVE_PREFIX}/release-evidence/agent-supply-chain/{relative}",
                                        path.stat().st_size,
                                        0o644,
                                        epoch,
                                    ),
                                    stream,
                                )
                    rendered = (
                        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode()
                        + b"\n"
                    )
                    add_bytes(
                        archive,
                        f"{ARCHIVE_PREFIX}/SOURCE_MANIFEST.json",
                        rendered,
                        0o644,
                        epoch,
                    )
        os.link(temporary_output, output)
    finally:
        temporary_output.unlink(missing_ok=True)
    return manifest


def require_ready(root: Path, evidence_dir: Path) -> None:
    if git(root, "status", "--porcelain"):
        raise ValueError("Git worktree must be clean before source archiving")
    subprocess.run(
        [str(root / "build/release/scripts/verify-governance.sh")],
        cwd=root,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    with tempfile.TemporaryDirectory() as temporary:
        report_path = Path(temporary) / "audit.json"
        result = subprocess.run(
            [
                "python3",
                str(root / "build/release/scripts/audit-agent-supply-chain.py"),
                "--root",
                str(root),
                "--evidence-dir",
                str(evidence_dir),
                "--output",
                str(report_path),
                "--require-ready",
            ],
            check=False,
        )
        if result.returncode != 0:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            raise ValueError(
                "Agent supply chain is not ready: " + ", ".join(report.get("blockers", []))
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, evidence_dir, output = args.root.resolve(), args.evidence_dir.resolve(), args.output.resolve()
    try:
        require_ready(root, evidence_dir)
        epoch = int(git(root, "show", "-s", "--format=%ct", "HEAD").decode().strip())
        create_archive(root, output, evidence_dir, tracked_paths(root), epoch)
    except (json.JSONDecodeError, OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"source-archive: {exc}", file=sys.stderr)
        return 1
    print(f"source-archive: created {output} ({sha256_file(output)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
