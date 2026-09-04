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
ARCHITECTURE = re.compile(r"(?:amd64|arm64)")


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


def verified_file(
    evidence_dir: Path, document: dict[str, Any], path_key: str, digest_key: str
) -> Path | None:
    path = evidence_file(evidence_dir, document.get(path_key))
    digest = str(document.get(digest_key, ""))
    if (
        path is None
        or not SHA256.fullmatch(digest)
        or path.stat().st_size == 0
        or sha256_file(path) != digest
    ):
        return None
    return path


def valid_target(
    document: dict[str, Any],
    policy: dict[str, Any],
    expected_arch: str | None = None,
) -> bool:
    architecture = str(document.get("target_arch", ""))
    return (
        document.get("target_os") == policy["target_os"]
        and bool(ARCHITECTURE.fullmatch(architecture))
        and architecture in policy["target_architectures"]
        and (expected_arch is None or architecture == expected_arch)
    )


def host_adaptation_inputs(root: Path, policy: dict[str, Any]) -> dict[str, str]:
    inputs: dict[str, str] = {}
    for relative in policy.get("host_adaptation_inputs", []):
        if not isinstance(relative, str) or not relative:
            raise ValueError("host adaptation input path is invalid")
        path = (root / relative).resolve()
        if not path.is_file() or not path.is_relative_to(root):
            raise ValueError("host adaptation input is unavailable")
        inputs[relative] = sha256_file(path)
    if not inputs:
        raise ValueError("host adaptation inputs are not configured")
    return inputs


def validate_evidence(
    evidence_dir: Path,
    evidence: dict[str, Any],
    policy: dict[str, Any],
    expected_arch: str | None = None,
    root: Path | None = None,
) -> list[str]:
    blockers: list[str] = []
    host_item = evidence["host_build"]
    if not host_item["present"]:
        blockers.append("missing-host-build-evidence")
    else:
        try:
            host = read_json(evidence_dir / host_item["file"])
            valid = (
                host.get("schema_version") == 1
                and root is not None
                and host.get("release_commit") == git(root, "rev-parse", "HEAD")
                and host.get("adaptation_inputs") == host_adaptation_inputs(root, policy)
                and host.get("source_commit")
                == policy["components"]["kylin_agent"]["source_commit"]
                and valid_target(host, policy, expected_arch)
                and host.get("rebuild_verified") is True
                and host.get("network_access_during_build") is False
                and verified_file(
                    evidence_dir, host, "artifact", "artifact_sha256"
                ) is not None
                and verified_file(
                    evidence_dir, host, "source_archive", "source_archive_sha256"
                ) is not None
                and verified_file(
                    evidence_dir, host, "build_log", "build_log_sha256"
                ) is not None
            )
        except (
            KeyError,
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            subprocess.CalledProcessError,
        ):
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
            package_names = {
                str(package.get("name", ""))
                for package in packages or []
                if isinstance(package, dict)
            }
            valid_packages = isinstance(packages, list) and bool(packages) and all(
                isinstance(package, dict)
                and bool(str(package.get("name", "")).strip())
                and bool(str(package.get("version", "")).strip())
                and bool(SHA256.fullmatch(str(package.get("sha256", ""))))
                and (package_file := evidence_file(
                    evidence_dir, package.get("filename")
                )) is not None
                and package_file.suffix == ".whl"
                and sha256_file(package_file) == package["sha256"]
                for package in packages
            )
            valid = (
                wheelhouse.get("schema_version") == 1
                and wheelhouse.get("source_commit")
                == policy["components"]["agent_runtime"]["source_commit"]
                and valid_target(wheelhouse, policy, expected_arch)
                and bool(str(wheelhouse.get("python_abi", "")).strip())
                and wheelhouse.get("offline_install_verified") is True
                and wheelhouse.get("network_access_during_install") is False
                and set(policy["runtime_required_packages"]).issubset(package_names)
                and verified_file(
                    evidence_dir, wheelhouse, "lockfile", "lockfile_sha256"
                ) is not None
                and verified_file(
                    evidence_dir,
                    wheelhouse,
                    "offline_install_log",
                    "offline_install_log_sha256",
                ) is not None
                and valid_packages
            )
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
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
            packages = sbom.get("packages")
            package_by_id = {
                package.get("SPDXID"): package
                for package in packages or []
                if isinstance(package, dict)
            }
            described = set(sbom.get("documentDescribes", []))
            extracted_license_ids = {
                item.get("licenseId")
                for item in sbom.get("hasExtractedLicensingInfos", [])
                if isinstance(item, dict)
            }
            component_packages_valid = all(
                (item := package_by_id.get(component["spdx_id"])) is not None
                and item.get("name") == component["package_name"]
                and item.get("versionInfo") == component["source_commit"]
                and item.get("licenseDeclared") == component["declared_license"]
                and item.get("downloadLocation") == component["source_url"]
                and (
                    not component["declared_license"].startswith("LicenseRef-")
                    or component["declared_license"] in extracted_license_ids
                )
                for component in policy["components"].values()
            )
            wheelhouse = read_json(
                evidence_dir / evidence["runtime_wheelhouse"]["file"]
            )
            def covers_wheel(wheel: dict[str, Any]) -> bool:
                return any(
                    package.get("name") == wheel.get("name")
                    and package.get("versionInfo") == wheel.get("version")
                    and {
                        (checksum.get("algorithm"), checksum.get("checksumValue"))
                        for checksum in package.get("checksums", [])
                        if isinstance(checksum, dict)
                    }
                    >= {("SHA256", wheel.get("sha256"))}
                    for package in packages or []
                    if isinstance(package, dict)
                )
            valid = (
                sbom.get("spdxVersion") == "SPDX-2.3"
                and sbom.get("SPDXID") == "SPDXRef-DOCUMENT"
                and sbom.get("dataLicense") == "CC0-1.0"
                and isinstance(packages, list)
                and bool(packages)
                and {
                    component["spdx_id"]
                    for component in policy["components"].values()
                }.issubset(described)
                and component_packages_valid
                and all(
                    isinstance(wheel, dict) and covers_wheel(wheel)
                    for wheel in wheelhouse.get("packages", [])
                )
            )
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
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
        try:
            notice = (evidence_dir / notice_item["file"]).read_text(
                encoding="utf-8"
            )
            required_notice_values = [
                value
                for component in policy["components"].values()
                for value in (
                    component["package_name"],
                    component["source_commit"],
                    component["source_url"],
                    component["declared_license"],
                )
            ]
            valid = all(value in notice for value in required_notice_values)
        except (KeyError, OSError, TypeError):
            valid = False
        notice_item["valid"] = valid
        if not valid:
            blockers.append("invalid-agent-notice")
    return blockers


