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
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            (runtime / "kylin_agent_runtime_cli").mkdir()
            (runtime / "pyproject.toml").write_text(
                '[project]\nversion = "0.9.8"\n', encoding="utf-8"
            )
            (runtime / "version").write_text("0.9.9\n", encoding="utf-8")
            (runtime / "kylin_agent_runtime_cli/__init__.py").write_text(
                '__version__ = "0.9.4"\n', encoding="utf-8"
            )
            versions = AUDIT.runtime_versions(runtime)
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

    def test_missing_submodule_is_reported_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy = {
                "components": {
                    "kylin_agent": {
                        "path": "third_party/kylin-agent",
                        "source_commit": "1" * 40,
                        "package_name": "kylin-agent",
                        "spdx_id": "SPDXRef-Package-kylin-agent",
                        "declared_license": "LicenseRef-AGPL",
                        "source_url": "https://example.invalid/agent",
                        "license_files": ["LICENSE"],
                    },
                    "agent_runtime": {
                        "path": "third_party/kylin-agent-runtime",
                        "source_commit": "2" * 40,
                        "package_name": "kylin-agent-runtime",
                        "spdx_id": "SPDXRef-Package-kylin-agent-runtime",
                        "declared_license": "MIT",
                        "source_url": "https://example.invalid/runtime",
                        "license_files": ["LICENSE"],
                        "declared_versions": {
                            "cli": "0.9.4",
                            "package_metadata": "0.9.8",
                            "version_file": "0.9.9",
                        },
                    },
                },
                "target_os": "kylin-v11",
                "target_architectures": ["amd64", "arm64"],
                "runtime_required_packages": ["kylin-agent-runtime", "aiohttp"],
                "sensitive_scan_paths": [],
                "evidence": {
                    "host_build": "agent-host-build.json",
                    "runtime_wheelhouse": "runtime-wheelhouse.json",
                    "sbom": "agent-components.spdx.json",
                    "notice": "NOTICE.agent.txt",
                },
            }
            policy_path = root / "policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")

            report = AUDIT.audit(root, policy_path, root / "evidence")

        self.assertFalse(report["ready"])
        self.assertIn("runtime-version-facts-unavailable", report["blockers"])
        self.assertIn("component-not-pinned:kylin_agent", report["blockers"])

    def test_current_tree_is_reported_not_ready_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = AUDIT.audit(
                ROOT,
                ROOT / "build/release/agent-supply-chain-policy.json",
                Path(temporary),
            )

        self.assertFalse(report["ready"])
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
            host_source = evidence_dir / "kylin-agent-source.tar.zst"
            host_source.write_bytes(b"complete corresponding source")
            host_log = evidence_dir / "host-build.log"
            host_log.write_text("clean V11 rebuild passed\n", encoding="utf-8")
            wheelhouse = evidence_dir / "wheelhouse"
            wheelhouse.mkdir()
            runtime_wheel = wheelhouse / "kylin_agent_runtime-0.9.8-py3-none-any.whl"
            runtime_wheel.write_bytes(b"locked runtime wheel")
            aiohttp_wheel = wheelhouse / "aiohttp-3.13.3-cp311-manylinux.whl"
            aiohttp_wheel.write_bytes(b"locked aiohttp wheel")
            lockfile = evidence_dir / "runtime.lock"
            lockfile.write_text("fully locked runtime dependencies\n", encoding="utf-8")
            install_log = evidence_dir / "offline-install.log"
            install_log.write_text("offline install passed\n", encoding="utf-8")
            agent_policy = policy["components"]["kylin_agent"]
            runtime_policy = policy["components"]["agent_runtime"]
            documents = {
                "agent-host-build.json": {
                    "schema_version": 1,
                    "source_commit": agent_policy["source_commit"],
                    "target_os": "kylin-v11",
                    "target_arch": "amd64",
                    "rebuild_verified": True,
                    "network_access_during_build": False,
                    "artifact": "kylin-agent",
                    "artifact_sha256": AUDIT.sha256_file(host_artifact),
                    "source_archive": host_source.name,
                    "source_archive_sha256": AUDIT.sha256_file(host_source),
                    "build_log": host_log.name,
                    "build_log_sha256": AUDIT.sha256_file(host_log),
                },
                "runtime-wheelhouse.json": {
                    "schema_version": 1,
                    "source_commit": runtime_policy["source_commit"],
                    "target_os": "kylin-v11",
                    "target_arch": "amd64",
                    "python_abi": "cp311",
                    "offline_install_verified": True,
                    "network_access_during_install": False,
                    "lockfile": lockfile.name,
                    "lockfile_sha256": AUDIT.sha256_file(lockfile),
                    "offline_install_log": install_log.name,
                    "offline_install_log_sha256": AUDIT.sha256_file(install_log),
                    "packages": [
                        {
                            "name": "kylin-agent-runtime",
                            "version": "0.9.8",
                            "filename": f"wheelhouse/{runtime_wheel.name}",
                            "sha256": AUDIT.sha256_file(runtime_wheel),
                        },
                        {
                            "name": "aiohttp",
                            "version": "3.13.3",
                            "filename": f"wheelhouse/{aiohttp_wheel.name}",
                            "sha256": AUDIT.sha256_file(aiohttp_wheel),
                        },
                    ],
                },
                "agent-components.spdx.json": {
                    "spdxVersion": "SPDX-2.3",
                    "SPDXID": "SPDXRef-DOCUMENT",
                    "dataLicense": "CC0-1.0",
                    "documentDescribes": [
                        agent_policy["spdx_id"], runtime_policy["spdx_id"]
                    ],
                    "packages": [
                        {
                            "name": agent_policy["package_name"],
                            "SPDXID": agent_policy["spdx_id"],
                            "versionInfo": agent_policy["source_commit"],
                            "licenseDeclared": agent_policy["declared_license"],
                            "downloadLocation": agent_policy["source_url"],
                        },
                        {
                            "name": runtime_policy["package_name"],
                            "SPDXID": runtime_policy["spdx_id"],
                            "versionInfo": runtime_policy["source_commit"],
                            "licenseDeclared": runtime_policy["declared_license"],
                            "downloadLocation": runtime_policy["source_url"],
                        },
                        {"name": "aiohttp", "SPDXID": "SPDXRef-Package-aiohttp"},
                    ],
                    "hasExtractedLicensingInfos": [
                        {
                            "licenseId": agent_policy["declared_license"],
                            "extractedText": (
                                "GNU Affero GPL version 3 family; exact only/or-later "
                                "operator remains pending legal review."
                            ),
                        }
                    ],
                },
            }
            for filename, document in documents.items():
                (evidence_dir / filename).write_text(
                    json.dumps(document), encoding="utf-8"
                )
            (evidence_dir / "NOTICE.agent.txt").write_text(
                "\n".join(
                    str(value)
                    for component in policy["components"].values()
                    for value in (
                        component["package_name"],
                        component["source_commit"],
                        component["source_url"],
                        component["declared_license"],
                    )
                ),
                encoding="utf-8",
            )

            evidence = AUDIT.load_evidence(evidence_dir, policy["evidence"])
            blockers = AUDIT.validate_evidence(evidence_dir, evidence, policy)

        self.assertEqual(blockers, [])
        self.assertTrue(all(item.get("valid") for item in evidence.values()))

    def test_claim_only_evidence_is_rejected(self) -> None:
        policy = AUDIT.read_json(
            ROOT / "build/release/agent-supply-chain-policy.json"
        )
        with tempfile.TemporaryDirectory() as temporary:
            evidence_dir = Path(temporary)
            (evidence_dir / "agent-host-build.json").write_text(
                json.dumps(
                    {
                        "source_commit": policy["components"]["kylin_agent"][
                            "source_commit"
                        ],
                        "target_os": "kylin-v11",
                        "rebuild_verified": True,
                    }
                ),
                encoding="utf-8",
            )
            evidence = AUDIT.load_evidence(evidence_dir, policy["evidence"])
            blockers = AUDIT.validate_evidence(evidence_dir, evidence, policy)

        self.assertIn("invalid-host-build-evidence", blockers)

    def test_placeholder_legal_evidence_is_rejected(self) -> None:
        policy = AUDIT.read_json(
            ROOT / "build/release/agent-supply-chain-policy.json"
        )
        with tempfile.TemporaryDirectory() as temporary:
            evidence_dir = Path(temporary)
            (evidence_dir / "agent-components.spdx.json").write_text(
                json.dumps(
                    {
                        "spdxVersion": "SPDX-2.3",
                        "SPDXID": "SPDXRef-DOCUMENT",
                        "dataLicense": "CC0-1.0",
                        "packages": [{"name": "placeholder"}],
                    }
                ),
                encoding="utf-8",
            )
            (evidence_dir / "NOTICE.agent.txt").write_text(
                "placeholder\n", encoding="utf-8"
            )
            evidence = AUDIT.load_evidence(evidence_dir, policy["evidence"])
            blockers = AUDIT.validate_evidence(evidence_dir, evidence, policy)

        self.assertIn("invalid-agent-sbom", blockers)
        self.assertIn("invalid-agent-notice", blockers)


if __name__ == "__main__":
    unittest.main()
