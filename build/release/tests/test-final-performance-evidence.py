#!/usr/bin/env python3
"""Tests for the final strict-V11 performance evidence binder."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/final-performance-evidence.py"
SPEC = importlib.util.spec_from_file_location("final_performance_evidence", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
IDENTITY = {"git_commit": "a" * 40, "candidate_package_sha256": "b" * 64}
DATASET_SHA = "c" * 64


def native() -> dict:
    return {
        "evidence_class": "kylin-v11-native-sdk-product-lifecycle",
        "real_device_evidence": True,
        "status": "pass",
        "release": {"git_commit": IDENTITY["git_commit"], "profile": "kylin-v11-native-x86_64", "kysdk": "ON", "install_strict": True},
        "candidate_package": {"sha256": IDENTITY["candidate_package_sha256"]},
        "capabilities": {"contest_ready": True},
        "checks": {"memory_write": "passed", "vector_search": "passed", "vector_delete": "passed"},
    }


def derived(kind: str) -> dict:
    return {"evidence_class": kind, "status": "pass", "release": dict(IDENTITY), "checks": {"complete": "passed"}}


def dataset() -> dict:
    value = derived("pixiu-final-dataset-manifest")
    value["dataset"] = {
        "name": "pixiu-final-v1",
        "profile": "acceptance",
        "sha256": DATASET_SHA,
        "retrieval_repetitions": 20,
        "case_counts": {"retrieval": 50, "preference": 15, "conflict": 25},
    }
    return value


def report() -> dict:
    metrics = []
    for name, (comparison, target, samples) in MODULE.METRICS.items():
        metrics.append({
            "name": name,
            "comparison": comparison,
            "target": target,
            "status": "PASS",
            "value": target,
            "denominator": samples,
        })
    return {
        "schema_version": "1.0",
        "overall_status": "PASS",
        "dataset_profile": "acceptance",
        "dataset_name": "pixiu-final-v1",
        "dataset_sha256": DATASET_SHA,
        "metrics": metrics,
        "outcomes": [{"case_id": str(index)} for index in range(90)],
        "execution": {
            "evidence_class": "kylin-v11-final-eval-capture",
            "real_device_evidence": True,
            "platform": "kylin-v11-amd64",
            "execution_mode": "installed-components-isolated-evaluation-state",
            "python_origin": "/usr/lib/pixiu/venv/bin/python",
            "component_origin": "/usr/lib/pixiu",
            "embedding_runtime": "kylin",
            "vector_store_runtime": "kylin",
            "isolated_sqlite": True,
            "isolated_vector_database": True,
            "git_commit": IDENTITY["git_commit"],
            "candidate_package_sha256": IDENTITY["candidate_package_sha256"],
            "native_evidence_sha256": "e" * 64,
        },
    }


def comparison() -> dict:
    return {
        "schema_version": 1,
        "status": "pass",
        "release": dict(IDENTITY),
        "dataset_sha256": DATASET_SHA,
        "task_set_sha256": "d" * 64,
        "variants": [
            {"name": name, "sample_count": 30, "metrics": {"task_success_rate": 0.8, "mean_turns": 2.0}}
            for name in sorted(MODULE.VARIANTS)
        ],
    }


class FinalPerformanceEvidenceTest(unittest.TestCase):
    def _files(self, root: Path, values: dict[str, dict]) -> dict[str, Path]:
        paths = {}
        for name, value in values.items():
            if name == "report" and "native" in paths:
                value["execution"]["native_evidence_sha256"] = MODULE.file_sha256(
                    paths["native"]
                )
            path = root / f"{name}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            paths[name] = path
        return paths

    def test_builds_same_release_payload_free_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._files(Path(directory), {
                "native": native(),
                "agent": derived("kylin-v11-agent-lifecycle"),
                "dataset": dataset(),
                "report": report(),
                "comparison": comparison(),
            })
            evidence = MODULE.build_evidence(paths)
        MODULE.validate_final(evidence)
        self.assertEqual(evidence["release"], IDENTITY)
        self.assertEqual(evidence["checks"]["comparison_and_ablation"], "passed")
        self.assertEqual(set(evidence["source_sha256"]), set(paths))
        self.assertNotIn("outcomes", evidence)

    def test_rejects_portable_or_non_strict_native_evidence(self) -> None:
        value = native()
        value["release"]["kysdk"] = "OFF"
        with self.assertRaisesRegex(MODULE.EvidenceError, "strict V11"):
            MODULE.native_identity(value)

    def test_rejects_under_sampled_metric(self) -> None:
        value = report()
        next(item for item in value["metrics"] if item["name"] == "retrieval_p95_ms")["denominator"] = 999
        with self.assertRaisesRegex(MODULE.EvidenceError, "retrieval_p95_ms"):
            MODULE.validate_eval_report(value, dataset()["dataset"])

    def test_requires_all_three_ablation_variants(self) -> None:
        value = comparison()
        value["variants"].pop()
        with self.assertRaisesRegex(MODULE.EvidenceError, "variants"):
            MODULE.validate_comparison(value, IDENTITY, DATASET_SHA)


if __name__ == "__main__":
    unittest.main()