def validate_report(report: dict[str, Any], policy: dict[str, Any] | None = None) -> None:
    """Validate a release-ready audit report without trusting its top-level booleans."""
    policy = policy or read_json(
        Path(__file__).resolve().parents[1] / "agent-supply-chain-policy.json"
    )
    components = report.get("components")
    versions = report.get("runtime_version_facts")
    sensitive = report.get("sensitive_scan")
    evidence = report.get("evidence")
    expected_evidence = set(policy["evidence"])
    if not (
        report.get("schema_version") == 1
        and report.get("evidence_schema") == 1
        and report.get("evidence_class") == "agent-supply-chain-audit"
        and report.get("status") == "pass"
        and report.get("ready") is True
        and re.fullmatch(r"[0-9a-f]{40}", str(report.get("release_commit", "")))
        and report.get("blockers") == []
        and isinstance(components, dict)
        and set(components) == set(policy["components"])
        and isinstance(versions, dict)
        and versions.get("actual") == policy["components"]["agent_runtime"]["declared_versions"]
        and versions.get("expected") == versions.get("actual")
        and versions.get("match") is True
        and isinstance(sensitive, dict)
        and sensitive.get("passed") is True
        and sensitive.get("files") == []
        and sensitive.get("matched_values_redacted") is True
        and isinstance(evidence, dict)
        and set(evidence) == expected_evidence
    ):
        raise ValueError("Agent supply-chain audit is not release-ready")
    for name, component_policy in policy["components"].items():
        component = components[name]
        if not (
            isinstance(component, dict)
            and component.get("path") == component_policy["path"]
            and component.get("expected_commit") == component_policy["source_commit"]
            and component.get("gitlink_commit") == component_policy["source_commit"]
            and component.get("checkout_commit") == component_policy["source_commit"]
            and component.get("checkout_clean") is True
            and component.get("license_files_present") is True
            and component.get("passed") is True
        ):
            raise ValueError(f"Agent component is not pinned and clean: {name}")
    for name, expected_filename in policy["evidence"].items():
        item = evidence[name]
        if not (
            isinstance(item, dict)
            and item.get("file") == expected_filename
            and item.get("present") is True
            and item.get("nonempty") is True
            and item.get("valid") is True
            and SHA256.fullmatch(str(item.get("sha256", "")))
        ):
            raise ValueError(f"Agent supply-chain artifact is invalid: {name}")


def audit(
    root: Path,
    policy_path: Path,
    evidence_dir: Path,
    expected_arch: str | None = None,
) -> dict[str, Any]:
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

    expected_versions = policy["components"]["agent_runtime"][
        "declared_versions"
    ]
    try:
        actual_versions = runtime_versions(
            root / policy["components"]["agent_runtime"]["path"]
        )
    except (OSError, ValueError):
        actual_versions = {}
        blockers.append("runtime-version-facts-unavailable")
    versions_match = actual_versions == expected_versions
    if actual_versions and not versions_match:
        blockers.append("runtime-version-facts-changed")

    sensitive_files = authenticated_url_files(root, policy["sensitive_scan_paths"])
    if sensitive_files:
        blockers.append("authenticated-url-detected")
    upstream_reference_files = authenticated_url_files(
        root, policy.get("upstream_reference_scan_paths", [])
    )

    evidence = load_evidence(evidence_dir, policy["evidence"])
    blockers.extend(validate_evidence(
        evidence_dir, evidence, policy, expected_arch, root=root
    ))
    blockers = sorted(set(blockers))
    try:
        release_commit = git(root, "rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError):
        release_commit = None
        blockers.append("release-commit-unavailable")
        blockers = sorted(set(blockers))
    return {
        "schema_version": 1,
        "evidence_schema": 1,
        "evidence_class": "agent-supply-chain-audit",
        "release_commit": release_commit,
        "expected_arch": expected_arch,
        "status": "pass" if not blockers else "fail",
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
        "upstream_reference_scan": {
            "rule": "authenticated-url-userinfo",
            "files": upstream_reference_files,
            "matched_values_redacted": True,
            "release_treatment": "excluded-or-sanitized-by-verified-release-build",
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
    parser.add_argument("--expected-arch", choices=("amd64", "arm64"))
    args = parser.parse_args()
    root = args.root.resolve()
    policy = (args.policy or root / "build/release/agent-supply-chain-policy.json").resolve()
    evidence = (
        args.evidence_dir
        or root / "build/release/evidence/agent-supply-chain"
    ).resolve()
    report = audit(root, policy, evidence, args.expected_arch)
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
