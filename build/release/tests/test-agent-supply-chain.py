#!/usr/bin/env python3
"""Tests for the Agent supply-chain release gate."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "build/release/scripts/audit-agent-supply-chain.py"
SPEC = importlib.util.spec_from_file_location("agent_supply_chain_audit", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class AgentSupplyChainAuditTest(unittest.TestCase):
    def test_authenticated_url_scan_redacts_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            scripts.mkdir()
            secret_url = "https://example-user:example-token@example.invalid/source.git"
            (scripts / "install.sh").write_text(secret_url, encoding="utf-8")

            findings = AUDIT.authenticated_url_files(root, ["scripts"])

            self.assertEqual(findings, ["scripts/install.sh"])
            self.assertNotIn("example-token", json.dumps(findings))

    def test_runtime_versions_preserve_three_distinct_facts(self) -> None:
        versions = AUDIT.runtime_versions(ROOT / "third_party/kylin-agent-runtime")
        self.assertEqual(
            versions,
            {
                "cli": "0.9.4",
                "package_metadata": "0.9.8",
                "version_file": "0.9.9",
            },
        )

    def test_evidence_path_cannot_escape_evidence_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            evidence_dir = Path(temporary) / "evidence"
            evidence_dir.mkdir()
            outside = Path(temporary) / "outside.bin"
            outside.write_bytes(b"outside")

            self.assertIsNone(AUDIT.evidence_file(evidence_dir, "../outside.bin"))

    def test_current_tree_is_reported_not_ready_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = AUDIT.audit(
                ROOT,
                ROOT / "build/release/agent-supply-chain-policy.json",
                Path(temporary),
            )

        self.assertFalse(report["ready"])
        self.assertIn("authenticated-url-detected", report["blockers"])
        self.assertIn("missing-host-build-evidence", report["blockers"])
        self.assertTrue(report["sensitive_scan"]["matched_values_redacted"])
        serialized = json.dumps(report)
        self.assertNotIn("example-token", serialized)

    def test_complete_evidence_set_validates(self) -> None:
        policy = AUDIT.read_json(
            ROOT / "build/release/agent-supply-chain-policy.json"
        )
        with tempfile.TemporaryDirectory() as temporary:
            evidence_dir = Path(temporary)
            host_artifact = evidence_dir / "kylin-agent"
            host_artifact.write_bytes(b"reproducible host artifact")
            wheelhouse = evidence_dir / "wheelhouse"
            wheelhouse.mkdir()
            runtime_wheel = wheelhouse / "runtime.whl"
            runtime_wheel.write_bytes(b"locked runtime wheel")
            documents = {
                "agent-host-build.json": {
                    "source_commit": policy["components"]["kylin_agent"][
                        "source_commit"
                    ],
                    "target_os": "kylin-v11",
                    "rebuild_verified": True,
                    "artifact": "kylin-agent",
                    "artifact_sha256": AUDIT.sha256_file(host_artifact),
                },
                "runtime-wheelhouse.json": {
                    "source_commit": policy["components"]["agent_runtime"][
                        "source_commit"
                    ],
                    "offline_install_verified": True,
                    "packages": [
                        {
                            "filename": "wheelhouse/runtime.whl",
                            "sha256": AUDIT.sha256_file(runtime_wheel),
                        }
                    ],
                },
                "agent-components.spdx.json": {
                    "spdxVersion": "SPDX-2.3",
                    "SPDXID": "SPDXRef-DOCUMENT",
                    "packages": [{"name": "agent-host"}],
                },
            }
            for filename, document in documents.items():
                (evidence_dir / filename).write_text(
                    json.dumps(document), encoding="utf-8"
                )
            (evidence_dir / "NOTICE.agent.txt").write_text(
                "Agent distribution notices\n", encoding="utf-8"
            )

            evidence = AUDIT.load_evidence(evidence_dir, policy["evidence"])
            blockers = AUDIT.validate_evidence(evidence_dir, evidence, policy)

        self.assertEqual(blockers, [])
        self.assertTrue(all(item.get("valid") for item in evidence.values()))


if __name__ == "__main__":
    unittest.main()
