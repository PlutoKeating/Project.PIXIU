#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "backend/scripts/capture_final_eval.py"
SPEC = importlib.util.spec_from_file_location("capture_final_eval", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def native() -> dict:
    return {
        "evidence_class": "kylin-v11-native-sdk-product-lifecycle",
        "real_device_evidence": True,
        "status": "pass",
        "release": {
            "git_commit": "a" * 40,
            "profile": "kylin-v11-native-x86_64",
            "architecture": "amd64",
            "kysdk": "ON",
            "install_strict": True,
            "product_version": "0.4.0",
            "debian_version": "0.4.0-1",
        },
        "candidate_package": {"sha256": "b" * 64},
        "capabilities": {
            "contest_ready": True,
            "platform": {"family": "kylin", "version_major": "11"},
            "embedding": {"configured": "kylin", "runtime": "kylin", "compliant": True},
            "vector_store": {"configured": "kylin", "runtime": "kylin", "compliant": True},
        },
        "checks": {
            "contest_ready": "passed",
            "memory_write": "passed",
            "vector_search": "passed",
            "vector_delete": "passed",
        },
    }


def predictions() -> list[dict]:
    result = []
    dataset = MODULE.build_reference_dataset()
    for case in dataset.cases:
        if case.task.value == "retrieval":
            prediction = {
                "knowledge_ids": list(case.expected["knowledge_ids"]),
                "evidence_ids": list(case.expected["evidence_ids"]),
            }
            if "aggregate_amount" in case.expected:
                prediction["aggregate_amount"] = case.expected["aggregate_amount"]
            samples = [1.0] * dataset.retrieval_repetitions
        elif case.task.value == "preference":
            prediction = {"labels": list(case.expected["labels"])}
            samples = [1.0]
        else:
            prediction = {"resolution": case.expected["resolution"]}
            samples = [1.0]
        result.append(
            {
                "case_id": case.id,
                "prediction": prediction,
                "latency_ms": samples[0],
                "latency_samples_ms": samples,
            }
        )
    return result


class FinalEvalCaptureTest(unittest.IsolatedAsyncioTestCase):
    async def test_report_binds_strict_runner_and_native_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            native_path = Path(directory) / "native.json"
            native_path.write_text(json.dumps(native()), encoding="utf-8")
            observed = {}

            async def runner(db_path: str, **kwargs):
                observed.update(kwargs)
                self.assertTrue(db_path.endswith("pixiu.db"))
                return predictions()

            report = await MODULE.capture_report(native_path, runner=runner)

        self.assertEqual(report["overall_status"], "PASS")
        self.assertEqual(len(report["outcomes"]), 90)
        self.assertEqual(observed["runtime"], "kylin")
        self.assertTrue(observed["vector_db_path"].endswith("vector-engine.db"))
        MODULE.validate_execution(
            report["execution"],
            {"git_commit": "a" * 40, "candidate_package_sha256": "b" * 64},
        )

    def test_execution_rejects_portable_runtime(self) -> None:
        value = {
            "evidence_class": MODULE.EVIDENCE_CLASS,
            "real_device_evidence": True,
            "platform": "kylin-v11-amd64",
            "execution_mode": "installed-components-isolated-evaluation-state",
            "python_origin": "/usr/lib/pixiu/venv/bin/python",
            "component_origin": "/usr/lib/pixiu",
            "embedding_runtime": "portable",
            "vector_store_runtime": "kylin",
            "isolated_sqlite": True,
            "isolated_vector_database": True,
            "git_commit": "a" * 40,
            "candidate_package_sha256": "b" * 64,
            "native_evidence_sha256": "c" * 64,
        }
        with self.assertRaisesRegex(MODULE.CaptureError, "not strict"):
            MODULE.validate_execution(value)


if __name__ == "__main__":
    unittest.main()
