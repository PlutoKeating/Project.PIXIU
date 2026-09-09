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

    def _privacy_checkpoint(
        self,
        topology_path: Path,
        node_path: Path,
        *,
        checkpoint: str,
        role: str,
        total_ops_synced: int,
        at: int,
    ):
        items = []
        if checkpoint == "post-write" and role == "writer":
            items = [
                {
                    "knowledge_id": "knw_" + "P" * 26,
                    "version": 1,
                    "title": "private-only-value",
                    "scope": "user:evidence",
                    "evidence_ids": ["evd_" + "P" * 26],
                }
            ]
        context = {"context": "private-only-value" if items else "", "items": items}
        status = _status() | {"total_ops_synced": total_ops_synced}
        with patch.object(MODULE, "request_json", side_effect=[context, status]):
            return MODULE.capture_privacy_checkpoint(
                topology_path=topology_path,
                node_path=node_path,
                base_url="http://127.0.0.1:8765",
                checkpoint=checkpoint,
                role=role,
                query="private visibility scenario marker",
                scope="user:evidence",
                captured_at=(
                    MODULE.datetime.fromtimestamp(at, MODULE.timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    at,
                ),
            )

    def _tombstone_checkpoint(
        self,
        topology_path: Path,
        node_path: Path,
        *,
        checkpoint: str,
        role: str,
        deleted: bool,
        paused: bool,
        peers_online: int,
        at: int,
    ):
        knowledge_id = "knw_" + "T" * 26
        items = [] if deleted else [
            {
                "knowledge_id": knowledge_id,
                "version": 1,
                "title": "private tombstone marker",
                "scope": "shared:evidence",
                "evidence_ids": ["evd_" + "T" * 26],
            }
        ]
        context = {"context": "private tombstone marker" if items else "", "items": items}
        state = {
            "present": True,
            "tombstone": deleted,
            "clock_entries": 1,
            "clock_total": 2 if deleted else 1,
            "operation_digest": ("b" if deleted else "a") * 64,
            "updated_at": 200 if deleted else 100,
        }
        status = _status() | {"paused": paused, "peers_online": peers_online}
        with patch.object(
            MODULE, "request_json", side_effect=[context, state, status]
        ):
            return MODULE.capture_tombstone_checkpoint(
                topology_path=topology_path,
                node_path=node_path,
                base_url="http://127.0.0.1:8765",
                checkpoint=checkpoint,
                role=role,
                query="private tombstone scenario query",
                scope="shared:evidence",
                knowledge_id=knowledge_id,
                captured_at=(
                    MODULE.datetime.fromtimestamp(at, MODULE.timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    at,
                ),
            )

    def _final_suite_inputs(self, root: Path):
        initial_path, _node_paths = self._topology(root)
        initial = json.loads(initial_path.read_text(encoding="utf-8"))
        final = json.loads(json.dumps(initial))
        final["generated_at_epoch"] = initial["generated_at_epoch"] + 100
        final["generated_at_utc"] = MODULE.datetime.fromtimestamp(
            final["generated_at_epoch"], MODULE.timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        final["source_node_manifest_sha256"] = [
            MODULE.hashlib.sha256(f"final-node-{index}".encode()).hexdigest()
            for index in range(3)
        ]
        final_path = root / "final-topology.json"
        final_path.write_text(json.dumps(final), encoding="utf-8")
        topology_hash = MODULE._sha256_file(initial_path)
        definitions = {
            "concurrent-update-and-conflict-resolution": (
                MODULE.CONCURRENCY_REPORT_CLASS,
                9,
                {
                    "baseline_three_device_convergence",
                    "two_distinct_paused_update_branches",
                    "three_device_reconnect_convergence",
                    "online_quiescent_final_state",
                },
            ),
            "offline-write-and-reconnect": (
                MODULE.OFFLINE_REPORT_CLASS,
                9,
                {
                    "one_node_isolated_with_baseline_preserved",
                    "remaining_nodes_write_and_propagate",
                    "isolated_node_reconnect_catch_up",
                    "online_quiescent_final_state",
                },
            ),
            "private-scope-non-propagation": (
                MODULE.PRIVACY_REPORT_CLASS,
                6,
                {
                    "private_memory_visible_on_writer_only",
                    "private_memory_absent_on_two_observers",
                    "zero_pending_sync_operations",
                    "unchanged_sync_acknowledgements",
                },
            ),
            "tombstone-propagation-and-no-resurrection": (
                MODULE.TOMBSTONE_REPORT_CLASS,
                12,
                {
                    "two_node_tombstone_propagation",
                    "old_copy_reconnect_did_not_resurrect",
                    "second_reconciliation_remained_deleted",
                    "online_quiescent_final_state",
                },
            ),
        }
        scenario_paths = []
        for scenario, (evidence_class, count, checks) in definitions.items():
            report = {
                "evidence_schema": 1,
                "evidence_class": evidence_class,
                "real_device_evidence": True,
                "final_device_evidence": False,
                "status": "pass",
                "run_id": initial["run_id"],
                "generated_at_epoch": initial["generated_at_epoch"] + 50,
                "generated_at_utc": MODULE.datetime.fromtimestamp(
                    initial["generated_at_epoch"] + 50, MODULE.timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "release": initial["release"],
                "topology_evidence_sha256": topology_hash,
                "source_checkpoint_sha256": [
                    MODULE.hashlib.sha256(f"{scenario}-{index}".encode()).hexdigest()
                    for index in range(count)
                ],
                "scenario": scenario,
                "checks": {name: "passed" for name in checks},
            }
            path = root / f"scenario-{len(scenario_paths)}.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            scenario_paths.append(path)
        return initial_path, final_path, scenario_paths

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

    def test_privacy_checkpoint_proves_writer_only_visibility_without_sync(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            topology_path, node_paths = self._topology(root)
            observations = []
            totals = [11, 22, 33]
            for phase_index, checkpoint in enumerate(("baseline", "post-write")):
                for node_index, node_path in enumerate(node_paths):
                    role = "baseline"
                    if checkpoint == "post-write":
                        role = "writer" if node_index == 0 else "observer"
                    observation = self._privacy_checkpoint(
                        topology_path,
                        node_path,
                        checkpoint=checkpoint,
                        role=role,
                        total_ops_synced=totals[node_index],
                        at=2_000_005_000 + phase_index * 100 + node_index,
                    )
                    encoded = json.dumps(observation, sort_keys=True)
                    self.assertNotIn("private visibility scenario marker", encoded)
                    self.assertNotIn("private-only-value", encoded)
                    self.assertNotIn("user:evidence", encoded)
                    path = root / f"privacy-{checkpoint}-{node_index}.json"
                    path.write_text(json.dumps(observation), encoding="utf-8")
                    observations.append(path)

            report = MODULE.validate_privacy_scenario(
                topology_path=topology_path,
                checkpoint_paths=observations,
            )

        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["real_device_evidence"])
        self.assertFalse(report["final_device_evidence"])
        self.assertEqual(report["scenario"], "private-scope-non-propagation")
        self.assertNotIn(
            "private-scope-non-propagation", report["remaining_required_scenarios"]
        )

    def test_privacy_validator_rejects_remote_visibility_and_sync_growth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            topology_path, node_paths = self._topology(root)
            observations = []
            for phase_index, checkpoint in enumerate(("baseline", "post-write")):
                for node_index, node_path in enumerate(node_paths):
                    role = "baseline"
                    if checkpoint == "post-write":
                        role = "writer" if node_index == 0 else "observer"
                    observation = self._privacy_checkpoint(
                        topology_path,
                        node_path,
                        checkpoint=checkpoint,
                        role=role,
                        total_ops_synced=10 + node_index,
                        at=2_000_006_000 + phase_index * 100 + node_index,
                    )
                    path = root / f"bad-privacy-{checkpoint}-{node_index}.json"
                    path.write_text(json.dumps(observation), encoding="utf-8")
                    observations.append(path)

            remote = json.loads(observations[4].read_text(encoding="utf-8"))
            original_view = remote["local_view_digest"]
            remote["local_result_count"] = 1
            remote["local_view_digest"] = "f" * 64
            observations[4].write_text(json.dumps(remote), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.EvidenceError, "escaped"):
                MODULE.validate_privacy_scenario(
                    topology_path=topology_path,
                    checkpoint_paths=observations,
                )
            remote["local_result_count"] = 0
            remote["local_view_digest"] = original_view
            observations[4].write_text(json.dumps(remote), encoding="utf-8")
            writer = json.loads(observations[3].read_text(encoding="utf-8"))
            writer["sync"]["total_ops_synced"] += 1
            observations[3].write_text(json.dumps(writer), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.EvidenceError, "acknowledgements"):
                MODULE.validate_privacy_scenario(
                    topology_path=topology_path,
                    checkpoint_paths=observations,
                )

    def test_tombstone_scenario_proves_reconnect_and_stable_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            topology_path, node_paths = self._topology(root)
            observations = []
            phases = [
                ("baseline", ["baseline"] * 3, [False] * 3, [False] * 3, [3] * 3),
                (
                    "deleted",
                    ["isolated", "deleter", "online-observer"],
                    [False, True, True],
                    [True, False, False],
                    [1, 2, 2],
                ),
                ("reconnected", ["converged"] * 3, [True] * 3, [False] * 3, [3] * 3),
                ("stable", ["stable"] * 3, [True] * 3, [False] * 3, [3] * 3),
            ]
            for phase_index, phase_data in enumerate(phases):
                phase, roles, deleted, pauses, peers = phase_data
                for node_index, node_path in enumerate(node_paths):
                    observation = self._tombstone_checkpoint(
                        topology_path,
                        node_path,
                        checkpoint=phase,
                        role=roles[node_index],
                        deleted=deleted[node_index],
                        paused=pauses[node_index],
                        peers_online=peers[node_index],
                        at=2_000_007_000 + phase_index * 100 + node_index,
                    )
                    encoded = json.dumps(observation, sort_keys=True)
                    self.assertNotIn("private tombstone", encoded)
                    self.assertNotIn("shared:evidence", encoded)
                    self.assertNotIn("knw_" + "T" * 26, encoded)
                    path = root / f"tombstone-{phase}-{node_index}.json"
                    path.write_text(json.dumps(observation), encoding="utf-8")
                    observations.append(path)

            report = MODULE.validate_tombstone_scenario(
                topology_path=topology_path,
                checkpoint_paths=observations,
            )

        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["real_device_evidence"])
        self.assertFalse(report["final_device_evidence"])
        self.assertEqual(
            report["scenario"], "tombstone-propagation-and-no-resurrection"
        )

    def test_tombstone_validator_rejects_unstable_final_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            topology_path, node_paths = self._topology(root)
            observations = []
            phases = [
                ("baseline", ["baseline"] * 3, [False] * 3, [False] * 3, [3] * 3),
                (
                    "deleted",
                    ["isolated", "deleter", "online-observer"],
                    [False, True, True],
                    [True, False, False],
                    [1, 2, 2],
                ),
                ("reconnected", ["converged"] * 3, [True] * 3, [False] * 3, [3] * 3),
                ("stable", ["stable"] * 3, [True] * 3, [False] * 3, [3] * 3),
            ]
            for phase_index, phase_data in enumerate(phases):
                phase, roles, deleted, pauses, peers = phase_data
                for node_index, node_path in enumerate(node_paths):
                    observation = self._tombstone_checkpoint(
                        topology_path,
                        node_path,
                        checkpoint=phase,
                        role=roles[node_index],
                        deleted=deleted[node_index],
                        paused=pauses[node_index],
                        peers_online=peers[node_index],
                        at=2_000_008_000 + phase_index * 100 + node_index,
                    )
                    path = root / f"bad-tombstone-{phase}-{node_index}.json"
                    path.write_text(json.dumps(observation), encoding="utf-8")
                    observations.append(path)
            tampered = json.loads(observations[-1].read_text(encoding="utf-8"))
            tampered["state_digest"] = "f" * 64
            observations[-1].write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.EvidenceError, "stable"):
                MODULE.validate_tombstone_scenario(
                    topology_path=topology_path,
                    checkpoint_paths=observations,
                )

    def test_final_suite_is_the_only_report_marked_final(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial, final, scenarios = self._final_suite_inputs(root)
            report = MODULE.validate_final_scenario_suite(
                initial_topology_path=initial,
                final_topology_path=final,
                scenario_paths=scenarios,
            )

        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["real_device_evidence"])
        self.assertTrue(report["final_device_evidence"])
        self.assertEqual(report["remaining_required_scenarios"], [])
        self.assertEqual(len(report["scenarios"]), 4)
        MODULE.validate_final_report(report)

        report["checks"].pop("final_logical_view_convergence")
        with self.assertRaisesRegex(MODULE.EvidenceError, "contract"):
            MODULE.validate_final_report(report)

    def test_final_suite_rejects_reused_topology_and_missing_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial, final, scenarios = self._final_suite_inputs(root)
            copied = json.loads(initial.read_text(encoding="utf-8"))
            copied["generated_at_epoch"] += 100
            copied["generated_at_utc"] = MODULE.datetime.fromtimestamp(
                copied["generated_at_epoch"], MODULE.timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            final.write_text(json.dumps(copied), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.EvidenceError, "fresh matching"):
                MODULE.validate_final_scenario_suite(
                    initial_topology_path=initial,
                    final_topology_path=final,
                    scenario_paths=scenarios,
                )

            _initial, final, scenarios = self._final_suite_inputs(root)
            broken = json.loads(scenarios[0].read_text(encoding="utf-8"))
            broken["checks"].pop("online_quiescent_final_state")
            scenarios[0].write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.EvidenceError, "incomplete"):
                MODULE.validate_final_scenario_suite(
                    initial_topology_path=initial,
                    final_topology_path=final,
                    scenario_paths=scenarios,
                )



if __name__ == "__main__":
    unittest.main()
