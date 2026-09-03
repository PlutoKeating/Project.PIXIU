#!/usr/bin/env python3
"""Tests for sanitized three-device topology evidence."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/three-device-evidence.py"
SPEC = importlib.util.spec_from_file_location("three_device_evidence", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _native() -> dict:
    return {
        "evidence_schema": 1,
        "release": {
            "product_version": "0.1.7",
            "debian_version": "0.1.7-1",
            "git_commit": "a" * 40,
            "architecture": "amd64",
            "profile": "kylin-v11-native-x86_64",
            "kysdk": "ON",
            "install_strict": True,
        },
        "candidate_package": {"sha256": "b" * 64},
        "capabilities": {
            "platform": {"family": "kylin", "version_major": "11", "v11": True},
            "embedding": {
                "configured": "kylin",
                "runtime": "kylin",
                "compliant": True,
            },
            "vector_store": {
                "configured": "kylin",
                "runtime": "kylin",
                "compliant": True,
            },
            "contest_ready": True,
        },
        "checks": {
            "contest_ready": "passed",
            "memory_write": "passed",
            "vector_search": "passed",
            "vector_delete": "passed",
            "deleted_memory_hidden": "passed",
        },
        "agent_host": {"available": True},
        "agent_runtime": {"version": "0.9.8"},
        "operation_ids": {"evidence_id": "must-not-leak"},
    }


def _peers(self_id: str, members: list[str]) -> dict:
    return {
        "peers": [
            {
                "id": member,
                "name": f"private-name-{member}",
                "is_self": member == self_id,
                "status": "ONLINE",
                "last_sync_ts": 123,
                "pending_ops": 0,
            }
            for member in members
        ]
    }


def _status() -> dict:
    return {
        "domain": "shared:private-domain",
        "peers_online": 3,
        "peers_total": 3,
        "pending_outgoing_ops": 0,
        "last_anti_entropy_ts": 123,
        "total_ops_synced": 10,
        "enabled": True,
        "paused": False,
    }


class ThreeDeviceEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = "run-20260901"
        self.members = ["dev_" + letter * 26 for letter in "ABC"]

    def _capture(self, directory: Path, index: int, *, at: int = 2_000_000_000):
        native = _native()
        native["generated_at_utc"] = f"2033-05-18T03:33:2{index}Z"
        native["operation_ids"]["evidence_id"] = f"must-not-leak-{index}"
        native_path = directory / f"native-{index}.json"
        native_path.write_text(json.dumps(native), encoding="utf-8")
        with patch.object(
            MODULE,
            "request_json",
            side_effect=[_peers(self.members[index], self.members), _status()],
        ):
            return MODULE.capture_node(
                run_id=self.run_id,
                native_path=native_path,
                base_url="http://127.0.0.1:8765",
                captured_at=(f"2033-05-18T03:33:2{index}Z", at + index),
            )

    def test_capture_is_strict_and_does_not_leak_identity_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = self._capture(Path(directory), 0)
        encoded = json.dumps(report, sort_keys=True)
        self.assertTrue(report["real_device_evidence"])
        self.assertFalse(report["final_device_evidence"])
        self.assertEqual(report["node"]["peers_total"], 3)
        for private in [*self.members, "private-name", "shared:private-domain", "must-not-leak"]:
            self.assertNotIn(private, encoded)

    def test_capture_rejects_non_loopback_and_non_strict_native_input(self) -> None:
        with self.assertRaisesRegex(MODULE.EvidenceError, "loopback"):
            MODULE.validate_base_url("http://example.invalid:8765")
        native = _native()
        native["release"]["install_strict"] = False
        with self.assertRaisesRegex(MODULE.EvidenceError, "not a passing strict"):
            MODULE._require_native_evidence(native)

    def test_validate_accepts_same_release_full_mesh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for index in range(3):
                path = root / f"node-{index}.json"
                path.write_text(json.dumps(self._capture(root, index)), encoding="utf-8")
                paths.append(path)
            report = MODULE.validate_cluster(paths)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["topology"]["node_count"], 3)
        self.assertEqual(report["topology"]["trust_edges"], 3)
        self.assertTrue(report["topology"]["full_mesh"])
        self.assertFalse(report["final_device_evidence"])
        self.assertIn("offline-write-and-reconnect", report["remaining_required_scenarios"])

    def test_validate_rejects_missing_edge_release_drift_and_excessive_skew(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifests = [self._capture(root, index) for index in range(3)]
            paths = [root / f"node-{index}.json" for index in range(3)]

            manifests[0]["node"]["members"][0]["identity_digest"] = "f" * 64
            for path, manifest in zip(paths, manifests, strict=True):
                path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.EvidenceError, "full-mesh"):
                MODULE.validate_cluster(paths)

            manifests = [self._capture(root, index) for index in range(3)]
            manifests[1]["release"]["debian_version"] = "0.1.8-1"
            for path, manifest in zip(paths, manifests, strict=True):
                path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.EvidenceError, "one release"):
                MODULE.validate_cluster(paths)

            manifests = [self._capture(root, index) for index in range(3)]
            manifests[2]["native_evidence_sha256"] = manifests[0][
                "native_evidence_sha256"
            ]
            for path, manifest in zip(paths, manifests, strict=True):
                path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.EvidenceError, "independent native"):
                MODULE.validate_cluster(paths)

            manifests = [self._capture(root, index) for index in range(3)]
            manifests[2]["captured_at_epoch"] += MODULE.MAX_CAPTURE_SKEW_SECONDS + 1
            manifests[2]["captured_at_utc"] = MODULE.datetime.fromtimestamp(
                manifests[2]["captured_at_epoch"], MODULE.timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            for path, manifest in zip(paths, manifests, strict=True):
                path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.EvidenceError, "time window"):
                MODULE.validate_cluster(paths)


if __name__ == "__main__":
    unittest.main()
