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

        install_spec = importlib.util.spec_from_file_location(
            "test_install_update_validator",
            MODULE.ROOT / "build/release/scripts/install-update-evidence.py",
        )
        assert install_spec and install_spec.loader
        install_module = importlib.util.module_from_spec(install_spec)
        install_spec.loader.exec_module(install_module)

        def snapshot(installed: bool, version: str | None, stamp: str) -> dict:
            return {
                "evidence_schema": 1,
                "evidence_class": install_module.SNAPSHOT_CLASS,
                "real_device_evidence": True,
                "captured_at_utc": stamp,
                "platform": {
                    "family": "kylin", "version_major": "11", "architecture": "amd64",
                },
                "candidate_package": {
                    "filename": package.name, "sha256": package_sha, "size": package.stat().st_size,
                    "debian_version": "0.4.0-1", "architecture": "amd64", "name": "pixiu",
                },
                "installed": {
                    "present": installed, "debian_version": version,
                    "service_active": installed, "binary_present": installed,
                    "release_manifest_present": installed,
                },
                "runtime": {
                    "version": {"product_version": str(version).split("-")[0]} if installed else None,
                    "health": {"status": "ready", "database": "ok"} if installed else None,
                    "capabilities": {"contest_ready": True} if installed else None,
                },
                "preserved_state": {
                    "config_present": True, "config_sha256": "c" * 64,
                    "database": {
                        "present": True, "integrity": "ok",
                        "logical_counts": {"evidence": 7, "knowledge_items": 5, "preferences": 2, "sync_peers": 2},
                        "device_identity_digest": "d" * 64,
                    },
                },
            }

        operation_specs = {
            "fresh_install": (snapshot(False, None, "2026-09-05T00:00:00Z"), snapshot(True, "0.4.0-1", "2026-09-05T00:01:00Z"), 0, "installed"),
            "reinstall": (snapshot(True, "0.4.0-1", "2026-09-05T00:02:00Z"), snapshot(True, "0.4.0-1", "2026-09-05T00:03:00Z"), 0, "installed"),
            "upgrade": (snapshot(True, "0.3.0-1", "2026-09-05T00:04:00Z"), snapshot(True, "0.4.0-1", "2026-09-05T00:05:00Z"), 0, "installed"),
            "rollback": (snapshot(True, "0.3.0-1", "2026-09-05T00:06:00Z"), snapshot(True, "0.3.0-1", "2026-09-05T00:07:00Z"), 5, "recovered"),
            "uninstall": (snapshot(True, "0.4.0-1", "2026-09-05T00:08:00Z"), snapshot(False, None, "2026-09-05T00:09:00Z"), 0, "removed"),
            "gui_update": (snapshot(True, "0.3.0-1", "2026-09-05T00:10:00Z"), snapshot(True, "0.4.0-1", "2026-09-05T00:11:00Z"), 0, "installed"),
        }
        install_sources = {"native": MODULE.sha256_file(records["native_sdk"])}
        for operation, (before, after, exit_code, outcome) in operation_specs.items():
            before_path = root / f"{operation}-before.json"
            after_path = root / f"{operation}-after.json"
            proof_path = root / f"{operation}-proof.log"
            before_path.write_text(json.dumps(before, sort_keys=True), encoding="utf-8")
            after_path.write_text(json.dumps(after, sort_keys=True), encoding="utf-8")
            proof_path.write_text(f"operation proof {operation}\n", encoding="utf-8")
            operation_document = install_module.make_operation(
                operation, before_path, after_path, proof_path, exit_code, outcome
            )
            operation_path = root / f"{operation}-operation.json"
            operation_path.write_text(json.dumps(operation_document, sort_keys=True), encoding="utf-8")
            attachments.extend((before_path, after_path, proof_path, operation_path))
            install_sources[operation] = MODULE.sha256_file(operation_path)
        install = json.loads(records["install_update"].read_text())
        install["release"].update({
            "product_version": "0.4.0", "debian_version": "0.4.0-1",
            "architecture": "amd64", "profile": "kylin-v11-native-x86_64",
            "native_evidence_sha256": MODULE.sha256_file(records["native_sdk"]),
        })
        install["source_sha256"] = install_sources
        install["observations"] = {
            "operation_count": 6, "payloads_retained": False,
            "uninstall_policy": "remove-preserves-user-data; purge-deletes-user-data",
        }
        records["install_update"].write_text(json.dumps(install), encoding="utf-8")

        three_sources = []
        for name in (
            "initial-topology.json", "final-topology.json", "concurrency-scenario.json",
            "offline-scenario.json", "privacy-scenario.json", "tombstone-scenario.json",
        ):
            source = root / name
            source.write_text(json.dumps({"source": name}), encoding="utf-8")
            attachments.append(source)
            three_sources.append(MODULE.sha256_file(source))
        three_device = json.loads(records["three_device"].read_text())
        three_device.update({
            "run_id": "run-20260905",
            "generated_at_utc": "2026-09-05T00:12:00Z",
            "generated_at_epoch": 1788567120,
            "initial_topology_evidence_sha256": three_sources[0],
            "final_topology_evidence_sha256": three_sources[1],
            "source_scenario_sha256": sorted(three_sources[2:]),
            "scenarios": [
                "concurrent-update-and-conflict-resolution",
                "offline-write-and-reconnect",
                "private-scope-non-propagation",
                "tombstone-propagation-and-no-resurrection",
            ],
            "checks": {
                "same_release_run_devices_and_domain": "passed",
                "fresh_final_three_device_topology": "passed",
                "all_required_scenarios_bound": "passed",
                "all_scenario_checks_passed": "passed",
                "all_scenarios_between_topology_captures": "passed",
                "final_online_quiescent_full_mesh": "passed",
                "final_logical_view_convergence": "passed",
            },
            "remaining_required_scenarios": [],
        })
        three_device["release"]["architecture"] = "amd64"
        records["three_device"].write_text(json.dumps(three_device), encoding="utf-8")

        supply = json.loads(records["agent_supply_chain"].read_text())
        supply_evidence = {}
        for index, (name, filename) in enumerate({
            "host_build": "agent-host-build.json",
            "runtime_wheelhouse": "runtime-wheelhouse.json",
            "sbom": "agent-components.spdx.json",
            "notice": "NOTICE.agent.txt",
        }.items()):
            artifact = root / filename
            artifact.write_text(f"supply artifact {index}\n", encoding="utf-8")
            attachments.append(artifact)
            supply_evidence[name] = {
                "file": filename, "present": True, "nonempty": True, "valid": True,
                "sha256": MODULE.sha256_file(artifact),
            }
        supply["evidence"] = supply_evidence
        records["agent_supply_chain"].write_text(json.dumps(supply), encoding="utf-8")
        return policy, package, records, attachments

    def test_complete_archive_round_trips_and_binds_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy, package, records, attachments = self.fixtures(root)
            attachment = root / "metrics.csv"
            attachment.write_text("metric,value\nrecall,0.91\n", encoding="utf-8")
            attachments.append(attachment)
            output = root / "evidence.zip"
            with (
                patch.object(MODULE, "validate_deep_record", return_value=[]),
                patch.object(MODULE, "validate_three_device_sources", return_value=[]),
                patch.object(MODULE, "validate_supply_chain_sources", return_value=[]),
            ):
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
        for name, evidence_class in (
            ("three_device", "kylin-v11-three-device-final-suite"),
            ("agent_supply_chain", "agent-supply-chain-audit"),
        ):
            errors = MODULE.validate_deep_record(
                name,
                {"evidence_schema": 1, "evidence_class": evidence_class, "status": "pass"},
            )
            self.assertTrue(any("deep evidence validation failed" in error for error in errors))

    def test_cross_references_require_raw_performance_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, records, attachments = self.fixtures(root)
            documents = {name: MODULE.read_json(path) for name, path in records.items()}
            errors = MODULE.validate_cross_references(
                documents, records,
                [path for path in attachments if path.name != "memory-ablation.json"],
            )
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

    def test_install_source_validation_rejects_tampered_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, records, attachments = self.fixtures(root)
            snapshot_path = next(
                path for path in attachments if path.name == "upgrade-after.json"
            )
            snapshot = MODULE.read_json(snapshot_path)
            snapshot["preserved_state"]["config_sha256"] = "e" * 64
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
            documents = {name: MODULE.read_json(path) for name, path in records.items()}
            errors = MODULE.validate_install_sources(documents, attachments)
            self.assertTrue(any("install/update" in error for error in errors))

    def test_three_device_source_validation_rejects_fake_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, records, attachments = self.fixtures(root)
            documents = {name: MODULE.read_json(path) for name, path in records.items()}
            errors = MODULE.validate_three_device_sources(documents, attachments)
            self.assertTrue(any("three-device" in error for error in errors))

    def test_supply_chain_source_validation_rejects_fake_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, records, attachments = self.fixtures(root)
            documents = {name: MODULE.read_json(path) for name, path in records.items()}
            errors = MODULE.validate_supply_chain_sources(documents, attachments)
            self.assertTrue(any("supply-chain" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
