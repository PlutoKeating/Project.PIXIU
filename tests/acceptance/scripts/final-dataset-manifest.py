#!/usr/bin/env python3
"""Freeze the Appendix-A-derived acceptance corpus and bind it to a release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OFFICIAL_SOURCE = Path("docs/OriginProblemDescription.md")
OFFICIAL_SOURCE_SHA256 = "e8f35ef4d537d2f85c338111d8f88e64fe9538eb8073681d78c36479c3a147bf"
EVIDENCE_CLASS = "pixiu-final-dataset-manifest"
COMMIT = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
SENSITIVE = re.compile(
    r"(?i)(?:https?|git)://[^/\s:@]+:[^/\s@]+@|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{12,}|\bBearer\s+[A-Za-z0-9._~-]{12,}|"
    r"/(?:home|Users)/[^/\s]+/|[A-Z]:\\Users\\[^\\\s]+\\|"
    r"\b1[3-9][0-9]{9}\b|\b[1-9][0-9]{16}[0-9Xx]\b"
)
REQUIRED_CHECKS = {"source_legal", "schema_valid", "no_sensitive_data", "split_frozen"}


class EvidenceError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError("input is not readable JSON") from exc
    if not isinstance(value, dict):
        raise EvidenceError("input JSON must be an object")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise EvidenceError("input file is not readable") from exc


def release_identity(native: dict[str, Any]) -> dict[str, str]:
    release = native.get("release")
    candidate = native.get("candidate_package")
    if not (
        native.get("evidence_class") == "kylin-v11-native-sdk-product-lifecycle"
        and native.get("real_device_evidence") is True
        and native.get("status") == "pass"
        and isinstance(release, dict)
        and release.get("profile") == "kylin-v11-native-x86_64"
        and release.get("kysdk") == "ON"
        and release.get("install_strict") is True
        and isinstance(candidate, dict)
        and isinstance(release.get("git_commit"), str)
        and COMMIT.fullmatch(release["git_commit"])
        and isinstance(candidate.get("sha256"), str)
        and SHA256.fullmatch(candidate["sha256"])
    ):
        raise EvidenceError("native evidence is not a strict V11 release")
    return {"git_commit": release["git_commit"], "candidate_package_sha256": candidate["sha256"]}


def canonical_dataset(dataset: Any) -> tuple[dict[str, Any], bytes, str]:
    try:
        document = dataset.model_dump(mode="json")
    except AttributeError as exc:
        raise EvidenceError("dataset does not implement the validated model contract") from exc
    canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    rendered = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    return document, rendered, sha256_bytes(canonical)


def build_manifest(dataset: Any, native: dict[str, Any], official_sha256: str) -> tuple[bytes, dict[str, Any]]:
    if official_sha256 != OFFICIAL_SOURCE_SHA256:
        raise EvidenceError("official problem description digest changed")
    identity = release_identity(native)
    document, rendered, canonical_sha = canonical_dataset(dataset)
    cases = document.get("cases")
    fixtures = document.get("fixtures")
    if not isinstance(cases, list) or not isinstance(fixtures, list):
        raise EvidenceError("dataset fixtures or cases are missing")
    case_counts = {kind: sum(case.get("task") == kind for case in cases if isinstance(case, dict)) for kind in ("retrieval", "preference", "conflict")}
    case_ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if not (
        document.get("profile") == "acceptance"
        and document.get("retrieval_repetitions", 0) >= 20
        and len(fixtures) >= 50
        and case_counts == {"retrieval": 50, "preference": 15, "conflict": 25}
        and len(case_ids) == 90
        and len(set(case_ids)) == 90
    ):
        raise EvidenceError("reference dataset is not the frozen 90-case acceptance corpus")
    if SENSITIVE.search(rendered.decode("utf-8")):
        raise EvidenceError("dataset contains a sensitive-looking value")
    split_sha = sha256_bytes(json.dumps(case_ids, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    manifest = {
        "evidence_schema": 1,
        "evidence_class": EVIDENCE_CLASS,
        "real_device_evidence": False,
        "status": "pass",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "release": identity,
        "checks": {name: "passed" for name in sorted(REQUIRED_CHECKS)},
        "dataset": {
            "name": document["name"],
            "profile": "acceptance",
            "sha256": canonical_sha,
            "artifact_sha256": sha256_bytes(rendered),
            "schema_version": document["schema_version"],
            "fixture_count": len(fixtures),
            "case_count": len(cases),
            "case_counts": case_counts,
            "retrieval_repetitions": document["retrieval_repetitions"],
        },
        "split": {
            "policy": "frozen-test-only",
            "train_count": 0,
            "validation_count": 0,
            "test_count": len(cases),
            "test_case_ids_sha256": split_sha,
        },
        "provenance": {
            "kind": "team-authored-synthetic-corpus",
            "derived_from": "competition Appendix A household-expense scenario",
            "official_source": OFFICIAL_SOURCE.as_posix(),
            "official_source_sha256": official_sha256,
            "third_party_dataset": False,
            "license_obligation": "PIXIU project source license; no third-party dataset content",
        },
    }
    return rendered, manifest


def validate_manifest(value: dict[str, Any]) -> None:
    release = value.get("release")
    dataset = value.get("dataset")
    split = value.get("split")
    provenance = value.get("provenance")
    checks = value.get("checks")
    if not all(isinstance(item, dict) for item in (release, dataset, split, provenance, checks)):
        raise EvidenceError("dataset manifest is incomplete")
    if not (
        value.get("evidence_schema") == 1
        and value.get("evidence_class") == EVIDENCE_CLASS
        and value.get("real_device_evidence") is False
        and value.get("status") == "pass"
        and isinstance(release.get("git_commit"), str) and COMMIT.fullmatch(release["git_commit"])
        and isinstance(release.get("candidate_package_sha256"), str) and SHA256.fullmatch(release["candidate_package_sha256"])
        and set(checks) == REQUIRED_CHECKS and all(checks[name] == "passed" for name in REQUIRED_CHECKS)
        and dataset.get("profile") == "acceptance"
        and dataset.get("case_counts") == {"retrieval": 50, "preference": 15, "conflict": 25}
        and dataset.get("case_count") == 90 and dataset.get("fixture_count") == 50
        and dataset.get("retrieval_repetitions") >= 20
        and all(isinstance(dataset.get(name), str) and SHA256.fullmatch(dataset[name]) for name in ("sha256", "artifact_sha256"))
        and split.get("policy") == "frozen-test-only"
        and split.get("train_count") == 0 and split.get("validation_count") == 0 and split.get("test_count") == 90
        and isinstance(split.get("test_case_ids_sha256"), str) and SHA256.fullmatch(split["test_case_ids_sha256"])
        and provenance.get("kind") == "team-authored-synthetic-corpus"
        and provenance.get("official_source_sha256") == OFFICIAL_SOURCE_SHA256
        and provenance.get("third_party_dataset") is False
    ):
        raise EvidenceError("dataset manifest does not pass its public contract")


def verify_repo(root: Path, commit: str) -> None:
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise EvidenceError("clean Git release checkout is required") from exc
    if head != commit or status:
        raise EvidenceError("dataset export must run from the clean release commit")


def write_pair(dataset_path: Path, dataset_bytes: bytes, manifest_path: Path, manifest: dict[str, Any]) -> None:
    if dataset_path.exists() or manifest_path.exists() or dataset_path.resolve() == manifest_path.resolve():
        raise EvidenceError("dataset outputs must be distinct and must not already exist")
    for path in (dataset_path, manifest_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    pending: list[tuple[Path, Path]] = []
    try:
        for path, content in (
            (dataset_path, dataset_bytes),
            (manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"),
        ):
            descriptor, name = tempfile.mkstemp(prefix=".pixiu-dataset-", dir=path.parent)
            with open(descriptor, "wb", closefd=True) as stream:
                stream.write(content)
            pending.append((Path(name), path))
        for temporary, target in pending:
            temporary.replace(target)
    finally:
        for temporary, _ in pending:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "validate"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--native-evidence", type=Path)
    parser.add_argument("--dataset-output", type=Path)
    parser.add_argument("--manifest-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.mode == "validate":
            manifest = read_json(args.manifest_output)
            validate_manifest(manifest)
            if args.dataset_output is not None and sha256_file(args.dataset_output) != manifest["dataset"]["artifact_sha256"]:
                raise EvidenceError("frozen dataset file does not match its manifest")
        else:
            if args.native_evidence is None or args.dataset_output is None:
                raise EvidenceError("--native-evidence and --dataset-output are required")
            native = read_json(args.native_evidence)
            identity = release_identity(native)
            verify_repo(args.root.resolve(), identity["git_commit"])
            official_sha = sha256_file(args.root.resolve() / OFFICIAL_SOURCE)
            sys.path.insert(0, str(args.root.resolve()))
            from backend.foundation.eval.reference import build_reference_dataset
            dataset_bytes, manifest = build_manifest(build_reference_dataset(), native, official_sha)
            validate_manifest(manifest)
            write_pair(args.dataset_output, dataset_bytes, args.manifest_output, manifest)
        print("Final dataset manifest: PASS")
        return 0
    except EvidenceError as exc:
        print(f"Final dataset manifest: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
