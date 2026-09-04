#!/usr/bin/env python3
"""Fail-closed validator and packager for the final contest submission."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import subprocess
import sys
import tarfile
import tempfile
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
OFFICIAL_TOP_LEVEL = {
    "01-项目报告",
    "02-技术方案及测试结果",
    "03-源代码及规范",
    "04-部署文档",
    "05-功能演示视频",
}
SOURCE_EXCLUDED_PREFIXES = ("submission/review/", "submission/final/")
FINAL_DEVICE_EVIDENCE = Path("02-技术方案及测试结果/02-效果与测试证据/three-device-final-suite.json")
RAW_EVIDENCE_ARCHIVE = Path("02-技术方案及测试结果/02-效果与测试证据/原始证据.zip")
SOURCE_ARCHIVE = Path("03-源代码及规范/Project.PIXIU-source.tar.gz")
REQUIRED_SOURCE_PATHS = {
    "README.md",
    "VERSION",
    "backend/",
    "frontend/",
    "integrations/kylin_agent/",
    "build/release/",
    "docs/delivery/",
    "third_party/kylin-agent/",
    "third_party/kylin-agent-runtime/",
    "third_party/kylin-coreai-embedding/",
    "third_party/libkysdk-vector-engine-client/",
}
REQUIRED_SUBMODULES = {
    "third_party/kylin-agent",
    "third_party/kylin-agent-runtime",
    "third_party/kylin-coreai-embedding",
    "third_party/libkysdk-vector-engine-client",
}
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


def worktree_source_entries() -> dict[str, dict[str, str]]:
    """Return the exact tracked source identity of the clean release checkout."""
    raw = git("ls-files", "--recurse-submodules", "-z")
    paths = [
        value
        for value in raw.split("\0")
        if value and not value.startswith(SOURCE_EXCLUDED_PREFIXES)
    ]
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("release source list is empty or contains duplicates")
    entries: dict[str, dict[str, str]] = {}
    for relative in paths:
        path = ROOT / relative
        if path.is_symlink():
            target = os.readlink(path)
            entries[relative] = {
                "type": "symlink",
                "sha256": hashlib.sha256(target.encode("utf-8")).hexdigest(),
            }
        elif path.is_file():
            entries[relative] = {"type": "file", "sha256": sha256(path)}
        else:
            raise ValueError(f"tracked release source is unavailable: {relative}")
    return entries


def validate_source_archive(path: Path, *, release_commit: str) -> list[str]:
    errors: list[str] = []
    prefix = "Project.PIXIU-source/"
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)):
                return ["source archive contains duplicate paths"]
            if any(
                not name.startswith(prefix)
                or name.startswith("/")
                or ".." in Path(name).parts
                for name in names
            ):
                return ["source archive contains an unsafe or unexpected path"]
            manifest_member = archive.getmember(prefix + "SOURCE_MANIFEST.json")
            stream = archive.extractfile(manifest_member)
            if stream is None:
                return ["source archive manifest is not a regular file"]
            manifest = json.load(stream)
            if not isinstance(manifest, dict):
                return ["source archive manifest must be a JSON object"]
            tracked = manifest.get("tracked_files")
            evidence = manifest.get("agent_supply_chain_evidence")
            submodules = manifest.get("submodules")
            if not (
                manifest.get("schema_version") == 1
                and manifest.get("archive_prefix") == "Project.PIXIU-source"
                and manifest.get("release_commit") == release_commit
                and isinstance(tracked, list)
                and bool(tracked)
                and isinstance(evidence, list)
                and bool(evidence)
                and isinstance(submodules, dict)
                and REQUIRED_SUBMODULES.issubset(submodules)
                and all(isinstance(value, str) and SHA1.fullmatch(value) for value in submodules.values())
            ):
                return ["source archive manifest contract is incomplete"]
            expected_submodules = {
                name: git("rev-parse", f"{release_commit}:{name}")
                for name in REQUIRED_SUBMODULES
            }
            if any(submodules.get(name) != commit for name, commit in expected_submodules.items()):
                errors.append("source archive submodule commits do not match release commit")
            tracked_paths = {
                item.get("path")
                for item in tracked
                if isinstance(item, dict) and isinstance(item.get("path"), str)
            }
            if len(tracked_paths) != len(tracked):
                errors.append("source archive manifest contains invalid or duplicate source paths")
            try:
                expected_sources = worktree_source_entries()
            except (OSError, subprocess.SubprocessError, ValueError):
                return ["release checkout source identity is unavailable"]
            if tracked_paths != set(expected_sources):
                errors.append("source archive source list does not match release checkout")
            if not all(
                required in tracked_paths
                if not required.endswith("/")
                else any(value.startswith(required) for value in tracked_paths)
                for required in REQUIRED_SOURCE_PATHS
            ):
                errors.append("source archive omits a required project or submodule tree")
            expected_names = {prefix + "SOURCE_MANIFEST.json"}
            expected_names.update(
                prefix + item["path"]
                for item in tracked
                if isinstance(item, dict) and isinstance(item.get("path"), str)
            )
            expected_names.update(
                prefix + "release-evidence/agent-supply-chain/" + item["path"]
                for item in evidence
                if isinstance(item, dict) and isinstance(item.get("path"), str)
            )
            if set(names) != expected_names:
                errors.append("source archive members do not exactly match its manifest")
            for item in tracked:
                if not isinstance(item, dict):
                    errors.append("source archive tracked file entry is invalid")
                    break
                relative = item.get("path")
                digest = item.get("sha256")
                kind = item.get("type")
                if (
                    not isinstance(relative, str)
                    or not isinstance(digest, str)
                    or not SHA256.fullmatch(digest)
                    or kind not in {"file", "symlink"}
                ):
                    errors.append("source archive tracked file metadata is invalid")
                    break
                member = archive.getmember(prefix + relative)
                if kind == "symlink":
                    resolved_link = posixpath.normpath(
                        posixpath.join(posixpath.dirname(member.name), member.linkname)
                    )
                    if (
                        not member.issym()
                        or member.linkname.startswith("/")
                        or not resolved_link.startswith(prefix)
                    ):
                        errors.append("source archive contains an unsafe symlink")
                        break
                    actual = hashlib.sha256(member.linkname.encode("utf-8")).hexdigest()
                else:
                    if not member.isfile():
                        errors.append("source archive tracked member type is invalid")
                        break
                    stream = archive.extractfile(member)
                    if stream is None:
                        errors.append("source archive tracked member is not readable")
                        break
                    digest_builder = hashlib.sha256()
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest_builder.update(chunk)
                    actual = digest_builder.hexdigest()
                if actual != digest:
                    errors.append(f"source archive member hash mismatch: {relative}")
                    break
                expected = expected_sources.get(relative)
                if expected is None or expected != {"type": kind, "sha256": digest}:
                    errors.append(f"source archive differs from release checkout: {relative}")
                    break
            for item in evidence:
                if not isinstance(item, dict):
                    errors.append("source archive evidence entry is invalid")
                    break
                relative, digest = item.get("path"), item.get("sha256")
                if not isinstance(relative, str) or not isinstance(digest, str) or not SHA256.fullmatch(digest):
                    errors.append("source archive evidence metadata is invalid")
                    break
                member = archive.getmember(prefix + "release-evidence/agent-supply-chain/" + relative)
                stream = archive.extractfile(member)
                if stream is None:
                    errors.append("source archive evidence member is not readable")
                    break
                digest_builder = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest_builder.update(chunk)
                if digest_builder.hexdigest() != digest:
                    errors.append(f"source archive evidence hash mismatch: {relative}")
                    break
    except (KeyError, OSError, tarfile.TarError, json.JSONDecodeError):
        return ["source archive is unreadable or malformed"]
    return errors


def load_plan() -> dict:
    with PLAN_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


def validate_deliverable_format(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    try:
        def prefix(size: int) -> bytes:
            with path.open("rb") as stream:
                return stream.read(size)

        if suffix == ".pdf":
            with path.open("rb") as stream:
                header = stream.read(8)
                stream.seek(max(0, path.stat().st_size - 2048))
                trailer = stream.read()
            return [] if header.startswith(b"%PDF-") and b"%%EOF" in trailer else [f"invalid PDF structure: {path.name}"]
        if suffix in {".docx", ".pptx"}:
            required = (
                {"[Content_Types].xml", "word/document.xml"}
                if suffix == ".docx"
                else {"[Content_Types].xml", "ppt/presentation.xml"}
            )
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                if (
                    len(names) != len(set(names))
                    or any(name.startswith("/") or ".." in Path(name).parts for name in names)
                    or not required.issubset(names)
                    or archive.testzip() is not None
                ):
                    return [f"invalid {suffix[1:].upper()} structure: {path.name}"]
            return []
        if suffix == ".mp4":
            header = prefix(32)
            return [] if len(header) >= 12 and header[4:8] == b"ftyp" else [f"invalid MP4 structure: {path.name}"]
        if suffix == ".avi":
            header = prefix(12)
            return [] if header[:4] == b"RIFF" and header[8:12] == b"AVI " else [f"invalid AVI structure: {path.name}"]
        if suffix == ".wmv":
            asf = bytes.fromhex("3026b2758e66cf11a6d900aa0062ce6c")
            return [] if prefix(16) == asf else [f"invalid WMV structure: {path.name}"]
        if suffix == ".deb":
            return [] if prefix(8) == b"!<arch>\n" else [f"invalid Debian package structure: {path.name}"]
        if suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                if (
                    not names
                    or len(names) != len(set(names))
                    or any(name.startswith("/") or ".." in Path(name).parts for name in names)
                    or archive.testzip() is not None
                ):
                    return [f"invalid ZIP structure: {path.name}"]
            return []
        if suffix == ".sha256":
            match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)\r?\n?", path.read_text(encoding="ascii"))
            artifact = path.with_suffix("")
            if (
                match is None
                or match.group(2) != artifact.name
                or not artifact.is_file()
                or match.group(1) != sha256(artifact)
            ):
                return [f"invalid or mismatched SHA-256 file: {path.name}"]
            return []
        if suffix == ".sig":
            checksum = path.with_suffix("")
            checksum_errors = validate_deliverable_format(checksum)
            if checksum_errors:
                return checksum_errors
            digest = checksum.read_text(encoding="ascii").split()[0]
            with tempfile.NamedTemporaryFile("w", encoding="ascii") as stream:
                stream.write(digest + "\n")
                stream.flush()
                result = subprocess.run(
                    [
                        "openssl", "pkeyutl", "-verify", "-pubin", "-rawin",
                        "-in", stream.name,
                        "-inkey", str(ROOT / "build/release/keys/pixiu-release-ed25519.pub"),
                        "-sigfile", str(path),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            return [] if result.returncode == 0 else [f"invalid release signature: {path.name}"]
    except (OSError, UnicodeError, subprocess.SubprocessError, zipfile.BadZipFile):
        return [f"unreadable deliverable format: {path.name}"]
    return []


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


def validate_raw_evidence_archive(archive: Path, package: Path) -> list[str]:
    result = subprocess.run(
        [
            sys.executable,
            str(SUBMISSION_ROOT / "build_evidence_archive.py"),
            "--validate",
            "--root",
            str(ROOT),
            "--package",
            str(package),
            "--output",
            str(archive),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return [] if result.returncode == 0 else ["raw evidence archive failed policy validation"]


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
    expected_ids = [f"D-{number:02d}" for number in range(1, 6)] + [
        f"A-{number:02d}" for number in range(1, 6)
    ] + ["R-01"]
    if ids != expected_ids:
        errors.append("deliverables must contain official D-01..D-05, D-02 annexes A-01..A-05, and R-01")

    paths = [path for item in plan.get("deliverables", []) for path in item.get("paths", [])]
    if len(paths) != len(set(paths)):
        errors.append("deliverable paths must be unique")
    external_paths = [item.get("path", "") for item in plan.get("external_materials", [])]
    top_levels = {
        Path(path).parts[0]
        for path in paths + external_paths
        if isinstance(path, str) and Path(path).parts
    }
    if top_levels != OFFICIAL_TOP_LEVEL:
        errors.append("all submission files must be nested under the five official top-level categories")
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
            final_path = FINAL_ROOT / name / relative
            if not final_path.is_file():
                errors.append(f"missing final deliverable: {relative}")
            else:
                errors.extend(validate_deliverable_format(final_path))
        for item in plan.get("external_materials", []):
            relative = item.get("path", "")
            external_path = FINAL_ROOT / name / relative
            if not relative or not external_path.is_file():
                errors.append(f"missing external material: {relative}")
            else:
                errors.extend(validate_deliverable_format(external_path))
        evidence_path = FINAL_ROOT / name / FINAL_DEVICE_EVIDENCE
        package_paths = [
            FINAL_ROOT / name / relative
            for relative in paths
            if relative.startswith("04-部署文档/01-可安装软件/") and relative.endswith(".deb")
        ]
        if evidence_path.is_file() and len(package_paths) == 1 and package_paths[0].is_file():
            errors.extend(
                validate_final_device_evidence(
                    evidence_path,
                    release_commit=commit if isinstance(commit, str) else "",
                    candidate_package=package_paths[0],
                )
            )
        raw_evidence = FINAL_ROOT / name / RAW_EVIDENCE_ARCHIVE
        if raw_evidence.is_file() and len(package_paths) == 1 and package_paths[0].is_file():
            errors.extend(validate_raw_evidence_archive(raw_evidence, package_paths[0]))
        source_archive = FINAL_ROOT / name / SOURCE_ARCHIVE
        if source_archive.is_file():
            errors.extend(
                validate_source_archive(
                    source_archive,
                    release_commit=commit if isinstance(commit, str) else "",
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
