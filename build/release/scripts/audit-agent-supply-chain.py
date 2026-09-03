#!/usr/bin/env python3
"""Audit whether the pinned openKylin Agent supply chain is release-ready.

The default command emits a factual JSON report and returns success so known
upstream blockers remain visible without making ordinary development CI red.
Release candidates must add ``--require-ready`` and provide the evidence dir.
Potential credentials are never copied into the report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


AUTHENTICATED_URL = re.compile(
    r"(?i)\b(?:https?|git)://[^/\s:@]+:[^/\s@]+@"
)
SHA256 = re.compile(r"[0-9a-f]{64}")


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("top-level JSON value must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evidence_file(evidence_dir: Path, relative_path: object) -> Path | None:
    if not isinstance(relative_path, str) or not relative_path:
        return None
    unresolved = evidence_dir / relative_path
    if unresolved.is_symlink():
        return None
    candidate = unresolved.resolve()
    try:
        candidate.relative_to(evidence_dir.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() and not candidate.is_symlink() else None


def iter_regular_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file() and not path.is_symlink():
            yield path
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and not child.is_symlink():
                    yield child


def authenticated_url_files(root: Path, relative_paths: list[str]) -> list[str]:
    findings: list[str] = []
    paths = [root / relative for relative in relative_paths]
    for path in iter_regular_files(paths):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if AUTHENTICATED_URL.search(content):
            findings.append(path.relative_to(root).as_posix())
    return findings


def runtime_versions(runtime: Path) -> dict[str, str]:
    pyproject = (runtime / "pyproject.toml").read_text(encoding="utf-8")
    cli_source = (
        runtime / "kylin_agent_runtime_cli" / "__init__.py"
    ).read_text(encoding="utf-8")
    metadata = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    cli = re.search(r'^__version__\s*=\s*"([^"]+)"', cli_source, re.MULTILINE)
    if metadata is None or cli is None:
        raise ValueError("cannot read all runtime version declarations")
    return {
        "cli": cli.group(1),
        "package_metadata": metadata.group(1),
        "version_file": (runtime / "version").read_text(encoding="utf-8").strip(),
    }


def check_component(root: Path, name: str, policy: dict[str, Any]) -> dict[str, Any]:
    relative_path = str(policy["path"])
    source = root / relative_path
    expected = str(policy["source_commit"])
    result: dict[str, Any] = {
        "name": name,
        "path": relative_path,
        "expected_commit": expected,
        "gitlink_commit": None,
        "checkout_commit": None,
        "checkout_clean": False,
        "license_files_present": False,
        "passed": False,
    }
    try:
        result["gitlink_commit"] = git(root, "rev-parse", f"HEAD:{relative_path}")
        result["checkout_commit"] = git(source, "rev-parse", "HEAD")
        result["checkout_clean"] = not bool(git(source, "status", "--porcelain"))
    except (OSError, subprocess.CalledProcessError):
        return result
    result["license_files_present"] = all(
        (source / str(item)).is_file() for item in policy.get("license_files", [])
    )
    result["passed"] = all(
        (
            result["gitlink_commit"] == expected,
            result["checkout_commit"] == expected,
            result["checkout_clean"],
            result["license_files_present"],
        )
    )
    return result


def load_evidence(evidence_dir: Path, policy: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, filename in policy.items():
        path = evidence_dir / filename
        item: dict[str, Any] = {"file": filename, "present": path.is_file()}
        if path.is_file():
            item["sha256"] = sha256_file(path)
            item["nonempty"] = path.stat().st_size > 0
        result[name] = item
    return result


def validate_evidence(
    evidence_dir: Path,
    evidence: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    host_item = evidence["host_build"]
    if not host_item["present"]:
        blockers.append("missing-host-build-evidence")
    else:
        try:
            host = read_json(evidence_dir / host_item["file"])
            artifact = evidence_file(evidence_dir, host.get("artifact"))
            declared_digest = str(host.get("artifact_sha256", ""))
            valid = (
                host.get("source_commit")
                == policy["components"]["kylin_agent"]["source_commit"]
                and host.get("target_os") == "kylin-v11"
                and host.get("rebuild_verified") is True
                and artifact is not None
                and bool(SHA256.fullmatch(declared_digest))
                and sha256_file(artifact) == declared_digest
            )
        except (OSError, ValueError, json.JSONDecodeError):
            valid = False
        host_item["valid"] = valid
        if not valid:
            blockers.append("invalid-host-build-evidence")

    wheel_item = evidence["runtime_wheelhouse"]
    if not wheel_item["present"]:
        blockers.append("missing-runtime-wheelhouse-evidence")
    else:
        try:
            wheelhouse = read_json(evidence_dir / wheel_item["file"])
            packages = wheelhouse.get("packages")
            valid_packages = isinstance(packages, list) and bool(packages) and all(
                isinstance(package, dict)
                and bool(SHA256.fullmatch(str(package.get("sha256", ""))))
                and (package_file := evidence_file(
                    evidence_dir, package.get("filename")
                )) is not None
                and sha256_file(package_file) == package["sha256"]
                for package in packages
            )
            valid = (
                wheelhouse.get("source_commit")
                == policy["components"]["agent_runtime"]["source_commit"]
                and wheelhouse.get("offline_install_verified") is True
                and valid_packages
            )
        except (OSError, ValueError, json.JSONDecodeError):
            valid = False
        wheel_item["valid"] = valid
        if not valid:
            blockers.append("invalid-runtime-wheelhouse-evidence")

    sbom_item = evidence["sbom"]
    if not sbom_item["present"]:
        blockers.append("missing-agent-sbom")
    else:
        try:
            sbom = read_json(evidence_dir / sbom_item["file"])
            valid = (
                str(sbom.get("spdxVersion", "")).startswith("SPDX-")
                and sbom.get("SPDXID") == "SPDXRef-DOCUMENT"
                and isinstance(sbom.get("packages"), list)
                and bool(sbom["packages"])
            )
        except (OSError, ValueError, json.JSONDecodeError):
            valid = False
        sbom_item["valid"] = valid
        if not valid:
            blockers.append("invalid-agent-sbom")

    notice_item = evidence["notice"]
    if not notice_item["present"]:
        blockers.append("missing-agent-notice")
    elif not notice_item.get("nonempty"):
        blockers.append("empty-agent-notice")
    else:
        notice_item["valid"] = True
    return blockers


def audit(root: Path, policy_path: Path, evidence_dir: Path) -> dict[str, Any]:
    policy = read_json(policy_path)
    components = {
        name: check_component(root, name, component_policy)
        for name, component_policy in policy["components"].items()
    }
    blockers = [
        f"component-not-pinned:{name}"
        for name, component in components.items()
        if not component["passed"]
    ]

    actual_versions = runtime_versions(
        root / policy["components"]["agent_runtime"]["path"]
    )
    expected_versions = policy["components"]["agent_runtime"][
        "declared_versions"
    ]
    versions_match = actual_versions == expected_versions
    if not versions_match:
        blockers.append("runtime-version-facts-changed")

    sensitive_files = authenticated_url_files(root, policy["sensitive_scan_paths"])
    if sensitive_files:
        blockers.append("authenticated-url-detected")

    evidence = load_evidence(evidence_dir, policy["evidence"])
    blockers.extend(validate_evidence(evidence_dir, evidence, policy))
    blockers = sorted(set(blockers))
    return {
        "schema_version": 1,
        "ready": not blockers,
        "policy": policy_path.relative_to(root).as_posix(),
        "components": components,
        "runtime_version_facts": {
            "actual": actual_versions,
            "expected": expected_versions,
            "match": versions_match,
        },
        "sensitive_scan": {
            "rule": "authenticated-url-userinfo",
            "passed": not sensitive_files,
            "files": sensitive_files,
            "matched_values_redacted": True,
        },
        "evidence": evidence,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    policy = (args.policy or root / "build/release/agent-supply-chain-policy.json").resolve()
    evidence = (
        args.evidence_dir
        or root / "build/release/evidence/agent-supply-chain"
    ).resolve()
    report = audit(root, policy, evidence)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 1 if args.require_ready and not report["ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
