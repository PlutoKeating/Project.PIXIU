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

    def _topology(self, root: Path):
        node_paths = []
        for index in range(3):
            path = root / f"node-{index}.json"
            path.write_text(json.dumps(self._capture(root, index)), encoding="utf-8")
            node_paths.append(path)
        topology_path = root / "topology.json"
        topology_path.write_text(
            json.dumps(MODULE.validate_cluster(node_paths)), encoding="utf-8"
        )
        return topology_path, node_paths

    def _concurrency_checkpoint(
        self,
        topology_path: Path,
        node_path: Path,
        *,
        checkpoint: str,
        role: str,
        value: str,
        version: int,
        paused: bool,
        at: int,
    ):
        context = {
            "context": value,
            "items": [
                {
                    "knowledge_id": "knw_" + "K" * 26,
                    "version": version,
                    "title": value,
                    "scope": "shared:evidence",
                    "evidence_ids": ["evd_" + value[0] * 26],
                    "conflict_status": "none",
                }
            ],
        }
        status = _status() | {"paused": paused}
        with patch.object(
            MODULE,
            "request_json",
            side_effect=[context, status, {"conflicts": []}],
        ):
            return MODULE.capture_concurrency_checkpoint(
                topology_path=topology_path,
                node_path=node_path,
                base_url="http://127.0.0.1:8765",
                checkpoint=checkpoint,
                role=role,
                query="private scenario marker",
                scope="shared:evidence",
                captured_at=(
                    MODULE.datetime.fromtimestamp(at, MODULE.timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    at,
                ),
            )

    def _offline_checkpoint(
        self,
        topology_path: Path,
        node_path: Path,
        *,
        checkpoint: str,
        role: str,
        value: str,
        version: int,
        paused: bool,
        peers_online: int,
        at: int,
    ):
        context = {
            "context": value,
            "items": [
                {
                    "knowledge_id": "knw_" + "K" * 26,
                    "version": version,
                    "title": value,
                    "scope": "shared:evidence",
                    "evidence_ids": ["evd_" + value[0] * 26],
                    "conflict_status": "none",
                }
            ],
        }
        status = _status() | {"paused": paused, "peers_online": peers_online}
        with patch.object(
            MODULE,
            "request_json",
            side_effect=[context, status, {"conflicts": []}],
        ):
            return MODULE.capture_offline_checkpoint(
                topology_path=topology_path,
                node_path=node_path,
                base_url="http://127.0.0.1:8765",
                checkpoint=checkpoint,
                role=role,
                query="private offline scenario marker",
                scope="shared:evidence",
                captured_at=(
                    MODULE.datetime.fromtimestamp(at, MODULE.timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    at,
                ),
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

    def test_concurrency_checkpoint_is_sanitized_and_scenario_converges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            topology_path, node_paths = self._topology(root)
            observations = []
            phases = [
                (
                    "baseline",
                    ["baseline"] * 3,
                    ["view-seed-private"] * 3,
                    [1] * 3,
                    [False] * 3,
                ),
                (
                    "diverged",
                    ["branch-a", "branch-b", "observer"],
                    ["view-alpha-private", "view-beta-private", "view-seed-private"],
                    [2, 2, 1],
                    [True, True, False],
                ),
                (
                    "converged",
                    ["converged"] * 3,
                    ["view-alpha-private"] * 3,
                    [2] * 3,
                    [False] * 3,
                ),
            ]
            for phase_index, (phase, roles, values, versions, pauses) in enumerate(phases):
                for node_index, node_path in enumerate(node_paths):
                    observation = self._concurrency_checkpoint(
                        topology_path,
                        node_path,
                        checkpoint=phase,
                        role=roles[node_index],
                        value=values[node_index],
                        version=versions[node_index],
                        paused=pauses[node_index],
                        at=2_000_001_000 + phase_index * 100 + node_index,
                    )
                    encoded = json.dumps(observation, sort_keys=True)
                    self.assertNotIn("private scenario marker", encoded)
                    self.assertNotIn(values[node_index], encoded)
                    self.assertNotIn("shared:evidence", encoded)
                    path = root / f"{phase}-{node_index}.json"
                    path.write_text(json.dumps(observation), encoding="utf-8")
                    observations.append(path)

            report = MODULE.validate_concurrency_scenario(
                topology_path=topology_path,
                checkpoint_paths=observations,
            )

        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["real_device_evidence"])
        self.assertFalse(report["final_device_evidence"])
        self.assertEqual(
            report["scenario"], "concurrent-update-and-conflict-resolution"
        )
        self.assertNotIn(
            "concurrent-update-and-conflict-resolution",
            report["remaining_required_scenarios"],
        )

    def test_concurrency_validator_rejects_missing_divergence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            topology_path, node_paths = self._topology(root)
            observations = []
            specifications = [
                (
                    "baseline",
                    ["baseline"] * 3,
                    ["view-seed-private"] * 3,
                    [1] * 3,
                    [False] * 3,
                ),
                (
                    "diverged",
                    ["branch-a", "branch-b", "observer"],
                    ["view-same-private", "view-same-private", "view-seed-private"],
                    [2, 2, 1],
                    [True, True, False],
                ),
                (
                    "converged",
                    ["converged"] * 3,
                    ["view-same-private"] * 3,
                    [2] * 3,
                    [False] * 3,
                ),
            ]
            for phase_index, (phase, roles, values, versions, pauses) in enumerate(
                specifications
            ):
                for node_index, node_path in enumerate(node_paths):
                    value = self._concurrency_checkpoint(
                        topology_path,
                        node_path,
                        checkpoint=phase,
                        role=roles[node_index],
                        value=values[node_index],
                        version=versions[node_index],
                        paused=pauses[node_index],
                        at=2_000_002_000 + phase_index * 100 + node_index,
                    )
                    path = root / f"bad-{phase}-{node_index}.json"
                    path.write_text(json.dumps(value), encoding="utf-8")
                    observations.append(path)
            tampered = json.loads(observations[0].read_text(encoding="utf-8"))
            original_hash = tampered["node_manifest_sha256"]
            tampered["node_manifest_sha256"] = "f" * 64
            observations[0].write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.EvidenceError, "topology nodes"):
                MODULE.validate_concurrency_scenario(
                    topology_path=topology_path,
                    checkpoint_paths=observations,
                )
            tampered["node_manifest_sha256"] = original_hash
            observations[0].write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.EvidenceError, "two offline branches"):
                MODULE.validate_concurrency_scenario(
                    topology_path=topology_path,
                    checkpoint_paths=observations,
                )

    def test_offline_checkpoint_proves_online_write_and_reconnect_catch_up(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            topology_path, node_paths = self._topology(root)
            observations = []
            phases = [
                (
                    "baseline",
                    ["baseline"] * 3,
                    ["view-seed-private"] * 3,
                    [1] * 3,
                    [False] * 3,
                    [3] * 3,
                ),
                (
                    "diverged",
                    ["isolated", "writer", "online-observer"],
                    ["view-seed-private", "view-update-private", "view-update-private"],
                    [1, 2, 2],
                    [True, False, False],
                    [1, 2, 2],
                ),
                (
                    "converged",
                    ["converged"] * 3,
                    ["view-update-private"] * 3,
                    [2] * 3,
                    [False] * 3,
                    [3] * 3,
                ),
            ]
            for phase_index, phase_data in enumerate(phases):
                phase, roles, values, versions, pauses, peers = phase_data
                for node_index, node_path in enumerate(node_paths):
                    observation = self._offline_checkpoint(
                        topology_path,
                        node_path,
                        checkpoint=phase,
                        role=roles[node_index],
                        value=values[node_index],
                        version=versions[node_index],
                        paused=pauses[node_index],
                        peers_online=peers[node_index],
                        at=2_000_003_000 + phase_index * 100 + node_index,
                    )
                    encoded = json.dumps(observation, sort_keys=True)
                    self.assertNotIn("private offline scenario marker", encoded)
                    self.assertNotIn(values[node_index], encoded)
                    self.assertNotIn("shared:evidence", encoded)
                    path = root / f"offline-{phase}-{node_index}.json"
                    path.write_text(json.dumps(observation), encoding="utf-8")
                    observations.append(path)

            report = MODULE.validate_offline_scenario(
                topology_path=topology_path,
                checkpoint_paths=observations,
            )

        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["real_device_evidence"])
        self.assertFalse(report["final_device_evidence"])
        self.assertEqual(report["scenario"], "offline-write-and-reconnect")
        self.assertNotIn(
            "offline-write-and-reconnect", report["remaining_required_scenarios"]
        )

    def test_offline_validator_rejects_unpropagated_online_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            topology_path, node_paths = self._topology(root)
            observations = []
            specifications = [
                ("baseline", ["baseline"] * 3, ["seed"] * 3, [1] * 3, [False] * 3, [3] * 3),
                (
                    "diverged",
                    ["isolated", "writer", "online-observer"],
                    ["seed", "updated", "seed"],
                    [1, 2, 1],
                    [True, False, False],
                    [1, 2, 2],
                ),
                ("converged", ["converged"] * 3, ["updated"] * 3, [2] * 3, [False] * 3, [3] * 3),
            ]
            for phase_index, phase_data in enumerate(specifications):
                phase, roles, values, versions, pauses, peers = phase_data
                for node_index, node_path in enumerate(node_paths):
                    value = self._offline_checkpoint(
                        topology_path,
                        node_path,
                        checkpoint=phase,
                        role=roles[node_index],
                        value=values[node_index],
                        version=versions[node_index],
                        paused=pauses[node_index],
                        peers_online=peers[node_index],
                        at=2_000_004_000 + phase_index * 100 + node_index,
                    )
                    path = root / f"bad-offline-{phase}-{node_index}.json"
                    path.write_text(json.dumps(value), encoding="utf-8")
                    observations.append(path)
            with self.assertRaisesRegex(MODULE.EvidenceError, "online propagation"):
                MODULE.validate_offline_scenario(
                    topology_path=topology_path,
                    checkpoint_paths=observations,
                )


if __name__ == "__main__":
    unittest.main()
