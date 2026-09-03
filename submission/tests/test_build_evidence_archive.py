from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "build_evidence_archive.py"
SPEC = importlib.util.spec_from_file_location("build_evidence_archive", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class EvidenceArchiveTest(unittest.TestCase):
    def fixtures(self, root: Path) -> tuple[dict, Path, dict[str, Path]]:
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
        return policy, package, records

    def test_complete_archive_round_trips_and_binds_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy, package, records = self.fixtures(root)
            attachment = root / "metrics.csv"
            attachment.write_text("metric,value\nrecall,0.91\n", encoding="utf-8")
            output = root / "evidence.zip"
            MODULE.build_archive(
                output, records, [attachment], policy,
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
            policy, package, records = self.fixtures(root)
            records.pop("agent_lifecycle")
            _, errors = MODULE.validate_inputs(
                records, policy, "a" * 40, MODULE.sha256_file(package)
            )
            self.assertTrue(any("missing evidence records" in error for error in errors))
            secret = root / "run.log"
            secret.write_text("Authorization: Bearer example-secret-token\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sensitive"):
                MODULE.scan_sensitive(secret)


if __name__ == "__main__":
    unittest.main()
