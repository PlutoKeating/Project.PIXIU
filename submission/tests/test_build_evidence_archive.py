from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "build_evidence_archive.py"
SPEC = importlib.util.spec_from_file_location("build_evidence_archive", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class EvidenceArchiveTest(unittest.TestCase):
    def fixtures(self, root: Path) -> tuple[dict, Path, dict[str, Path], list[Path]]:
        policy = MODULE.read_json(MODULE.POLICY_PATH)
        package = root / "pixiu-final_amd64.deb"
        package.write_bytes(b"!<arch>\nrelease")
        package_sha = MODULE.sha256_file(package)
        commit = "a" * 40
        records: dict[str, Path] = {}
        for name, rule in policy["records"].items():
            document = {
                "evidence_schema": 1,
                "evidence_class": rule["evidence_class"],
                "status": "pass",
                "real_device_evidence": rule.get("real_device_evidence"),
                "release": {
                    "git_commit": commit,
                    "candidate_package_sha256": package_sha,
                },
                "checks": {check: "passed" for check in rule.get("required_checks", [])},
            }
            if name == "agent_supply_chain":
                document.update({"release_commit": commit, "ready": True})
            if name == "native_sdk":
                document["candidate_package"] = {"sha256": package_sha}
            if name == "three_device":
                document["final_device_evidence"] = True
            path = root / f"{name}.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            records[name] = path

        frozen_dataset = root / "final-dataset.json"
        eval_report = root / "full-eval-report.json"
        comparison = root / "memory-ablation.json"
        cases = []
        for index in range(50):
            cases.append({
                "id": f"retrieval-{index}", "task": "retrieval",
                "expected": {"knowledge_ids": [f"knw-{index}"], "top_k": 1},
            })
        for index in range(15):
            cases.append({
                "id": f"preference-{index}", "task": "preference",
                "expected": {"labels": [f"label-{index}"]},
            })
        for index in range(25):
            cases.append({
                "id": f"conflict-{index}", "task": "conflict",
                "expected": {"resolution": "NEW_WINS"},
            })
        frozen_document = {
            "schema_version": "1.0",
            "name": "pixiu-final-v1",
            "profile": "acceptance",
            "retrieval_repetitions": 20,
            "fixtures": [{"id": index} for index in range(50)],
            "cases": cases,
        }
        frozen_dataset.write_text(
            json.dumps(frozen_document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        canonical_dataset_sha = MODULE.hashlib.sha256(
            json.dumps(
                frozen_document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        metric_contracts = {
            "preference_accuracy": (">=", 0.85, 15, 1.0),
            "knowledge_recall_at_k": (">=", 0.85, 50, 1.0),
            "retrieval_p95_ms": ("<=", 500.0, 1000, 100.0),
            "conflict_accuracy": (">=", 0.88, 25, 1.0),
        }
        metrics = [
            {
                "name": name,
                "comparison": comparison_operator,
                "target": target,
                "status": "PASS",
                "value": value,
                "denominator": samples,
            }
            for name, (comparison_operator, target, samples, value) in metric_contracts.items()
        ]
        outcomes = []
        for case in cases:
            if case["task"] == "retrieval":
                prediction = {"knowledge_ids": list(case["expected"]["knowledge_ids"])}
                latency_samples = [100.0] * 20
            elif case["task"] == "preference":
                prediction = {"labels": list(case["expected"]["labels"])}
                latency_samples = []
            else:
                prediction = {"resolution": case["expected"]["resolution"]}
                latency_samples = []
            outcomes.append({
                "case_id": case["id"],
                "task": case["task"],
                "prediction": prediction,
                "error": None,
                "latency_samples_ms": latency_samples,
            })
        eval_report.write_text(
            json.dumps({
                "schema_version": "1.0",
                "overall_status": "PASS",
                "dataset_profile": "acceptance",
                "dataset_name": "pixiu-final-v1",
                "dataset_sha256": canonical_dataset_sha,
                "metrics": metrics,
                "outcomes": outcomes,
            }),
            encoding="utf-8",
        )
        variants = [
            {
                "name": name,
                "sample_count": 30,
                "metrics": {"task_success_rate": 0.8, "mean_turns": 2.0},
            }
            for name in ("distributed_memory", "no_memory", "single_device_memory")
        ]
        task_set_sha = "d" * 64
        comparison.write_text(
            json.dumps({
                "schema_version": 1,
                "status": "pass",
                "release": {"git_commit": commit, "candidate_package_sha256": package_sha},
                "dataset_sha256": canonical_dataset_sha,
                "task_set_sha256": task_set_sha,
                "variants": variants,
            }),
            encoding="utf-8",
        )
        attachments = [frozen_dataset, eval_report, comparison]

        agent = json.loads(records["agent_lifecycle"].read_text())
        agent["release"]["native_evidence_sha256"] = MODULE.sha256_file(records["native_sdk"])
        records["agent_lifecycle"].write_text(json.dumps(agent), encoding="utf-8")
        dataset = json.loads(records["dataset"].read_text())
        dataset["dataset"] = {
            "name": "pixiu-final-v1",
            "profile": "acceptance",
            "sha256": canonical_dataset_sha,
            "artifact_sha256": MODULE.sha256_file(frozen_dataset),
            "schema_version": "1.0",
            "fixture_count": 50,
            "case_count": 90,
            "case_counts": {"retrieval": 50, "preference": 15, "conflict": 25},
            "retrieval_repetitions": 20,
        }
        records["dataset"].write_text(json.dumps(dataset), encoding="utf-8")
        performance = json.loads(records["performance"].read_text())
        performance["source_sha256"] = {
            "native": MODULE.sha256_file(records["native_sdk"]),
            "agent": MODULE.sha256_file(records["agent_lifecycle"]),
            "dataset": MODULE.sha256_file(records["dataset"]),
            "report": MODULE.sha256_file(eval_report),
            "comparison": MODULE.sha256_file(comparison),
        }
        performance["metrics"] = {
            name: {
                "value": value,
                "target": target,
                "comparison": comparison_operator,
                "sample_count": samples,
            }
            for name, (comparison_operator, target, samples, value) in metric_contracts.items()
        }
        performance["comparison"] = {
            "variants": variants,
            "task_set_sha256": task_set_sha,
        }
        records["performance"].write_text(json.dumps(performance), encoding="utf-8")
        return policy, package, records, attachments

    def test_complete_archive_round_trips_and_binds_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy, package, records, attachments = self.fixtures(root)
            attachment = root / "metrics.csv"
            attachment.write_text("metric,value\nrecall,0.91\n", encoding="utf-8")
            attachments.append(attachment)
            output = root / "evidence.zip"
            with patch.object(MODULE, "validate_deep_record", return_value=[]):
                MODULE.build_archive(
                    output, records, attachments, policy,
                    release_commit="a" * 40, package=package, epoch=315532800,
                )
                self.assertEqual(
                    MODULE.validate_archive(
                        output, policy,
                        release_commit="a" * 40,
                        package_sha256=MODULE.sha256_file(package),
                    ),
                    [],
                )
                package.write_bytes(b"!<arch>\ndifferent")
                self.assertTrue(
                    MODULE.validate_archive(
                        output, policy,
                        release_commit="a" * 40,
                        package_sha256=MODULE.sha256_file(package),
                    )
                )

    def test_missing_record_and_sensitive_attachment_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy, package, records, _ = self.fixtures(root)
            records.pop("agent_lifecycle")
            with patch.object(MODULE, "validate_deep_record", return_value=[]):
                _, errors = MODULE.validate_inputs(
                    records, policy, "a" * 40, MODULE.sha256_file(package)
                )
            self.assertTrue(any("missing evidence records" in error for error in errors))
            secret = root / "run.log"
            secret.write_text("Authorization: Bearer example-secret-token\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sensitive"):
                MODULE.scan_sensitive(secret)

    def test_deep_validation_rejects_a_shallow_agent_record(self) -> None:
        errors = MODULE.validate_deep_record(
            "agent_lifecycle",
            {"evidence_schema": 1, "evidence_class": "kylin-v11-agent-lifecycle", "status": "pass"},
        )
        self.assertTrue(any("deep evidence validation failed" in error for error in errors))

    def test_cross_references_require_raw_performance_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, records, attachments = self.fixtures(root)
            documents = {name: MODULE.read_json(path) for name, path in records.items()}
            errors = MODULE.validate_cross_references(documents, records, attachments[:-1])
            self.assertTrue(any("comparison input is not archived" in error for error in errors))

    def test_embedded_source_validation_rejects_non_dataset_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, records, attachments = self.fixtures(root)
            documents = {name: MODULE.read_json(path) for name, path in records.items()}
            documents["dataset"]["dataset"]["sha256"] = "0" * 64
            errors = MODULE.validate_embedded_sources(documents, attachments)
            self.assertTrue(any("canonical digest mismatch" in error for error in errors))

    def test_embedded_source_validation_recomputes_raw_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, records, attachments = self.fixtures(root)
            report_path = next(path for path in attachments if path.name == "full-eval-report.json")
            report = MODULE.read_json(report_path)
            report["outcomes"][0]["prediction"]["knowledge_ids"] = []
            report_path.write_text(json.dumps(report), encoding="utf-8")
            documents = {name: MODULE.read_json(path) for name, path in records.items()}
            documents["performance"]["source_sha256"]["report"] = MODULE.sha256_file(report_path)
            errors = MODULE.validate_embedded_sources(documents, attachments)
            self.assertTrue(any("raw outcomes" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
