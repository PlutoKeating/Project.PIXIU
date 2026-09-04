#!/usr/bin/env python3
"""Capture and validate a privacy-preserving Kylin V11 install/update matrix."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVIDENCE_CLASS = "kylin-v11-install-update-matrix"
SNAPSHOT_CLASS = "kylin-v11-install-state"
OPERATION_CLASS = "kylin-v11-install-operation"
OPERATIONS = {
    "fresh_install",
    "reinstall",
    "upgrade",
    "rollback",
    "uninstall",
    "gui_update",
}
MECHANISMS = {
    "fresh_install": "system_package_installer",
    "reinstall": "privileged_update_helper",
    "upgrade": "privileged_update_helper",
    "rollback": "privileged_update_helper",
    "uninstall": "system_package_manager",
    "gui_update": "gui_upgrade_controller",
}
SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")


class EvidenceError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"unreadable JSON input: {path.name}") from exc
    if not isinstance(value, dict):
        raise EvidenceError("JSON input must be an object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path = path.resolve()
    if path.exists():
        raise EvidenceError("refusing to overwrite evidence output")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise EvidenceError(f"unreadable evidence artifact: {path.name}") from exc
    return digest.hexdigest()


def digest_text(label: str, value: str) -> str:
    return hashlib.sha256(f"{label}\0{value}".encode()).hexdigest()


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def command(*args: str, required: bool = True) -> str:
    result = subprocess.run(
        list(args), text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    if required and result.returncode != 0:
        raise EvidenceError(f"required command failed: {args[0]}")
    return result.stdout.strip() if result.returncode == 0 else ""


def loopback_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise EvidenceError("backend URL must be HTTP loopback")
    return value.rstrip("/")


def request_json(base_url: str, path: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(base_url + path, timeout=30) as response:
            value = json.load(response)
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"backend endpoint unavailable: {path}") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"backend endpoint is not an object: {path}")
    return value


def parse_os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EvidenceError("cannot read operating-system identity") from exc
    for line in lines:
        if "=" not in line or line.startswith("#"):
            continue
        key, raw = line.split("=", 1)
        values[key] = raw.strip().strip('"')
    combined = " ".join(values.get(key, "") for key in ("ID", "NAME", "VERSION_ID"))
    major = re.search(r"(?:^|[^0-9])V?11(?:[^0-9]|$)", combined, re.IGNORECASE)
    return {
        "family": "kylin" if "kylin" in combined.lower() else "other",
        "version_major": "11" if major else "other",
        "architecture": command("dpkg", "--print-architecture"),
    }


def database_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"present": False}
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            counts = {
                table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                for table in ("evidence", "knowledge_items", "preferences", "sync_peers")
                if table in tables
            }
            identity = ""
            if "sync_identity" in tables:
                row = connection.execute(
                    "SELECT device_id FROM sync_identity ORDER BY rowid LIMIT 1"
                ).fetchone()
                identity = "" if row is None else str(row[0])
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise EvidenceError("installed database cannot be inspected safely") from exc
    return {
        "present": True,
        "integrity": "ok" if integrity == ("ok",) else "failed",
        "logical_counts": counts,
        "device_identity_digest": digest_text("device", identity) if identity else None,
    }


def package_identity(package: Path) -> dict[str, Any]:
    package = package.resolve()
    if package.is_symlink() or not package.is_file():
        raise EvidenceError("candidate package must be a regular non-symlink file")
    return {
        "filename": package.name,
        "sha256": sha256_file(package),
        "size": package.stat().st_size,
        "debian_version": command("dpkg-deb", "-f", str(package), "Version"),
        "architecture": command("dpkg-deb", "-f", str(package), "Architecture"),
        "name": command("dpkg-deb", "-f", str(package), "Package"),
    }


def capture_snapshot(
    package: Path, base_url: str, expect_installed: bool
) -> dict[str, Any]:
    candidate = package_identity(package)
    if candidate["name"] != "pixiu":
        raise EvidenceError("candidate package is not PIXIU")
    package_state = command(
        "dpkg-query", "-W", "-f=${db:Status-Abbrev}|${Version}", "pixiu",
        required=False,
    )
    installed = package_state.startswith("ii ") and "|" in package_state
    installed_version = package_state.split("|", 1)[1] if installed else ""
    if installed != expect_installed:
        raise EvidenceError("observed package state differs from --expect-installed")
    service = command(
        "systemctl", "--user", "is-active", "pixiu-backend.service", required=False
    )
    service_pid = command(
        "systemctl", "--user", "show", "--property", "MainPID", "--value",
        "pixiu-backend.service", required=False,
    )
    service_same_uid = False
    if service_pid.isdigit() and int(service_pid) > 0:
        try:
            status = Path(f"/proc/{service_pid}/status").read_text(encoding="utf-8")
            match = re.search(r"^Uid:\s+(\d+)", status, re.MULTILINE)
            service_same_uid = bool(match and int(match.group(1)) == os.getuid())
        except OSError:
            service_same_uid = False
    version = health = capabilities = None
    if installed:
        base_url = loopback_url(base_url)
        version = request_json(base_url, "/version")
        health = request_json(base_url, "/health")
        capabilities = request_json(base_url, "/capabilities")
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "pixiu/pixiu.env"
    database = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "pixiu/pixiu.db"
    return {
        "evidence_schema": 1,
        "evidence_class": SNAPSHOT_CLASS,
        "real_device_evidence": True,
        "captured_at_utc": timestamp(),
        "platform": parse_os_release(),
        "candidate_package": candidate,
        "installed": {
            "present": installed,
            "debian_version": installed_version or None,
            "service_active": service == "active",
            "service_same_uid": service_same_uid,
            "binary_present": Path("/usr/bin/pixiu").is_file(),
            "release_manifest_present": Path(
                "/usr/share/pixiu/release-manifest.json"
            ).is_file(),
        },
        "runtime": {
            "version": version,
            "health": health,
            "capabilities": capabilities,
        },
        "preserved_state": {
            "config_present": config.is_file(),
            "config_sha256": sha256_file(config) if config.is_file() else None,
            "database": database_state(database),
        },
    }


def validate_snapshot(value: dict[str, Any]) -> None:
    platform = value.get("platform")
    candidate = value.get("candidate_package")
    installed = value.get("installed")
    state = value.get("preserved_state")
    if not all(isinstance(section, dict) for section in (platform, candidate, installed, state)):
        raise EvidenceError("install snapshot is incomplete")
    if not (
        value.get("evidence_schema") == 1
        and value.get("evidence_class") == SNAPSHOT_CLASS
        and value.get("real_device_evidence") is True
        and platform.get("family") == "kylin"
        and platform.get("version_major") == "11"
        and platform.get("architecture") == "amd64"
        and candidate.get("name") == "pixiu"
        and SHA256.fullmatch(str(candidate.get("sha256", "")))
        and candidate.get("architecture") == "amd64"
        and isinstance(installed.get("present"), bool)
    ):
        raise EvidenceError("snapshot is not a Kylin V11 amd64 PIXIU observation")
    if installed["present"]:
        runtime = value.get("runtime")
        database = state.get("database")
        if not (
            installed.get("service_active") is True
            and installed.get("service_same_uid") is True
            and installed.get("binary_present") is True
            and installed.get("release_manifest_present") is True
            and isinstance(runtime, dict)
            and isinstance(runtime.get("version"), dict)
            and isinstance(runtime.get("health"), dict)
            and runtime["health"].get("status") == "ready"
            and runtime["health"].get("database") == "ok"
            and isinstance(runtime.get("capabilities"), dict)
            and runtime["capabilities"].get("contest_ready") is True
            and state.get("config_present") is True
            and SHA256.fullmatch(str(state.get("config_sha256", "")))
            and isinstance(database, dict)
            and database.get("present") is True
            and database.get("integrity") == "ok"
            and isinstance(database.get("logical_counts"), dict)
            and SHA256.fullmatch(str(database.get("device_identity_digest", "")))
        ):
            raise EvidenceError("installed snapshot is not healthy and contest-ready")


def make_operation(
    operation: str, before_path: Path, after_path: Path, proof_path: Path,
    exit_code: int, outcome: str,
) -> dict[str, Any]:
    before, after = read_json(before_path), read_json(after_path)
    validate_snapshot(before)
    validate_snapshot(after)
    if operation not in OPERATIONS:
        raise EvidenceError("unknown install operation")
    if before["candidate_package"]["sha256"] != after["candidate_package"]["sha256"]:
        raise EvidenceError("operation snapshots use different candidate packages")
    if proof_path.is_symlink() or not proof_path.is_file() or proof_path.stat().st_size == 0:
        raise EvidenceError("operation proof must be a non-empty regular file")
    return {
        "evidence_schema": 1,
        "evidence_class": OPERATION_CLASS,
        "real_device_evidence": True,
        "operation": operation,
        "mechanism": MECHANISMS[operation],
        "outcome": outcome,
        "exit_code": exit_code,
        "candidate_package_sha256": before["candidate_package"]["sha256"],
        "source_sha256": {
            "before": sha256_file(before_path),
            "after": sha256_file(after_path),
            "proof": sha256_file(proof_path),
        },
        "before": before,
        "after": after,
    }


def preserved(before: dict[str, Any], after: dict[str, Any]) -> bool:
    left, right = before["preserved_state"], after["preserved_state"]
    return (
        left.get("config_present") is True
        and left.get("config_sha256") == right.get("config_sha256")
        and left.get("database") == right.get("database")
    )


def validate_operation(value: dict[str, Any], package_sha: str) -> None:
    operation = value.get("operation")
    before, after = value.get("before"), value.get("after")
    sources = value.get("source_sha256")
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise EvidenceError("operation snapshots are missing")
    validate_snapshot(before)
    validate_snapshot(after)
    if not (
        value.get("evidence_schema") == 1
        and value.get("evidence_class") == OPERATION_CLASS
        and value.get("real_device_evidence") is True
        and operation in OPERATIONS
        and value.get("mechanism") == MECHANISMS[operation]
        and value.get("candidate_package_sha256") == package_sha
        and isinstance(sources, dict)
        and set(sources) == {"before", "after", "proof"}
        and all(SHA256.fullmatch(str(item)) for item in sources.values())
    ):
        raise EvidenceError("install operation identity is invalid")
    b = before["installed"]
    a = after["installed"]
    candidate_version = after["candidate_package"]["debian_version"]
    if operation == "fresh_install":
        valid = not b["present"] and a["present"] and a["debian_version"] == candidate_version
        valid &= value.get("exit_code") == 0 and value.get("outcome") == "installed"
    elif operation == "reinstall":
        valid = b["debian_version"] == candidate_version == a["debian_version"]
        valid &= value.get("exit_code") == 0 and value.get("outcome") == "installed" and preserved(before, after)
    elif operation in {"upgrade", "gui_update"}:
        valid = b["present"] and b["debian_version"] != candidate_version
        valid &= a["debian_version"] == candidate_version
        valid &= value.get("exit_code") == 0 and value.get("outcome") == "installed" and preserved(before, after)
    elif operation == "rollback":
        valid = b["present"] and b["debian_version"] != candidate_version
        valid &= a["debian_version"] == b["debian_version"]
        valid &= value.get("exit_code") == 5 and value.get("outcome") == "recovered" and preserved(before, after)
    else:
        database = after["preserved_state"].get("database")
        valid = b["present"] and not a["present"]
        valid &= not a["service_active"] and not a["binary_present"]
        valid &= isinstance(database, dict) and database.get("present") is True
        valid &= preserved(before, after)
        valid &= value.get("exit_code") == 0 and value.get("outcome") == "removed"
    if not valid:
        raise EvidenceError(f"{operation} state transition is not proven")


def validate_native(path: Path) -> tuple[dict[str, Any], str]:
    value = read_json(path)
    module_path = Path(__file__).with_name("native-sdk-smoke.py")
    spec = importlib.util.spec_from_file_location("pixiu_native_validator", module_path)
    if spec is None or spec.loader is None:
        raise EvidenceError("native validator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        module.validate_evidence(value)
    except RuntimeError as exc:
        raise EvidenceError("native evidence does not pass strict validation") from exc
    return value, sha256_file(path)


def assemble(native_path: Path, operation_paths: list[Path]) -> dict[str, Any]:
    native, native_sha = validate_native(native_path)
    release = native["release"]
    package_sha = native["candidate_package"]["sha256"]
    operations: dict[str, dict[str, Any]] = {}
    sources: dict[str, str] = {"native": native_sha}
    for path in operation_paths:
        value = read_json(path)
        operation = value.get("operation")
        if operation in operations:
            raise EvidenceError(f"duplicate install operation: {operation}")
        validate_operation(value, package_sha)
        if value["after"]["candidate_package"]["debian_version"] != release["debian_version"]:
            raise EvidenceError("install operation candidate version differs from native evidence")
        operations[operation] = value
        sources[str(operation)] = sha256_file(path)
    if set(operations) != OPERATIONS:
        raise EvidenceError("install matrix does not contain every required operation")
    checks = {name: "passed" for name in sorted(OPERATIONS)}
    checks["data_preserved"] = "passed"
    evidence = {
        "evidence_schema": 1,
        "evidence_class": EVIDENCE_CLASS,
        "real_device_evidence": True,
        "status": "pass",
        "generated_at_utc": timestamp(),
        "release": {
            "git_commit": release["git_commit"],
            "product_version": release["product_version"],
            "debian_version": release["debian_version"],
            "architecture": release["architecture"],
            "profile": release["profile"],
            "candidate_package_sha256": package_sha,
            "native_evidence_sha256": native_sha,
        },
        "checks": checks,
        "source_sha256": sources,
        "observations": {
            "operation_count": len(operations),
            "payloads_retained": False,
            "uninstall_policy": "remove-preserves-user-data; purge-deletes-user-data",
        },
    }
    validate_final(evidence)
    return evidence


def validate_final(value: dict[str, Any]) -> None:
    release, checks, sources = value.get("release"), value.get("checks"), value.get("source_sha256")
    required_checks = OPERATIONS | {"data_preserved"}
    if not (
        value.get("evidence_schema") == 1
        and value.get("evidence_class") == EVIDENCE_CLASS
        and value.get("real_device_evidence") is True
        and value.get("status") == "pass"
        and isinstance(release, dict)
        and COMMIT.fullmatch(str(release.get("git_commit", "")))
        and release.get("architecture") == "amd64"
        and release.get("profile") == "kylin-v11-native-x86_64"
        and SHA256.fullmatch(str(release.get("candidate_package_sha256", "")))
        and SHA256.fullmatch(str(release.get("native_evidence_sha256", "")))
        and isinstance(checks, dict)
        and set(checks) == required_checks
        and all(checks[name] == "passed" for name in required_checks)
        and isinstance(sources, dict)
        and set(sources) == OPERATIONS | {"native"}
        and all(SHA256.fullmatch(str(item)) for item in sources.values())
        and len(set(sources.values())) == len(sources)
        and value.get("observations", {}).get("payloads_retained") is False
    ):
        raise EvidenceError("final install/update matrix is invalid")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--package", type=Path, required=True)
    snapshot_parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    snapshot_parser.add_argument("--expect-installed", choices=("yes", "no"), required=True)
    snapshot_parser.add_argument("--output", type=Path, required=True)
    operation_parser = subparsers.add_parser("operation")
    operation_parser.add_argument("--kind", choices=sorted(OPERATIONS), required=True)
    operation_parser.add_argument("--before", type=Path, required=True)
    operation_parser.add_argument("--after", type=Path, required=True)
    operation_parser.add_argument("--proof", type=Path, required=True)
    operation_parser.add_argument("--exit-code", type=int, required=True)
    operation_parser.add_argument("--outcome", choices=("installed", "recovered", "removed"), required=True)
    operation_parser.add_argument("--output", type=Path, required=True)
    final_parser = subparsers.add_parser("finalize")
    final_parser.add_argument("--native-evidence", type=Path, required=True)
    final_parser.add_argument("--operation", type=Path, action="append", required=True)
    final_parser.add_argument("--output", type=Path, required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "snapshot":
            value = capture_snapshot(args.package, args.base_url, args.expect_installed == "yes")
            validate_snapshot(value)
            write_json(args.output, value)
        elif args.command == "operation":
            value = make_operation(args.kind, args.before, args.after, args.proof, args.exit_code, args.outcome)
            validate_operation(value, value["candidate_package_sha256"])
            write_json(args.output, value)
        elif args.command == "finalize":
            write_json(args.output, assemble(args.native_evidence, args.operation))
        else:
            validate_final(read_json(args.input))
    except (EvidenceError, OSError, subprocess.SubprocessError) as exc:
        print(f"install-update-evidence: {exc}", file=sys.stderr)
        return 1
    print("install-update-evidence: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
