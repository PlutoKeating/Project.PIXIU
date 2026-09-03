#!/usr/bin/env python3
"""Generate a non-self-referential manifest for signed release assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


DEB_NAME = re.compile(
    r"^pixiu_(?P<version>[0-9]+\.[0-9]+\.[0-9]+)-"
    r"(?P<revision>[0-9A-Za-z.+~]+)_(?P<architecture>[0-9A-Za-z]+)\.deb$"
)


def regular_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_file():
        raise SystemExit(f"pixiu-assets: {label} must be a regular non-symlink file")
    return resolved


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def timestamp() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    instant = (
        datetime.fromtimestamp(int(epoch), tz=timezone.utc)
        if epoch is not None
        else datetime.now(tz=timezone.utc)
    )
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def asset(path: Path, role: str) -> dict[str, object]:
    return {
        "name": path.name,
        "role": role,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deb", type=Path, required=True)
    parser.add_argument("--checksum", type=Path, required=True)
    parser.add_argument("--signature", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--channel", choices=("staging", "production"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    deb = regular_file(args.deb, "deb")
    checksum = regular_file(args.checksum, "checksum")
    signature = regular_file(args.signature, "signature")
    public_key = regular_file(args.public_key, "public key")
    output = args.output.resolve()
    if len({deb.parent, checksum.parent, signature.parent, output.parent}) != 1:
        raise SystemExit("pixiu-assets: all assets and output must share one directory")
    if output in {deb, checksum, signature, public_key}:
        raise SystemExit("pixiu-assets: output must not overwrite an input")

    match = DEB_NAME.fullmatch(deb.name)
    if not match:
        raise SystemExit("pixiu-assets: invalid PIXIU deb filename")
    if checksum.name != f"{deb.name}.sha256" or signature.name != f"{checksum.name}.sig":
        raise SystemExit("pixiu-assets: checksum/signature filenames do not match deb")
    fields = checksum.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[1].removeprefix("*") != deb.name:
        raise SystemExit("pixiu-assets: checksum does not name the deb")
    actual_digest = sha256(deb)
    if fields[0].lower() != actual_digest:
        raise SystemExit("pixiu-assets: deb checksum mismatch")
    with tempfile.NamedTemporaryFile("w", encoding="ascii", delete=False) as stream:
        stream.write(f"{actual_digest}\n")
        digest_file = Path(stream.name)
    try:
        verified = subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-verify",
                "-pubin",
                "-rawin",
                "-in",
                str(digest_file),
                "-inkey",
                str(public_key),
                "-sigfile",
                str(signature),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    finally:
        digest_file.unlink(missing_ok=True)
    if verified.returncode != 0:
        raise SystemExit("pixiu-assets: release signature verification failed")
    with tempfile.TemporaryDirectory() as directory:
        subprocess.run(
            ["dpkg-deb", "-x", str(deb), directory],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        embedded_path = Path(directory) / "usr/share/pixiu/release-manifest.json"
        if not embedded_path.is_file():
            raise SystemExit("pixiu-assets: package component manifest is missing")
        embedded = json.loads(embedded_path.read_text(encoding="utf-8"))

    control_version = subprocess.check_output(
        ["dpkg-deb", "--field", str(deb), "Version"], text=True
    ).strip()
    control_arch = subprocess.check_output(
        ["dpkg-deb", "--field", str(deb), "Architecture"], text=True
    ).strip()

    values = match.groupdict()
    expected_debian_version = f'{values["version"]}-{values["revision"]}'
    git_commit = embedded.get("build", {}).get("git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", git_commit):
        raise SystemExit("pixiu-assets: invalid embedded git commit")
    if (
        embedded.get("product", {}).get("debian_version") != expected_debian_version
        or embedded.get("build", {}).get("architecture") != values["architecture"]
        or control_version != expected_debian_version
        or control_arch != values["architecture"]
    ):
        raise SystemExit("pixiu-assets: package identity metadata mismatch")
    manifest = {
        "manifest_schema": 1,
        "product_version": values["version"],
        "debian_version": expected_debian_version,
        "architecture": values["architecture"],
        "channel": args.channel,
        "git_commit": git_commit,
        "generated_at_utc": timestamp(),
        "assets": [
            asset(deb, "package"),
            asset(checksum, "checksum"),
            asset(signature, "signature"),
        ],
        "authentication": {
            "checksum": f"{output.name}.sha256",
            "signature": f"{output.name}.sha256.sig",
            "algorithm": "Ed25519-over-lowercase-SHA256",
        },
        "generation": {
            "tool": "build/release/scripts/generate-artifact-manifest.py",
            "command": [
                "generate-artifact-manifest.py",
                "--deb", deb.name,
                "--checksum", checksum.name,
                "--signature", signature.name,
                "--public-key", public_key.name,
                "--channel", args.channel,
                "--output", output.name,
            ],
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=output.parent, delete=False
    ) as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.chmod(0o644)
    temporary.replace(output)


if __name__ == "__main__":
    main()
