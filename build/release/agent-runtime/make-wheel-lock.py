#!/usr/bin/env python3
"""Create a deterministic hash-locked requirements file from a wheelhouse."""

from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from pathlib import Path


FIELD = re.compile(r"^([^:]+):\s*(.*)$")


def wheel_identity(path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(path) as archive:
        metadata_files = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_files) != 1:
            raise ValueError(f"{path.name}: expected exactly one METADATA file")
        fields: dict[str, str] = {}
        for line in archive.read(metadata_files[0]).decode("utf-8").splitlines():
            match = FIELD.match(line)
            if match:
                fields.setdefault(match.group(1), match.group(2))
    name = fields.get("Name", "").strip().lower().replace("_", "-")
    version = fields.get("Version", "").strip()
    if not name or not version:
        raise ValueError(f"{path.name}: package identity missing")
    return name, version


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheelhouse", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    packages: dict[str, tuple[str, str]] = {}
    for wheel in sorted(args.wheelhouse.glob("*.whl")):
        name, version = wheel_identity(wheel)
        if name in packages:
            raise ValueError(f"duplicate distribution in wheelhouse: {name}")
        packages[name] = (version, digest(wheel))
    if not packages:
        raise ValueError("wheelhouse is empty")
    args.output.write_text(
        "# Generated from the complete V11 wheelhouse; install with --require-hashes.\n"
        + "".join(
            f"{name}=={version} --hash=sha256:{sha256}\n"
            for name, (version, sha256) in sorted(packages.items())
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
