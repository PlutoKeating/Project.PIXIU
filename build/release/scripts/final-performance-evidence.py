#!/usr/bin/env python3
"""Bind final V11 metrics and the required memory ablation to one release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVIDENCE_CLASS = "kylin-v11-final-performance"
COMMIT = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
REQUIRED_CHECKS = {
    "preference_accuracy",
    "knowledge_recall",
    "retrieval_p95",
    "conflict_accuracy",
    "comparison_and_ablation",
}
METRICS = {
    "preference_accuracy": (">=", 0.85, 15),
    "knowledge_recall_at_k": (">=", 0.85, 50),
    "retrieval_p95_ms": ("<=", 500.0, 1000),
    "conflict_accuracy": (">=", 0.88, 25),
}
VARIANTS = {"no_memory", "single_device_memory", "distributed_memory"}


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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise EvidenceError("input file is not readable") from exc
    return digest.hexdigest()


def write_json(path: Path, value: dict[str, Any], overwrite: bool) -> None:
    path = path.resolve()
    if path.exists() and not overwrite:
        raise EvidenceError("output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def _identity(commit: object, package_sha: object, label: str) -> dict[str, str]:
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise EvidenceError(f"{label} release commit is invalid")
    if not isinstance(package_sha, str) or not SHA256.fullmatch(package_sha):
        raise EvidenceError(f"{label} candidate package digest is invalid")
    return {"git_commit": commit, "candidate_package_sha256": package_sha}


def native_identity(value: dict[str, Any]) -> dict[str, str]:
    sections = [value.get(name) for name in ("release", "candidate_package", "capabilities", "checks")]
    if not all(isinstance(section, dict) for section in sections):
        raise EvidenceError("native SDK evidence is incomplete")
    release, candidate, capabilities, checks = sections
    if not (
        value.get("evidence_class") == "kylin-v11-native-sdk-product-lifecycle"
        and value.get("real_device_evidence") is True
        and value.get("status") == "pass"
        and release.get("profile") == "kylin-v11-native-x86_64"
        and release.get("kysdk") == "ON"
        and release.get("install_strict") is True
        and capabilities.get("contest_ready") is True
        and all(checks.get(name) == "passed" for name in ("memory_write", "vector_search", "vector_delete"))
    ):
        raise EvidenceError("native SDK evidence is not a passing strict V11 lifecycle")
    return _identity(release.get("git_commit"), candidate.get("sha256"), "native SDK")


def derived_identity(value: dict[str, Any], evidence_class: str, label: str) -> dict[str, str]:
    release = value.get("release")
    if not (
        value.get("evidence_class") == evidence_class
        and value.get("status") == "pass"
        and isinstance(value.get("checks"), dict)
        and isinstance(release, dict)
        and all(result == "passed" for result in value["checks"].values())
    ):
        raise EvidenceError(f"{label} evidence is not passing")
    return _identity(release.get("git_commit"), release.get("candidate_package_sha256"), label)


def validate_dataset(value: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    identity = derived_identity(value, "pixiu-final-dataset-manifest", "dataset")
    dataset = value.get("dataset")
    if not isinstance(dataset, dict):
        raise EvidenceError("dataset manifest lacks dataset metadata")
    counts = dataset.get("case_counts")
    if not (
        dataset.get("profile") == "acceptance"
        and isinstance(dataset.get("name"), str) and dataset["name"]
        and isinstance(dataset.get("sha256"), str) and SHA256.fullmatch(dataset["sha256"])
        and dataset.get("retrieval_repetitions", 0) >= 20
        and isinstance(counts, dict)
        and counts.get("retrieval", 0) >= 50
        and counts.get("preference", 0) >= 15
        and counts.get("conflict", 0) >= 25
    ):
        raise EvidenceError("dataset manifest does not describe the frozen acceptance corpus")
    return identity, dataset


def validate_eval_report(value: dict[str, Any], dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    outcomes = value.get("outcomes")
    metrics = value.get("metrics")
    if not (
        value.get("schema_version") == "1.0"
        and value.get("overall_status") == "PASS"
        and value.get("dataset_profile") == "acceptance"
        and value.get("dataset_name") == dataset["name"]
        and value.get("dataset_sha256") == dataset["sha256"]
        and isinstance(outcomes, list)
        and len(outcomes) >= 90
        and isinstance(metrics, list)
    ):
        raise EvidenceError("evaluation report is not a complete passing acceptance run")
    by_name = {item.get("name"): item for item in metrics if isinstance(item, dict)}
    selected: dict[str, dict[str, Any]] = {}
    for name, (comparison, target, minimum_samples) in METRICS.items():
        metric = by_name.get(name)
        if not (
            isinstance(metric, dict)
            and metric.get("comparison") == comparison
            and metric.get("target") == target
            and metric.get("status") == "PASS"
            and isinstance(metric.get("value"), (int, float))
            and not isinstance(metric.get("value"), bool)
            and isinstance(metric.get("denominator"), int)
            and metric["denominator"] >= minimum_samples
            and ((comparison == ">=" and metric["value"] >= target) or (comparison == "<=" and metric["value"] <= target))
        ):
            raise EvidenceError(f"final metric is missing or below its contract: {name}")
        selected[name] = {
            "value": metric["value"],
            "target": target,
            "comparison": comparison,
            "sample_count": metric["denominator"],
        }
    return selected


def validate_comparison(value: dict[str, Any], identity: dict[str, str], dataset_sha: str) -> list[dict[str, Any]]:
    release = value.get("release")
    if not isinstance(release, dict):
        raise EvidenceError("comparison release identity is missing")
    comparison_identity = _identity(
        release.get("git_commit"),
        release.get("candidate_package_sha256"),
        "comparison",
    )
    variants = value.get("variants")
    if not (
        value.get("schema_version") == 1
        and value.get("status") == "pass"
        and comparison_identity == identity
        and value.get("dataset_sha256") == dataset_sha
        and isinstance(value.get("task_set_sha256"), str)
        and SHA256.fullmatch(value["task_set_sha256"])
        and isinstance(variants, list)
        and {item.get("name") for item in variants if isinstance(item, dict)} == VARIANTS
        and len(variants) == 3
    ):
        raise EvidenceError("comparison matrix identity or variants are invalid")
    normalized = []
    for variant in variants:
        metrics = variant.get("metrics") if isinstance(variant, dict) else None
        if not (
            isinstance(metrics, dict)
            and set(metrics) == {"task_success_rate", "mean_turns"}
            and isinstance(variant.get("sample_count"), int)
            and variant["sample_count"] >= 30
            and isinstance(metrics.get("task_success_rate"), (int, float))
            and not isinstance(metrics.get("task_success_rate"), bool)
            and 0 <= metrics["task_success_rate"] <= 1
            and isinstance(metrics.get("mean_turns"), (int, float))
            and not isinstance(metrics.get("mean_turns"), bool)
            and metrics["mean_turns"] > 0
        ):
            raise EvidenceError("comparison variant has incomplete raw metrics")
        normalized.append({
            "name": variant["name"],
            "sample_count": variant["sample_count"],
            "metrics": {
                "task_success_rate": metrics["task_success_rate"],
                "mean_turns": metrics["mean_turns"],
            },
        })
    return sorted(normalized, key=lambda item: item["name"])


def build_evidence(paths: dict[str, Path]) -> dict[str, Any]:
    native = read_json(paths["native"])
    agent = read_json(paths["agent"])
    dataset_manifest = read_json(paths["dataset"])
    report = read_json(paths["report"])
    comparison = read_json(paths["comparison"])
    identity = native_identity(native)
    if derived_identity(agent, "kylin-v11-agent-lifecycle", "Agent") != identity:
        raise EvidenceError("Agent and native SDK evidence identify different releases")
    dataset_identity, dataset = validate_dataset(dataset_manifest)
    if dataset_identity != identity:
        raise EvidenceError("dataset and native SDK evidence identify different releases")
    metrics = validate_eval_report(report, dataset)
    variants = validate_comparison(comparison, identity, dataset["sha256"])
    return {
        "evidence_schema": 1,
        "evidence_class": EVIDENCE_CLASS,
        "real_device_evidence": True,
        "status": "pass",
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "release": identity,
        "checks": {name: "passed" for name in sorted(REQUIRED_CHECKS)},
        "dataset": {"name": dataset["name"], "sha256": dataset["sha256"], "profile": "acceptance"},
        "metrics": metrics,
        "comparison": {"variants": variants, "task_set_sha256": comparison["task_set_sha256"]},
        "source_sha256": {name: file_sha256(path) for name, path in sorted(paths.items())},
    }


def validate_final(value: dict[str, Any]) -> None:
    release = value.get("release", {})
    checks = value.get("checks")
    metrics = value.get("metrics")
    comparison = value.get("comparison", {})
    sources = value.get("source_sha256")
    _identity(release.get("git_commit"), release.get("candidate_package_sha256"), "final performance")
    if not (
        value.get("evidence_schema") == 1
        and value.get("evidence_class") == EVIDENCE_CLASS
        and value.get("real_device_evidence") is True
        and value.get("status") == "pass"
        and isinstance(checks, dict) and set(checks) == REQUIRED_CHECKS
        and all(checks[name] == "passed" for name in REQUIRED_CHECKS)
        and isinstance(metrics, dict) and set(metrics) == set(METRICS)
        and isinstance(comparison.get("variants"), list)
        and {item.get("name") for item in comparison["variants"] if isinstance(item, dict)} == VARIANTS
        and isinstance(sources, dict) and set(sources) == {"agent", "comparison", "dataset", "native", "report"}
        and all(isinstance(item, str) and SHA256.fullmatch(item) for item in sources.values())
    ):
        raise EvidenceError("final performance evidence does not pass its public contract")
    for name, (expected_comparison, target, minimum_samples) in METRICS.items():
        metric = metrics[name]
        if not (
            isinstance(metric, dict)
            and set(metric) == {"value", "target", "comparison", "sample_count"}
            and metric.get("comparison") == expected_comparison
            and metric.get("target") == target
            and isinstance(metric.get("sample_count"), int)
            and metric["sample_count"] >= minimum_samples
            and isinstance(metric.get("value"), (int, float))
            and not isinstance(metric.get("value"), bool)
            and (
                (expected_comparison == ">=" and metric["value"] >= target)
                or (expected_comparison == "<=" and metric["value"] <= target)
            )
        ):
            raise EvidenceError(f"final performance metric is invalid: {name}")
    if not (
        isinstance(comparison.get("task_set_sha256"), str)
        and SHA256.fullmatch(comparison["task_set_sha256"])
        and len(comparison["variants"]) == 3
        and all(
            isinstance(item, dict)
            and isinstance(item.get("sample_count"), int)
            and item["sample_count"] >= 30
            and isinstance(item.get("metrics"), dict)
            and set(item["metrics"]) == {"task_success_rate", "mean_turns"}
            for item in comparison["variants"]
        )
    ):
        raise EvidenceError("final comparison summary is invalid")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "validate"))
    parser.add_argument("--native-evidence", type=Path)
    parser.add_argument("--agent-evidence", type=Path)
    parser.add_argument("--dataset-manifest", type=Path)
    parser.add_argument("--eval-report", type=Path)
    parser.add_argument("--comparison", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        if args.mode == "validate":
            validate_final(read_json(args.output))
        else:
            inputs = {
                "native": args.native_evidence,
                "agent": args.agent_evidence,
                "dataset": args.dataset_manifest,
                "report": args.eval_report,
                "comparison": args.comparison,
            }
            if any(path is None for path in inputs.values()):
                raise EvidenceError("all five evidence inputs are required")
            evidence = build_evidence(inputs)  # type: ignore[arg-type]
            validate_final(evidence)
            write_json(args.output, evidence, args.overwrite)
        print("Final performance evidence: PASS")
        return 0
    except EvidenceError as exc:
        print(f"Final performance evidence: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
