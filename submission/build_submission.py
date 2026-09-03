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
SHA256 = re.compile(r"[0-9a-f]{64}")
VIDEO_SUFFIXES = {".avi", ".mp4", ".wmv"}
FINAL_DEVICE_EVIDENCE = Path("07-效果与测试证据/three-device-final-suite.json")
EXPECTED_DEVICE_SCENARIOS = {
    "concurrent-update-and-conflict-resolution",
    "offline-write-and-reconnect",
    "private-scope-non-propagation",
    "tombstone-propagation-and-no-resurrection",
}
EXPECTED_DEVICE_CHECKS = {
    "same_release_run_devices_and_domain",
    "fresh_final_three_device_topology",
    "all_required_scenarios_bound",
    "all_scenario_checks_passed",
    "all_scenarios_between_topology_captures",
    "final_online_quiescent_full_mesh",
    "final_logical_view_convergence",
}


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


def validate_final_device_evidence(
    evidence_path: Path, *, release_commit: str, candidate_package: Path
) -> list[str]:
    errors: list[str] = []
    try:
        report = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["three-device final evidence is not readable JSON"]
    if not isinstance(report, dict):
        return ["three-device final evidence must be a JSON object"]
    release = report.get("release")
    checks = report.get("checks")
    scenarios = report.get("scenarios")
    scenario_hashes = report.get("source_scenario_sha256")
    if not (
        report.get("evidence_schema") == 1
        and report.get("evidence_class") == "kylin-v11-three-device-final-suite"
        and report.get("real_device_evidence") is True
        and report.get("final_device_evidence") is True
        and report.get("status") == "pass"
        and report.get("remaining_required_scenarios") == []
        and isinstance(scenarios, list)
        and all(isinstance(value, str) for value in scenarios)
        and set(scenarios) == EXPECTED_DEVICE_SCENARIOS
        and isinstance(checks, dict)
        and EXPECTED_DEVICE_CHECKS.issubset(checks)
        and all(checks[name] == PASS for name in EXPECTED_DEVICE_CHECKS)
        and isinstance(scenario_hashes, list)
        and len(scenario_hashes) == 4
        and all(isinstance(value, str) and SHA256.fullmatch(value) for value in scenario_hashes)
        and len(set(scenario_hashes)) == 4
        and isinstance(report.get("initial_topology_evidence_sha256"), str)
        and SHA256.fullmatch(report["initial_topology_evidence_sha256"])
        and isinstance(report.get("final_topology_evidence_sha256"), str)
        and SHA256.fullmatch(report["final_topology_evidence_sha256"])
        and report["initial_topology_evidence_sha256"]
        != report["final_topology_evidence_sha256"]
        and isinstance(release, dict)
    ):
        errors.append("three-device final evidence contract is incomplete")
        return errors
    if release.get("git_commit") != release_commit:
        errors.append("three-device evidence commit does not match release_commit")
    if release.get("profile") != "kylin-v11-native-x86_64":
        errors.append("three-device evidence is not a strict Kylin V11 profile")
    if release.get("architecture") != "amd64":
        errors.append("three-device evidence architecture is not amd64")
    if release.get("candidate_package_sha256") != sha256(candidate_package):
        errors.append("three-device evidence package hash does not match final .deb")
    if not isinstance(release.get("agent_runtime_version"), str) or not re.fullmatch(
        r"0\.9\.[0-9]+", release["agent_runtime_version"]
    ):
        errors.append("three-device evidence Agent runtime is unsupported")
    return errors


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
        evidence_path = FINAL_ROOT / name / FINAL_DEVICE_EVIDENCE
        package_paths = [
            FINAL_ROOT / name / relative
            for relative in paths
            if relative.startswith("11-") and relative.endswith(".deb")
        ]
        if evidence_path.is_file() and len(package_paths) == 1 and package_paths[0].is_file():
            errors.extend(
                validate_final_device_evidence(
                    evidence_path,
                    release_commit=commit if isinstance(commit, str) else "",
                    candidate_package=package_paths[0],
                )
            )
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
