#!/usr/bin/env python3
"""Fail-closed validator and packager for the final contest submission."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBMISSION_ROOT = ROOT / "submission"
FINAL_ROOT = SUBMISSION_ROOT / "final"
PLAN_PATH = SUBMISSION_ROOT / "submission-plan.json"
PASS = "passed"
SHA1 = re.compile(r"[0-9a-f]{40}")
VIDEO_SUFFIXES = {".avi", ".mp4", ".wmv"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args], text=True, stderr=subprocess.STDOUT
    ).strip()


def load_plan() -> dict:
    with PLAN_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


def validate_plan(plan: dict, *, require_ready: bool) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("submission plan schema_version must be 1")
    name = plan.get("submission_name")
    if name != "华南理工大学－OSAgent记忆优化及高效应用研究－PIXIU":
        errors.append("official outer submission name is incorrect")

    for relative, expected in plan.get("official_sources", {}).items():
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            errors.append(f"official source hash mismatch: {relative}")

    ids = [item.get("id") for item in plan.get("deliverables", [])]
    expected_ids = [f"D-{number:02d}" for number in range(1, 11)] + ["R-01"]
    if ids != expected_ids:
        errors.append("deliverables must contain ordered D-01..D-10 and R-01")

    paths = [path for item in plan.get("deliverables", []) for path in item.get("paths", [])]
    if len(paths) != len(set(paths)):
        errors.append("deliverable paths must be unique")
    video_paths = [Path(path) for path in paths if path.startswith("05-")]
    if len(video_paths) != 1 or video_paths[0].suffix.lower() not in VIDEO_SUFFIXES:
        errors.append("D-05 must be one AVI, MP4, or WMV video")

    if require_ready:
        if plan.get("release_ready") is not True:
            errors.append("release_ready is false")
        commit = plan.get("release_commit")
        if not isinstance(commit, str) or not SHA1.fullmatch(commit):
            errors.append("release_commit must be a full lowercase Git SHA-1")
        elif git("rev-parse", "HEAD") != commit:
            errors.append("HEAD does not match release_commit")
        pending = [key for key, value in plan.get("release_gates", {}).items() if value != PASS]
        if pending:
            errors.append("release gates not passed: " + ", ".join(pending))
        if git("status", "--porcelain"):
            errors.append("Git worktree is not clean")
        for relative in paths:
            if not (FINAL_ROOT / name / relative).is_file():
                errors.append(f"missing final deliverable: {relative}")
        for item in plan.get("external_materials", []):
            relative = item.get("path", "")
            if not relative or not (FINAL_ROOT / name / relative).is_file():
                errors.append(f"missing external material: {relative}")
    return errors


def write_checksums_and_zip(plan: dict) -> Path:
    package_root = FINAL_ROOT / plan["submission_name"]
    output = FINAL_ROOT / f'{plan["submission_name"]}.zip'
    manifest_path = package_root / "SUBMISSION_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    members = sorted(path for path in package_root.rglob("*") if path.is_file())
    checksum_path = package_root / "SHA256SUMS"
    checksum_path.write_text(
        "".join(
            f"{sha256(path)}  {path.relative_to(package_root).as_posix()}\n"
            for path in members
            if path != checksum_path
        ),
        encoding="utf-8",
    )
    members = sorted(path for path in package_root.rglob("*") if path.is_file())
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in members:
            archive.write(path, (Path(plan["submission_name"]) / path.relative_to(package_root)).as_posix())
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="validate plan structure and immutable sources")
    group.add_argument("--package", action="store_true", help="validate a complete release and create final ZIP")
    args = parser.parse_args()
    plan = load_plan()
    errors = validate_plan(plan, require_ready=args.package)
    if errors:
        for error in errors:
            print(f"[submission] ERROR: {error}", file=sys.stderr)
        return 1
    if args.package:
        output = write_checksums_and_zip(plan)
        print(f"[submission] created {output}")
    else:
        print("[submission] plan and immutable sources are valid; release readiness was not asserted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
