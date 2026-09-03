#!/usr/bin/env python3
"""Build and validate the fail-closed D-07 raw evidence archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "submission/evidence-policy.json"
SHA1 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
SENSITIVE = re.compile(
    rb"(?i)(?:https?|git)://[^/\s:@]+:[^/\s@]+@|-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{12,}|\bBearer\s+[A-Za-z0-9._~-]{12,}|/(?:home|Users)/[^/\s]+/|[A-Z]:\\Users\\[^\\\s]+\\"
)
TEXT_SUFFIXES = {".json", ".csv", ".txt", ".log", ".md", ".yaml", ".yml"}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: JSON root must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def nested(value: dict[str, Any], path: list[str]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def regular(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_file() or resolved.stat().st_size == 0:
        raise ValueError(f"{label} must be a non-empty regular file")
    return resolved


def scan_sensitive(path: Path) -> None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return
    if SENSITIVE.search(path.read_bytes()):
        raise ValueError(f"sensitive value or personal path detected: {path.name}")


def validate_record(
    name: str,
    document: dict[str, Any],
    rule: dict[str, Any],
    *,
    release_commit: str,
    package_sha256: str,
) -> list[str]:
    errors: list[str] = []
    if not (
        document.get("evidence_schema") == 1
        and document.get("evidence_class") == rule["evidence_class"]
        and document.get("status") == "pass"
    ):
        errors.append(f"{name}: evidence identity/status is invalid")
    if nested(document, rule["commit_path"]) != release_commit:
        errors.append(f"{name}: release commit mismatch")
    package_path = rule.get("package_sha256_path")
    if package_path and nested(document, package_path) != package_sha256:
        errors.append(f"{name}: candidate package hash mismatch")
    if "real_device_evidence" in rule and document.get("real_device_evidence") is not rule["real_device_evidence"]:
        errors.append(f"{name}: real-device classification mismatch")
    if rule.get("requires_ready") and document.get("ready") is not True:
        errors.append(f"{name}: supply chain is not ready")
    if rule.get("requires_final_device_evidence") and document.get("final_device_evidence") is not True:
        errors.append(f"{name}: final device evidence is false")
    checks = document.get("checks")
    for check in rule.get("required_checks", []):
        if not isinstance(checks, dict) or checks.get(check) != "passed":
            errors.append(f"{name}: required check not passed: {check}")
    return errors


def validate_inputs(
    records: dict[str, Path], policy: dict[str, Any], release_commit: str, package_sha256: str
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    expected = set(policy["records"])
    if set(records) != expected:
        missing, extra = sorted(expected - set(records)), sorted(set(records) - expected)
        if missing:
            errors.append("missing evidence records: " + ", ".join(missing))
        if extra:
            errors.append("unknown evidence records: " + ", ".join(extra))
    documents: dict[str, dict[str, Any]] = {}
    for name in sorted(expected & set(records)):
        try:
            path = regular(records[name], f"{name} record")
            scan_sensitive(path)
            document = read_json(path)
            documents[name] = document
            errors.extend(
                validate_record(
                    name, document, policy["records"][name],
                    release_commit=release_commit, package_sha256=package_sha256,
                )
            )
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{name}: {exc}")
    return documents, errors


def zip_info(name: str, epoch: int) -> zipfile.ZipInfo:
    instant = datetime.fromtimestamp(max(epoch, 315532800), timezone.utc)
    info = zipfile.ZipInfo(name, instant.timetuple()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def build_archive(
    output: Path,
    records: dict[str, Path],
    attachments: list[Path],
    policy: dict[str, Any],
    *,
    release_commit: str,
    package: Path,
    epoch: int,
) -> None:
    if output.exists():
        raise ValueError("refusing to overwrite existing evidence archive")
    package = regular(package, "candidate package")
    package_sha256 = sha256_file(package)
    _, errors = validate_inputs(records, policy, release_commit, package_sha256)
    if errors:
        raise ValueError("; ".join(errors))
    entries: list[tuple[str, Path]] = []
    for name, rule in sorted(policy["records"].items()):
        entries.append((f"records/{rule['filename']}", regular(records[name], name)))
    used_attachment_names: set[str] = set()
    for attachment in attachments:
        attachment = regular(attachment, "attachment")
        scan_sensitive(attachment)
        if attachment.name in used_attachment_names:
            raise ValueError(f"duplicate attachment basename: {attachment.name}")
        used_attachment_names.add(attachment.name)
        entries.append((f"attachments/{attachment.name}", attachment))
    manifest = {
        "evidence_schema": 1,
        "evidence_class": "pixiu-final-raw-evidence-archive",
        "status": "pass",
        "release": {
            "git_commit": release_commit,
            "candidate_package": package.name,
            "candidate_package_sha256": package_sha256,
        },
        "records": [
            {"path": name, "size": path.stat().st_size, "sha256": sha256_file(path)}
            for name, path in entries
        ],
    }
    rendered = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode() + b"\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".pixiu-evidence-", suffix=".zip", dir=output.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            archive.writestr(zip_info("EVIDENCE_MANIFEST.json", epoch), rendered)
            for name, path in entries:
                archive.writestr(zip_info(name, epoch), path.read_bytes())
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def validate_archive(
    archive_path: Path, policy: dict[str, Any], *, release_commit: str, package_sha256: str
) -> list[str]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or archive.testzip() is not None:
                return ["evidence archive has duplicate or corrupt members"]
            manifest = json.loads(archive.read("EVIDENCE_MANIFEST.json"))
            if not isinstance(manifest, dict) or not (
                manifest.get("evidence_schema") == 1
                and manifest.get("evidence_class") == "pixiu-final-raw-evidence-archive"
                and manifest.get("status") == "pass"
                and nested(manifest, ["release", "git_commit"]) == release_commit
                and nested(manifest, ["release", "candidate_package_sha256"]) == package_sha256
            ):
                return ["evidence archive manifest identity is invalid"]
            declared = manifest.get("records")
            if not isinstance(declared, list):
                return ["evidence archive record manifest is invalid"]
            declared_names = {item.get("path") for item in declared if isinstance(item, dict)}
            if set(names) != declared_names | {"EVIDENCE_MANIFEST.json"}:
                errors.append("evidence archive members do not match manifest")
            record_documents: dict[str, Path] = {}
            with tempfile.TemporaryDirectory() as temporary:
                temporary_root = Path(temporary)
                for item in declared:
                    if not isinstance(item, dict):
                        errors.append("evidence archive record entry is invalid")
                        continue
                    name, digest, size = item.get("path"), item.get("sha256"), item.get("size")
                    if not isinstance(name, str) or name.startswith("/") or ".." in Path(name).parts:
                        errors.append("evidence archive contains unsafe path")
                        continue
                    content = archive.read(name)
                    if len(content) != size or hashlib.sha256(content).hexdigest() != digest:
                        errors.append(f"evidence archive member mismatch: {name}")
                        continue
                    if Path(name).suffix.lower() in TEXT_SUFFIXES and SENSITIVE.search(content):
                        errors.append(f"evidence archive contains sensitive content: {name}")
                        continue
                    if name.startswith("records/"):
                        target = temporary_root / Path(name).name
                        target.write_bytes(content)
                        logical = next(
                            (key for key, rule in policy["records"].items() if rule["filename"] == Path(name).name),
                            None,
                        )
                        if logical:
                            record_documents[logical] = target
                        else:
                            errors.append(f"unknown primary evidence record: {name}")
                _, record_errors = validate_inputs(
                    record_documents, policy, release_commit, package_sha256
                )
                errors.extend(record_errors)
    except (KeyError, OSError, TypeError, ValueError, zipfile.BadZipFile, json.JSONDecodeError):
        return ["evidence archive is unreadable or malformed"]
    return errors


def parse_records(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--record must use NAME=PATH")
        name, path = value.split("=", 1)
        if not name or name in result:
            raise ValueError(f"duplicate or empty record name: {name}")
        result[name] = Path(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", action="store_true")
    group.add_argument("--validate", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--record", action="append", default=[])
    parser.add_argument("--attachment", action="append", type=Path, default=[])
    args = parser.parse_args()
    root = args.root.resolve()
    policy = read_json(root / "submission/evidence-policy.json")
    try:
        release_commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        if not SHA1.fullmatch(release_commit):
            raise ValueError("release commit is invalid")
        package = regular(args.package, "candidate package")
        if args.build:
            if subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True):
                raise ValueError("evidence archive requires a clean worktree")
            epoch = int(
                subprocess.check_output(
                    ["git", "-C", str(root), "show", "-s", "--format=%ct", "HEAD"], text=True
                ).strip()
            )
            build_archive(
                args.output.resolve(), parse_records(args.record), args.attachment, policy,
                release_commit=release_commit, package=package, epoch=epoch,
            )
        else:
            errors = validate_archive(
                args.output.resolve(), policy,
                release_commit=release_commit, package_sha256=sha256_file(package),
            )
            if errors:
                raise ValueError("; ".join(errors))
    except (OSError, subprocess.CalledProcessError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"evidence-archive: {exc}", file=sys.stderr)
        return 1
    print("evidence-archive: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
