from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "build_submission.py"
SPEC = importlib.util.spec_from_file_location("build_submission", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SubmissionBuilderTest(unittest.TestCase):
    def test_repository_plan_is_structurally_valid(self) -> None:
        self.assertEqual(MODULE.validate_plan(MODULE.load_plan(), require_ready=False), [])

    def test_pending_plan_refuses_final_package(self) -> None:
        errors = MODULE.validate_plan(MODULE.load_plan(), require_ready=True)
        self.assertIn("release_ready is false", errors)
        self.assertTrue(any(error.startswith("release gates not passed:") for error in errors))

    def test_package_contains_checksums_but_not_itself_in_checksum_list(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "entry"
            package.mkdir()
            (package / "document.pdf").write_bytes(b"document")
            with mock.patch.object(MODULE, "FINAL_ROOT", root):
                output = MODULE.write_checksums_and_zip({"submission_name": "entry"})
            self.assertTrue(output.is_file())
            checksums = (package / "SHA256SUMS").read_text(encoding="utf-8")
            self.assertIn("document.pdf", checksums)
            self.assertIn("SUBMISSION_MANIFEST.json", checksums)
            self.assertNotIn("SHA256SUMS", checksums)

    def test_final_device_evidence_binds_release_and_candidate_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "candidate.deb"
            package.write_bytes(b"candidate package")
            commit = "a" * 40
            report = {
                "evidence_schema": 1,
                "evidence_class": "kylin-v11-three-device-final-suite",
                "real_device_evidence": True,
                "final_device_evidence": True,
                "status": "pass",
                "remaining_required_scenarios": [],
                "scenarios": sorted(MODULE.EXPECTED_DEVICE_SCENARIOS),
                "checks": {name: "passed" for name in MODULE.EXPECTED_DEVICE_CHECKS},
                "source_scenario_sha256": [
                    MODULE.hashlib.sha256(f"scenario-{index}".encode()).hexdigest()
                    for index in range(4)
                ],
                "initial_topology_evidence_sha256": "b" * 64,
                "final_topology_evidence_sha256": "c" * 64,
                "release": {
                    "git_commit": commit,
                    "profile": "kylin-v11-native-x86_64",
                    "architecture": "amd64",
                    "candidate_package_sha256": MODULE.sha256(package),
                    "agent_runtime_version": "0.9.8",
                },
            }
            evidence = root / "evidence.json"
            evidence.write_text(json.dumps(report), encoding="utf-8")
            self.assertEqual(
                MODULE.validate_final_device_evidence(
                    evidence, release_commit=commit, candidate_package=package
                ),
                [],
            )
            report["release"]["git_commit"] = "d" * 40
            evidence.write_text(json.dumps(report), encoding="utf-8")
            self.assertIn(
                "three-device evidence commit does not match release_commit",
                MODULE.validate_final_device_evidence(
                    evidence, release_commit=commit, candidate_package=package
                ),
            )
            report["scenarios"] = [{}]
            evidence.write_text(json.dumps(report), encoding="utf-8")
            self.assertEqual(
                MODULE.validate_final_device_evidence(
                    evidence, release_commit=commit, candidate_package=package
                ),
                ["three-device final evidence contract is incomplete"],
            )


if __name__ == "__main__":
    unittest.main()
