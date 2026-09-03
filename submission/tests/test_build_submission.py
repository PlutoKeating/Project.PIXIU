from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "build_submission.py"
SPEC = importlib.util.spec_from_file_location("build_submission", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SubmissionBuilderTest(unittest.TestCase):
    def test_office_pdf_and_video_formats_are_not_extension_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "report.pdf"
            pdf.write_bytes(b"%PDF-1.7\nbody\n%%EOF\n")
            docx = root / "report.docx"
            with zipfile.ZipFile(docx, "w") as archive:
                archive.writestr("[Content_Types].xml", "<Types/>")
                archive.writestr("word/document.xml", "<document/>")
            mp4 = root / "demo.mp4"
            mp4.write_bytes(b"\x00\x00\x00\x18ftypisom")
            self.assertEqual(MODULE.validate_deliverable_format(pdf), [])
            self.assertEqual(MODULE.validate_deliverable_format(docx), [])
            self.assertEqual(MODULE.validate_deliverable_format(mp4), [])
            fake = root / "fake.pdf"
            fake.write_text("not a PDF", encoding="utf-8")
            self.assertTrue(MODULE.validate_deliverable_format(fake))

    def test_release_checksum_binds_artifact_name_and_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "pixiu.deb"
            package.write_bytes(b"!<arch>\nfixture")
            checksum = root / "pixiu.deb.sha256"
            checksum.write_text(
                f"{MODULE.sha256(package)}  {package.name}\n", encoding="ascii"
            )
            self.assertEqual(MODULE.validate_deliverable_format(package), [])
            self.assertEqual(MODULE.validate_deliverable_format(checksum), [])
            checksum.write_text(f"{'0' * 64}  {package.name}\n", encoding="ascii")
            self.assertTrue(MODULE.validate_deliverable_format(checksum))

    def test_raw_evidence_policy_failure_is_not_hidden(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, package = root / "evidence.zip", root / "pixiu.deb"
            archive.write_bytes(b"not relevant to delegated validator")
            package.write_bytes(b"!<arch>\nfixture")
            with mock.patch.object(
                MODULE.subprocess,
                "run",
                return_value=MODULE.subprocess.CompletedProcess([], 1, "rejected"),
            ):
                self.assertEqual(
                    MODULE.validate_raw_evidence_archive(archive, package),
                    ["raw evidence archive failed policy validation"],
                )

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
