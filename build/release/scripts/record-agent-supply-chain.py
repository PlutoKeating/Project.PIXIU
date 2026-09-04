#!/usr/bin/env python3
"""Record artifact-backed Agent supply-chain evidence for a release candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AUTHENTICATED_URL = re.compile(r"(?i)\b(?:https?|git)://[^/\s:@]+:[^/\s@]+@")
SAFE_ID = re.compile(r"[^A-Za-z0-9.-]")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def release_commit(root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def host_adaptation_inputs(root: Path, policy: dict[str, Any]) -> dict[str, str]:
    inputs: dict[str, str] = {}
    for relative in policy.get("host_adaptation_inputs", []):
        if not isinstance(relative, str) or not relative:
            raise ValueError("host adaptation input path is invalid")
        path = require_regular(root / relative, "host adaptation input")
        inputs[relative] = sha256_file(path)
    if not inputs:
        raise ValueError("host adaptation inputs are not configured")
    return inputs


def runtime_adaptation_inputs(root: Path, policy: dict[str, Any]) -> dict[str, str]:
    inputs: dict[str, str] = {}
    for relative in policy.get("runtime_adaptation_inputs", []):
        if not isinstance(relative, str) or not relative:
            raise ValueError("runtime adaptation input path is invalid")
        path = require_regular(root / relative, "runtime adaptation input")
        inputs[relative] = sha256_file(path)
    if not inputs:
        raise ValueError("runtime adaptation inputs are not configured")
    return inputs


def require_regular(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_file() or resolved.stat().st_size == 0:
        raise ValueError(f"{label} must be a non-empty regular file")
    return resolved


def reject_authenticated_url(path: Path, label: str) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if AUTHENTICATED_URL.search(text):
        raise ValueError(f"{label} contains an authenticated URL")


def stream_has_authenticated_url(stream: Any) -> bool:
    carry = b""
    while block := stream.read(1024 * 1024):
        content = (carry + block).decode("utf-8", errors="ignore")
        if AUTHENTICATED_URL.search(content):
            return True
        carry = block[-4096:]
    return False


def reject_archive_authenticated_url(path: Path, label: str) -> None:
    try:
        with tarfile.open(path, "r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                stream = archive.extractfile(member)
                if stream is not None and stream_has_authenticated_url(stream):
                    raise ValueError(f"{label} contains an authenticated URL")
    except tarfile.TarError as exc:
        raise ValueError(f"{label} must be a readable tar archive") from exc


def copy_evidence(source: Path, directory: Path, relative: str, label: str) -> Path:
    source = require_regular(source, label)
    destination = directory / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and sha256_file(destination) != sha256_file(source):
        raise ValueError(f"refusing to overwrite different {label}: {relative}")
    if source != destination.resolve():
        shutil.copy2(source, destination)
    return destination


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def timestamp() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    instant = (
        datetime.fromtimestamp(int(epoch), timezone.utc)
        if epoch is not None
        else datetime.now(timezone.utc)
    )
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def target(args: argparse.Namespace, policy: dict[str, Any]) -> dict[str, str]:
    if args.target_os != policy["target_os"]:
        raise ValueError("target OS does not match policy")
    if args.target_arch not in policy["target_architectures"]:
        raise ValueError("target architecture does not match policy")
    return {"target_os": args.target_os, "target_arch": args.target_arch}


def record_host(args: argparse.Namespace, policy: dict[str, Any]) -> None:
    if not args.network_isolated:
        raise ValueError("host build must be explicitly recorded as network-isolated")
    directory = args.evidence_dir.resolve()
    log = require_regular(args.build_log, "build log")
    reject_authenticated_url(log, "build log")
    artifact_input = require_regular(args.artifact, "host artifact")
    with artifact_input.open("rb") as stream:
        if stream_has_authenticated_url(stream):
            raise ValueError("host artifact contains an authenticated URL")
    source_input = require_regular(args.source_archive, "corresponding source archive")
    reject_archive_authenticated_url(source_input, "corresponding source archive")
    artifact = copy_evidence(artifact_input, directory, f"host/{args.artifact.name}", "host artifact")
    source = copy_evidence(
        source_input,
        directory,
        f"host/{args.source_archive.name}",
        "corresponding source archive",
    )
    log = copy_evidence(log, directory, f"host/{args.build_log.name}", "build log")
    document: dict[str, Any] = {
        "schema_version": 1,
        "release_commit": release_commit(args.root.resolve()),
        "source_commit": policy["components"]["kylin_agent"]["source_commit"],
        "adaptation_inputs": host_adaptation_inputs(args.root.resolve(), policy),
        **target(args, policy),
        "recorded_at": timestamp(),
        "rebuild_verified": True,
        "network_access_during_build": False,
        "artifact": artifact.relative_to(directory).as_posix(),
        "artifact_sha256": sha256_file(artifact),
        "source_archive": source.relative_to(directory).as_posix(),
        "source_archive_sha256": sha256_file(source),
        "build_log": log.relative_to(directory).as_posix(),
        "build_log_sha256": sha256_file(log),
    }
    write_json(directory / policy["evidence"]["host_build"], document)


def wheel_metadata(path: Path, policy: dict[str, Any]) -> tuple[str, str, str]:
    with zipfile.ZipFile(path) as archive:
        authenticated_members: list[str] = []
        authenticated_member_hashes: dict[str, str] = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            with archive.open(info) as stream:
                if stream_has_authenticated_url(stream):
                    authenticated_members.append(info.filename)
                    authenticated_member_hashes[info.filename] = hashlib.sha256(
                        archive.read(info.filename)
                    ).hexdigest()
        members = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(members) != 1:
            raise ValueError(f"{path.name}: wheel must contain exactly one METADATA")
        metadata = archive.read(members[0]).decode("utf-8")
    fields: dict[str, str] = {}
    for line in metadata.splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            fields.setdefault(key, value)
    name, version = fields.get("Name", "").strip(), fields.get("Version", "").strip()
    if not name or not version:
        raise ValueError(f"{path.name}: wheel metadata lacks Name or Version")
    normalized_name = name.lower().replace("_", "-")
    if authenticated_members:
        exception = policy.get("wheel_authenticated_url_exceptions", {}).get(
            f"{normalized_name}=={version}", {}
        )
        member_hashes = exception.get("member_sha256")
        identity_matches = exception.get("sha256") == sha256_file(path) or (
            isinstance(member_hashes, dict)
            and member_hashes == authenticated_member_hashes
        )
        allowed = identity_matches and (
            sorted(exception.get("members", [])) == sorted(authenticated_members)
        ) and bool(str(exception.get("reason", "")).strip())
        if not allowed:
            raise ValueError(
                f"{path.name}: wheel contains an unapproved authenticated URL location"
            )
    license_id = fields.get("License-Expression", "").strip() or "NOASSERTION"
    return name, version, license_id


def record_wheelhouse(args: argparse.Namespace, policy: dict[str, Any]) -> None:
    if not args.network_isolated:
        raise ValueError("runtime install must be explicitly recorded as network-isolated")
    directory = args.evidence_dir.resolve()
    source_dir = args.wheelhouse.resolve()
    wheels = sorted(source_dir.glob("*.whl"))
    if not wheels:
        raise ValueError("wheelhouse has no wheels")
    lock = require_regular(args.lockfile, "runtime lockfile")
    log = require_regular(args.offline_install_log, "offline install log")
    reject_authenticated_url(lock, "runtime lockfile")
    reject_authenticated_url(log, "offline install log")
    packages: list[dict[str, str]] = []
    names: set[str] = set()
    for wheel in wheels:
        wheel = require_regular(wheel, "wheel")
        name, version, license_id = wheel_metadata(wheel, policy)
        normalized_name = name.lower().replace("_", "-")
        if normalized_name in names:
            raise ValueError(f"duplicate wheel distribution: {name}")
        names.add(normalized_name)
        copied = copy_evidence(wheel, directory, f"wheelhouse/{wheel.name}", "wheel")
        packages.append(
            {
                "name": normalized_name,
                "version": version,
                "license": license_id,
                "filename": copied.relative_to(directory).as_posix(),
                "sha256": sha256_file(copied),
            }
        )
    required = {name.lower().replace("_", "-") for name in policy["runtime_required_packages"]}
    if not required.issubset(names):
        raise ValueError(f"wheelhouse lacks required packages: {sorted(required - names)}")
    lock = copy_evidence(lock, directory, f"runtime/{args.lockfile.name}", "runtime lockfile")
    log = copy_evidence(log, directory, f"runtime/{args.offline_install_log.name}", "offline install log")
    document: dict[str, Any] = {
        "schema_version": 1,
        "release_commit": release_commit(args.root.resolve()),
        "source_commit": policy["components"]["agent_runtime"]["source_commit"],
        "adaptation_inputs": runtime_adaptation_inputs(args.root.resolve(), policy),
        **target(args, policy),
        "python_abi": args.python_abi,
        "recorded_at": timestamp(),
        "offline_install_verified": True,
        "network_access_during_install": False,
        "lockfile": lock.relative_to(directory).as_posix(),
        "lockfile_sha256": sha256_file(lock),
        "offline_install_log": log.relative_to(directory).as_posix(),
        "offline_install_log_sha256": sha256_file(log),
        "packages": packages,
    }
    write_json(directory / policy["evidence"]["runtime_wheelhouse"], document)


def spdx_id(name: str, version: str) -> str:
    return "SPDXRef-Wheel-" + SAFE_ID.sub("-", f"{name}-{version}")


def record_legal(args: argparse.Namespace, policy: dict[str, Any]) -> None:
    directory = args.evidence_dir.resolve()
    wheelhouse = read_json(directory / policy["evidence"]["runtime_wheelhouse"])
    packages: list[dict[str, Any]] = []
    described: list[str] = []
    for component in policy["components"].values():
        described.append(component["spdx_id"])
        packages.append(
            {
                "name": component["package_name"],
                "SPDXID": component["spdx_id"],
                "versionInfo": component["source_commit"],
                "downloadLocation": component["source_url"],
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": component["declared_license"],
            }
        )
    for wheel in wheelhouse["packages"]:
        packages.append(
            {
                "name": wheel["name"],
                "SPDXID": spdx_id(wheel["name"], wheel["version"]),
                "versionInfo": wheel["version"],
                "downloadLocation": "NOASSERTION",
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": wheel.get("license", "NOASSERTION"),
                "checksums": [{"algorithm": "SHA256", "checksumValue": wheel["sha256"]}],
            }
        )
    identity = hashlib.sha256(
        json.dumps(packages, sort_keys=True).encode("utf-8")
    ).hexdigest()
    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "PIXIU Agent release components",
        "documentNamespace": f"https://spdx.org/spdxdocs/pixiu-agent-{identity}",
        "creationInfo": {"created": timestamp(), "creators": ["Organization: PIXIU"]},
        "documentDescribes": described,
        "packages": packages,
        "hasExtractedLicensingInfos": [
            {
                "licenseId": component["declared_license"],
                "name": f"Extracted upstream license for {component['package_name']}",
                "extractedText": "See the corresponding archived upstream LICENSE file.",
            }
            for component in policy["components"].values()
            if component["declared_license"].startswith("LicenseRef-")
        ],
    }
    write_json(directory / policy["evidence"]["sbom"], document)
    notice_lines = [
        "PIXIU Agent distribution notice",
        "",
        "This inventory records upstream facts; it is not a legal conclusion.",
    ]
    for component in policy["components"].values():
        notice_lines.extend(
            [
                "",
                f"Component: {component['package_name']}",
                f"Source: {component['source_url']}",
                f"Commit: {component['source_commit']}",
                f"Declared license: {component['declared_license']}",
            ]
        )
    (directory / policy["evidence"]["notice"]).write_text(
        "\n".join(notice_lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("host-build", "runtime-wheelhouse"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--target-os", default="kylin-v11")
        sub.add_argument("--target-arch", required=True)
    host = subparsers.choices["host-build"]
    host.add_argument("--artifact", type=Path, required=True)
    host.add_argument("--source-archive", type=Path, required=True)
    host.add_argument("--build-log", type=Path, required=True)
    host.add_argument("--network-isolated", action="store_true")
    runtime = subparsers.choices["runtime-wheelhouse"]
    runtime.add_argument("--wheelhouse", type=Path, required=True)
    runtime.add_argument("--lockfile", type=Path, required=True)
    runtime.add_argument("--offline-install-log", type=Path, required=True)
    runtime.add_argument("--python-abi", required=True)
    runtime.add_argument("--network-isolated", action="store_true")
    subparsers.add_parser("legal")
    args = parser.parse_args()
    root = args.root.resolve()
    policy = read_json(root / "build/release/agent-supply-chain-policy.json")
    try:
        {"host-build": record_host, "runtime-wheelhouse": record_wheelhouse, "legal": record_legal}[
            args.command
        ](args, policy)
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        subprocess.CalledProcessError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"agent-supply-chain-record: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
