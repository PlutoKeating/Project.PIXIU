#!/usr/bin/env python3
"""Build and validate the fail-closed A-02 raw evidence archive."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
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
DEEP_VALIDATORS = {
    "native_sdk": ("build/release/scripts/native-sdk-smoke.py", "validate_evidence"),
    "agent_lifecycle": ("build/release/scripts/agent-lifecycle-evidence.py", "validate_final"),
    "performance": ("build/release/scripts/final-performance-evidence.py", "validate_final"),
    "dataset": ("build/release/scripts/final-dataset-manifest.py", "validate_manifest"),
    "install_update": ("build/release/scripts/install-update-evidence.py", "validate_final"),
    "three_device": ("build/release/scripts/three-device-evidence.py", "validate_final_report"),
    "agent_supply_chain": ("build/release/scripts/audit-agent-supply-chain.py", "validate_report"),
}


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


def validate_deep_record(name: str, document: dict[str, Any]) -> list[str]:
    validator = DEEP_VALIDATORS.get(name)
    if validator is None:
        return []
    relative_path, function_name = validator
    script = ROOT / relative_path
    try:
        spec = importlib.util.spec_from_file_location(f"pixiu_{name}_validator", script)
        if spec is None or spec.loader is None:
            raise RuntimeError("validator cannot be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        getattr(module, function_name)(document)
    except Exception as exc:
        return [f"{name}: deep evidence validation failed: {exc}"]
    return []


def validate_embedded_sources(
    documents: dict[str, dict[str, Any]], attachment_paths: list[Path]
) -> list[str]:
    try:
        performance = documents["performance"]
        dataset_manifest = documents["dataset"]
        sources = performance["source_sha256"]
        by_digest = {sha256_file(path): path for path in attachment_paths}
        dataset_path = by_digest[nested(dataset_manifest, ["dataset", "artifact_sha256"])]
        report_path = by_digest[sources["report"]]
        comparison_path = by_digest[sources["comparison"]]

        dataset_document = read_json(dataset_path)
        canonical_dataset = json.dumps(
            dataset_document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        if hashlib.sha256(canonical_dataset).hexdigest() != nested(
            dataset_manifest, ["dataset", "sha256"]
        ):
            raise ValueError("frozen dataset canonical digest mismatch")
        cases = dataset_document.get("cases")
        fixtures = dataset_document.get("fixtures")
        if not isinstance(cases, list) or not isinstance(fixtures, list):
            raise ValueError("frozen dataset structure is incomplete")
        counts = {
            kind: sum(
                isinstance(case, dict) and case.get("task") == kind for case in cases
            )
            for kind in ("retrieval", "preference", "conflict")
        }
        ids = [case.get("id") for case in cases if isinstance(case, dict)]
        if not (
            dataset_document.get("profile") == "acceptance"
            and dataset_document.get("name") == nested(dataset_manifest, ["dataset", "name"])
            and dataset_document.get("retrieval_repetitions", 0) >= 20
            and len(fixtures) == 50
            and counts == {"retrieval": 50, "preference": 15, "conflict": 25}
            and len(ids) == 90
            and len(set(ids)) == 90
        ):
            raise ValueError("frozen dataset content does not match its manifest")

        relative_path, _ = DEEP_VALIDATORS["performance"]
        spec = importlib.util.spec_from_file_location(
            "pixiu_embedded_performance_validator", ROOT / relative_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("performance validator cannot be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report_document = read_json(report_path)
        selected_metrics = module.validate_eval_report(
            report_document,
            dataset_manifest["dataset"],
            identity={
                "git_commit": nested(performance, ["release", "git_commit"]),
                "candidate_package_sha256": nested(
                    performance, ["release", "candidate_package_sha256"]
                ),
            },
            native_evidence_sha256=sources["native"],
        )
        recomputed_metrics = recompute_primary_metrics(
            dataset_document, report_document
        )
        for name, value in recomputed_metrics.items():
            if not math.isclose(
                float(selected_metrics[name]["value"]), value, rel_tol=0.0, abs_tol=1e-9
            ):
                raise ValueError(f"reported metric does not match raw outcomes: {name}")
        identity = {
            "git_commit": nested(performance, ["release", "git_commit"]),
            "candidate_package_sha256": nested(
                performance, ["release", "candidate_package_sha256"]
            ),
        }
        selected_variants = module.validate_comparison(
            read_json(comparison_path), identity, dataset_manifest["dataset"]["sha256"],
            sources["dataset"],
        )
        if performance.get("metrics") != selected_metrics:
            raise ValueError("performance summary does not match the archived evaluation report")
        if nested(performance, ["comparison", "variants"]) != selected_variants:
            raise ValueError("performance summary does not match the archived comparison matrix")
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        return [f"embedded source validation failed: {exc}"]
    return []


def validate_ablation_sources(
    documents: dict[str, dict[str, Any]], attachment_paths: list[Path]
) -> list[str]:
    """Rebuild the Agent ablation chain from archived reports and snapshots."""
    try:
        performance = documents["performance"]
        performance_sources = performance["source_sha256"]
        by_digest = {sha256_file(path): path for path in attachment_paths}
        comparison_path = by_digest[performance_sources["comparison"]]
        matrix = read_json(comparison_path)
        spec = importlib.util.spec_from_file_location(
            "pixiu_embedded_ablation_validator",
            ROOT / "build/release/scripts/agent-memory-ablation.py",
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("ablation validator cannot be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.validate_matrix(matrix)
        task_path = by_digest[matrix["task_set_sha256"]]
        tasks = module.validate_task_set(read_json(task_path))
        expected_task_ids = {task["id"] for task in tasks}
        release = matrix["release"]
        variant_sources = matrix["source_variant_sha256"]
        rebuilt_variants = []
        distributed_snapshots: list[dict[str, Any]] = []
        for variant in sorted(module.VARIANTS):
            report_path = by_digest[variant_sources[variant]]
            report = read_json(report_path)
            module.validate_variant_report(report)
            if not (
                report["variant"] == variant
                and report["release"] == release
                and report["task_set_sha256"] == matrix["task_set_sha256"]
                and {item["task_id"] for item in report["outcomes"]} == expected_task_ids
            ):
                raise ValueError(f"ablation variant does not bind the matrix task set: {variant}")
            sources = report.get("source_sha256")
            if not isinstance(sources, dict) or set(sources) != {"native", "teach_snapshot", "recall_snapshot"}:
                raise ValueError(f"ablation variant source map is incomplete: {variant}")
            if sources["native"] != performance_sources["native"]:
                raise ValueError(f"ablation variant identifies another native run: {variant}")
            snapshots = []
            for phase, role in (("teach_snapshot", "teach"), ("recall_snapshot", "recall")):
                snapshot = read_json(by_digest[sources[phase]])
                module.validate_snapshot(snapshot, variant, release, role)
                snapshots.append(snapshot)
                if snapshot["native_evidence_sha256"] != performance_sources["native"]:
                    raise ValueError(f"ablation snapshot identifies another native run: {variant}")
                node_sha = snapshot.get("node_manifest_sha256")
                if variant == "distributed_memory":
                    node_manifest = read_json(by_digest[node_sha])
                    module._validate_node_manifest(node_manifest, release)
                    if node_manifest.get("run_id") != snapshot.get("topology_run_id"):
                        raise ValueError("distributed snapshot and node manifest run differ")
            if variant == "distributed_memory":
                if (
                    snapshots[0]["node_identity_digest"] == snapshots[1]["node_identity_digest"]
                    or snapshots[0]["topology_run_id"] != snapshots[1]["topology_run_id"]
                ):
                    raise ValueError("distributed ablation is not a cross-device recall")
                distributed_snapshots = snapshots
            rebuilt_variants.append({
                "name": variant,
                "sample_count": report["sample_count"],
                "metrics": report["metrics"],
            })
        if sorted(rebuilt_variants, key=lambda item: item["name"]) != matrix["variants"]:
            raise ValueError("ablation matrix does not reproduce from variant reports")
        if len(distributed_snapshots) != 2:
            raise ValueError("distributed ablation snapshots are missing")
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        return [f"ablation source validation failed: {exc}"]
    return []


def validate_install_sources(
    documents: dict[str, dict[str, Any]], attachment_paths: list[Path]
) -> list[str]:
    try:
        install = documents["install_update"]
        sources = install["source_sha256"]
        by_digest = {sha256_file(path): path for path in attachment_paths}
        relative_path, _ = DEEP_VALIDATORS["install_update"]
        spec = importlib.util.spec_from_file_location(
            "pixiu_embedded_install_validator", ROOT / relative_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("install/update validator cannot be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        package_sha = nested(install, ["release", "candidate_package_sha256"])
        for operation in sorted(module.OPERATIONS):
            operation_path = by_digest[sources[operation]]
            operation_document = read_json(operation_path)
            module.validate_operation(operation_document, package_sha)
            if operation_document.get("operation") != operation:
                raise ValueError("install operation source kind mismatch")
            operation_sources = operation_document.get("source_sha256")
            if not isinstance(operation_sources, dict):
                raise ValueError("install operation source map is missing")
            for source_name in ("before", "after", "proof"):
                source_path = by_digest[operation_sources[source_name]]
                if source_name != "proof":
                    snapshot = read_json(source_path)
                    module.validate_snapshot(snapshot)
                    if snapshot != operation_document[source_name]:
                        raise ValueError("install operation snapshot does not match attachment")
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        return [f"embedded install/update validation failed: {exc}"]
    return []


def validate_three_device_sources(
    documents: dict[str, dict[str, Any]], attachment_paths: list[Path]
) -> list[str]:
    try:
        final = documents["three_device"]
        by_digest = {sha256_file(path): path for path in attachment_paths}
        relative_path, _ = DEEP_VALIDATORS["three_device"]
        spec = importlib.util.spec_from_file_location(
            "pixiu_embedded_three_device_validator", ROOT / relative_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("three-device validator cannot be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        initial_path = by_digest[final["initial_topology_evidence_sha256"]]
        final_path = by_digest[final["final_topology_evidence_sha256"]]
        scenario_paths = [by_digest[digest] for digest in final["source_scenario_sha256"]]

        rebuilt = module.validate_final_scenario_suite(
            initial_topology_path=initial_path,
            final_topology_path=final_path,
            scenario_paths=scenario_paths,
        )
        for field in (
            "run_id", "release", "initial_topology_evidence_sha256",
            "final_topology_evidence_sha256", "source_scenario_sha256",
            "scenarios", "checks", "remaining_required_scenarios",
        ):
            if rebuilt.get(field) != final.get(field):
                raise ValueError(f"three-device final report differs from sources: {field}")

        for topology_path in (initial_path, final_path):
            topology = read_json(topology_path)
            node_paths = [
                by_digest[digest] for digest in topology["source_node_manifest_sha256"]
            ]
            rebuilt_topology = module.validate_cluster(node_paths)
            for field in ("run_id", "release", "topology", "source_node_manifest_sha256"):
                if rebuilt_topology.get(field) != topology.get(field):
                    raise ValueError(f"three-device topology differs from nodes: {field}")

        validators = {
            "concurrent-update-and-conflict-resolution": module.validate_concurrency_scenario,
            "offline-write-and-reconnect": module.validate_offline_scenario,
            "private-scope-non-propagation": module.validate_privacy_scenario,
            "tombstone-propagation-and-no-resurrection": module.validate_tombstone_scenario,
        }
        for scenario_path in scenario_paths:
            scenario = read_json(scenario_path)
            checkpoint_paths = [
                by_digest[digest] for digest in scenario["source_checkpoint_sha256"]
            ]
            rebuilt_scenario = validators[scenario["scenario"]](
                topology_path=initial_path, checkpoint_paths=checkpoint_paths
            )
            for field in (
                "run_id", "release", "topology_evidence_sha256", "source_checkpoint_sha256",
                "scenario", "checks", "remaining_required_scenarios",
            ):
                if rebuilt_scenario.get(field) != scenario.get(field):
                    raise ValueError(f"three-device scenario differs from checkpoints: {field}")
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        return [f"embedded three-device validation failed: {exc}"]
    return []


def validate_supply_chain_sources(
    documents: dict[str, dict[str, Any]], attachment_paths: list[Path]
) -> list[str]:
    try:
        report = documents["agent_supply_chain"]
        policy = read_json(ROOT / "build/release/agent-supply-chain-policy.json")
        by_digest = {sha256_file(path): path for path in attachment_paths}
        evidence = report["evidence"]
        top_paths = {
            name: by_digest[item["sha256"]] for name, item in evidence.items()
        }
        host = read_json(top_paths["host_build"])
        wheelhouse = read_json(top_paths["runtime_wheelhouse"])
        sbom = read_json(top_paths["sbom"])
        notice = top_paths["notice"].read_text(encoding="utf-8")

        def bound_artifact(document: dict[str, Any], path_key: str, digest_key: str) -> Path:
            path = by_digest[document[digest_key]]
            if Path(str(document[path_key])).name != path.name:
                raise ValueError(f"supply-chain artifact filename mismatch: {path_key}")
            return path

        agent_policy = policy["components"]["kylin_agent"]
        runtime_policy = policy["components"]["agent_runtime"]
        if not (
            host.get("schema_version") == 1
            and host.get("source_commit") == agent_policy["source_commit"]
            and host.get("target_os") == policy["target_os"]
            and host.get("target_arch") in policy["target_architectures"]
            and host.get("rebuild_verified") is True
            and host.get("network_access_during_build") is False
        ):
            raise ValueError("archived Agent host build record is invalid")
        for path_key, digest_key in (
            ("artifact", "artifact_sha256"),
            ("source_archive", "source_archive_sha256"),
            ("build_log", "build_log_sha256"),
        ):
            bound_artifact(host, path_key, digest_key)

        packages = wheelhouse.get("packages")
        if not (
            wheelhouse.get("schema_version") == 1
            and wheelhouse.get("source_commit") == runtime_policy["source_commit"]
            and wheelhouse.get("target_os") == policy["target_os"]
            and wheelhouse.get("target_arch") in policy["target_architectures"]
            and bool(str(wheelhouse.get("python_abi", "")).strip())
            and wheelhouse.get("offline_install_verified") is True
            and wheelhouse.get("network_access_during_install") is False
            and isinstance(packages, list)
            and bool(packages)
            and set(policy["runtime_required_packages"]).issubset(
                {item.get("name") for item in packages if isinstance(item, dict)}
            )
        ):
            raise ValueError("archived Agent Runtime wheelhouse record is invalid")
        bound_artifact(wheelhouse, "lockfile", "lockfile_sha256")
        bound_artifact(wheelhouse, "offline_install_log", "offline_install_log_sha256")
        for package in packages:
            if not isinstance(package, dict):
                raise ValueError("archived Runtime package entry is invalid")
            wheel = bound_artifact(package, "filename", "sha256")
            if wheel.suffix != ".whl" or not package.get("name") or not package.get("version"):
                raise ValueError("archived Runtime wheel is invalid")

        sbom_packages = sbom.get("packages")
        if not (
            sbom.get("spdxVersion") == "SPDX-2.3"
            and sbom.get("SPDXID") == "SPDXRef-DOCUMENT"
            and sbom.get("dataLicense") == "CC0-1.0"
            and isinstance(sbom_packages, list)
            and bool(sbom_packages)
        ):
            raise ValueError("archived Agent SBOM is invalid")
        by_spdx = {
            item.get("SPDXID"): item for item in sbom_packages if isinstance(item, dict)
        }
        described = set(sbom.get("documentDescribes", []))
        extracted_licenses = {
            item.get("licenseId")
            for item in sbom.get("hasExtractedLicensingInfos", [])
            if isinstance(item, dict)
        }
        for component in policy["components"].values():
            item = by_spdx.get(component["spdx_id"])
            if not (
                component["spdx_id"] in described
                and isinstance(item, dict)
                and item.get("name") == component["package_name"]
                and item.get("versionInfo") == component["source_commit"]
                and item.get("licenseDeclared") == component["declared_license"]
                and item.get("downloadLocation") == component["source_url"]
                and (
                    not component["declared_license"].startswith("LicenseRef-")
                    or component["declared_license"] in extracted_licenses
                )
            ):
                raise ValueError("archived Agent component SBOM entry is invalid")
            for required in (
                component["package_name"], component["source_commit"],
                component["source_url"], component["declared_license"],
            ):
                if required not in notice:
                    raise ValueError("archived Agent NOTICE is incomplete")
        for wheel in packages:
            if not any(
                item.get("name") == wheel["name"]
                and item.get("versionInfo") == wheel["version"]
                and any(
                    checksum.get("algorithm") == "SHA256"
                    and checksum.get("checksumValue") == wheel["sha256"]
                    for checksum in item.get("checksums", [])
                    if isinstance(checksum, dict)
                )
                for item in sbom_packages
                if isinstance(item, dict)
            ):
                raise ValueError("archived Runtime wheel is absent from SBOM")
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError, UnicodeError) as exc:
        return [f"embedded Agent supply-chain validation failed: {exc}"]
    return []


def recompute_primary_metrics(
    dataset: dict[str, Any], report: dict[str, Any]
) -> dict[str, float]:
    cases = dataset.get("cases")
    outcomes = report.get("outcomes")
    repetitions = dataset.get("retrieval_repetitions")
    if not isinstance(cases, list) or not isinstance(outcomes, list):
        raise ValueError("dataset cases or report outcomes are missing")
    if not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError("dataset retrieval repetition count is invalid")
    case_map = {
        case.get("id"): case
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("id"), str)
    }
    outcome_map = {
        outcome.get("case_id"): outcome
        for outcome in outcomes
        if isinstance(outcome, dict) and isinstance(outcome.get("case_id"), str)
    }
    if len(case_map) != len(cases) or len(outcome_map) != len(outcomes) or set(case_map) != set(outcome_map):
        raise ValueError("report outcomes do not cover each frozen case exactly once")

    preference_total = preference_correct = 0
    retrieval_total = 0
    retrieval_recall = 0.0
    conflict_total = conflict_correct = 0
    latency_samples: list[float] = []
    for case_id, case in case_map.items():
        outcome = outcome_map[case_id]
        task = case.get("task")
        expected = case.get("expected")
        prediction = outcome.get("prediction")
        if (
            outcome.get("task") != task
            or outcome.get("error") is not None
            or not isinstance(expected, dict)
            or not isinstance(prediction, dict)
        ):
            raise ValueError(f"raw outcome is invalid: {case_id}")
        if task == "preference":
            preference_total += 1
            if set(prediction.get("labels", [])) == set(expected.get("labels", [])):
                preference_correct += 1
        elif task == "retrieval":
            retrieval_total += 1
            expected_ids = set(expected.get("knowledge_ids", []))
            actual_ids = prediction.get("knowledge_ids", [])
            top_k = expected.get("top_k", 1)
            if not expected_ids or not isinstance(actual_ids, list) or not isinstance(top_k, int):
                raise ValueError(f"retrieval outcome is invalid: {case_id}")
            retrieval_recall += len(set(actual_ids[:top_k]) & expected_ids) / len(expected_ids)
            samples = outcome.get("latency_samples_ms")
            if not (
                isinstance(samples, list)
                and len(samples) == repetitions
                and all(
                    isinstance(sample, (int, float))
                    and not isinstance(sample, bool)
                    and math.isfinite(float(sample))
                    and sample >= 0
                    for sample in samples
                )
            ):
                raise ValueError(f"retrieval latency samples are invalid: {case_id}")
            latency_samples.extend(float(sample) for sample in samples)
        elif task == "conflict":
            conflict_total += 1
            if prediction.get("resolution") == expected.get("resolution"):
                conflict_correct += 1
        else:
            raise ValueError(f"unknown frozen task kind: {case_id}")
    if not all((preference_total, retrieval_total, conflict_total, latency_samples)):
        raise ValueError("raw outcomes do not cover all metric families")
    ordered = sorted(latency_samples)
    p95 = ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]
    return {
        "preference_accuracy": preference_correct / preference_total,
        "knowledge_recall_at_k": retrieval_recall / retrieval_total,
        "retrieval_p95_ms": p95,
        "conflict_accuracy": conflict_correct / conflict_total,
    }


def validate_cross_references(
    documents: dict[str, dict[str, Any]],
    record_paths: dict[str, Path],
    attachment_paths: list[Path],
) -> list[str]:
    required = {"native_sdk", "agent_lifecycle", "performance", "dataset", "install_update"}
    if not required.issubset(documents) or not required.issubset(record_paths):
        return ["cross-reference validation is missing primary evidence records"]
    errors: list[str] = []
    record_digests = {name: sha256_file(path) for name, path in record_paths.items()}
    attachment_digests = {sha256_file(path) for path in attachment_paths}
    agent_native = nested(documents["agent_lifecycle"], ["release", "native_evidence_sha256"])
    if agent_native != record_digests["native_sdk"]:
        errors.append("agent_lifecycle: native evidence digest mismatch")

    sources = documents["performance"].get("source_sha256")
    if not isinstance(sources, dict) or set(sources) != {"native", "agent", "dataset", "report", "comparison"}:
        errors.append("performance: source digest map is incomplete")
    else:
        if len(set(sources.values())) != len(sources):
            errors.append("performance: source digests must identify distinct inputs")
        expected_records = {
            "native": record_digests["native_sdk"],
            "agent": record_digests["agent_lifecycle"],
            "dataset": record_digests["dataset"],
        }
        for source, digest in expected_records.items():
            if sources.get(source) != digest:
                errors.append(f"performance: {source} source digest mismatch")
        for source in ("report", "comparison"):
            if sources.get(source) not in attachment_digests:
                errors.append(f"performance: referenced {source} input is not archived")

    dataset_artifact = nested(documents["dataset"], ["dataset", "artifact_sha256"])
    if dataset_artifact not in attachment_digests:
        errors.append("dataset: frozen dataset artifact is not archived")
    install_sources = documents["install_update"].get("source_sha256")
    if not isinstance(install_sources, dict):
        errors.append("install_update: source digest map is incomplete")
    else:
        if install_sources.get("native") != record_digests["native_sdk"]:
            errors.append("install_update: native evidence digest mismatch")
        for operation in (
            "fresh_install", "reinstall", "upgrade", "rollback", "uninstall", "gui_update"
        ):
            if install_sources.get(operation) not in attachment_digests:
                errors.append(f"install_update: {operation} record is not archived")
    three_device = documents.get("three_device", {})
    topology_digests = {
        three_device.get("initial_topology_evidence_sha256"),
        three_device.get("final_topology_evidence_sha256"),
    }
    scenario_digests = three_device.get("source_scenario_sha256")
    if (
        None in topology_digests
        or not isinstance(scenario_digests, list)
        or len(scenario_digests) != 4
        or not topology_digests.union(scenario_digests).issubset(attachment_digests)
    ):
        errors.append("three_device: topology/scenario sources are not archived")
    supply_evidence = documents.get("agent_supply_chain", {}).get("evidence")
    if not isinstance(supply_evidence, dict) or any(
        not isinstance(item, dict) or item.get("sha256") not in attachment_digests
        for item in supply_evidence.values()
    ):
        errors.append("agent_supply_chain: audited artifacts are not archived")
    if not errors:
        errors.extend(validate_embedded_sources(documents, attachment_paths))
        errors.extend(validate_ablation_sources(documents, attachment_paths))
        errors.extend(validate_install_sources(documents, attachment_paths))
        errors.extend(validate_three_device_sources(documents, attachment_paths))
        errors.extend(validate_supply_chain_sources(documents, attachment_paths))
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
            errors.extend(validate_deep_record(name, document))
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
    documents, errors = validate_inputs(records, policy, release_commit, package_sha256)
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
    errors.extend(validate_cross_references(documents, records, attachments))
    if errors:
        raise ValueError("; ".join(errors))
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
            attachment_documents: list[Path] = []
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
                    elif name.startswith("attachments/"):
                        target = temporary_root / f"attachment-{len(attachment_documents)}-{Path(name).name}"
                        target.write_bytes(content)
                        attachment_documents.append(target)
                _, record_errors = validate_inputs(
                    record_documents, policy, release_commit, package_sha256
                )
                errors.extend(record_errors)
                parsed_documents = {
                    name: read_json(path) for name, path in record_documents.items()
                }
                errors.extend(
                    validate_cross_references(
                        parsed_documents, record_documents, attachment_documents
                    )
                )
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
