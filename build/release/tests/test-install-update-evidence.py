#!/usr/bin/env python3

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "build/release/scripts/install-update-evidence.py"
SPEC = importlib.util.spec_from_file_location("install_update_evidence", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


PACKAGE_SHA = "b" * 64
CANDIDATE_VERSION = "0.4.0-1"
OLD_VERSION = "0.3.0-1"


def native() -> dict:
    direct = {
        name: "passed"
        for name in {
            "embedding", "database_load", "collection_create", "collection_load",
            "vector_upsert", "vector_search", "vector_delete",
            "deleted_vector_hidden", "collection_drop", "disconnect",
        }
    }
    return {
        "evidence_schema": 1,
        "evidence_class": "kylin-v11-native-sdk-product-lifecycle",
        "real_device_evidence": True,
        "status": "pass",
        "release": {
            "git_commit": "a" * 40,
            "profile": "kylin-v11-native-x86_64",
            "architecture": "amd64",
            "kysdk": "ON",
            "install_strict": True,
            "product_version": "0.4.0",
            "debian_version": CANDIDATE_VERSION,
        },
        "candidate_package": {
            "sha256": PACKAGE_SHA,
            "size": 1234,
            "filename": "pixiu_0.4.0-1_amd64.deb",
        },
        "installed": {
            "architecture": "amd64",
            "packages": {
                "pixiu": CANDIDATE_VERSION,
                "libkylin-coreai-embedding": "1.0",
                "libkysdk-vector-engine-client": "1.0",
            },
        },
        "agent_host": {"available": True},
        "agent_runtime": {"version": "0.9.6"},
        "version": {"product_version": "0.4.0"},
        "health": {"status": "ready", "database": "ok"},
        "capabilities": {
            "contest_ready": True,
            "platform": {"family": "kylin", "version_major": "11", "v11": True},
            "embedding": {"configured": "kylin", "runtime": "kylin", "compliant": True},
            "vector_store": {"configured": "kylin", "runtime": "kylin", "compliant": True},
        },
        "direct_sdk": direct,
        "checks": {
            name: "passed"
            for name in {
                "contest_ready", "memory_write", "vector_search",
                "vector_delete", "deleted_memory_hidden",
            }
        },
        "operation_ids": {"evidence_id": "evd_test", "knowledge_id": "knw_test"},
    }


def snapshot(installed: bool, version: str | None, stamp: str) -> dict:
    state = {
        "config_present": True,
        "config_sha256": "c" * 64,
        "database": {
            "present": True,
            "integrity": "ok",
            "logical_counts": {
                "evidence": 7,
                "knowledge_items": 5,
                "preferences": 2,
                "sync_peers": 2,
            },
            "device_identity_digest": "d" * 64,
        },
    }
    return {
        "evidence_schema": 1,
        "evidence_class": MODULE.SNAPSHOT_CLASS,
        "real_device_evidence": True,
        "captured_at_utc": stamp,
        "platform": {"family": "kylin", "version_major": "11", "architecture": "amd64"},
        "candidate_package": {
            "filename": "pixiu_0.4.0-1_amd64.deb",
            "sha256": PACKAGE_SHA,
            "size": 1234,
            "debian_version": CANDIDATE_VERSION,
            "architecture": "amd64",
            "name": "pixiu",
        },
        "installed": {
            "present": installed,
            "debian_version": version,
            "service_active": installed,
            "binary_present": installed,
            "release_manifest_present": installed,
        },
        "runtime": {
            "version": {"product_version": version.split("-")[0]} if installed else None,
            "health": {"status": "ready", "database": "ok"} if installed else None,
            "capabilities": {"contest_ready": True} if installed else None,
        },
        "preserved_state": state,
    }


class InstallUpdateEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, name: str, value: object) -> Path:
        path = self.root / name
        if isinstance(value, dict):
            path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        else:
            path.write_text(str(value), encoding="utf-8")
        return path

    def operation(
        self, kind: str, before: dict, after: dict, exit_code: int, outcome: str
    ) -> Path:
        before_path = self.write(f"{kind}-before.json", before)
        after_path = self.write(f"{kind}-after.json", after)
        proof = self.write(f"{kind}-proof.log", f"real operation proof: {kind}\n")
        value = MODULE.make_operation(
            kind, before_path, after_path, proof, exit_code, outcome
        )
        path = self.write(f"{kind}.json", value)
        return path

    def valid_operations(self) -> list[Path]:
        absent = snapshot(False, None, "2026-09-05T00:00:00Z")
        old = snapshot(True, OLD_VERSION, "2026-09-05T00:01:00Z")
        current = snapshot(True, CANDIDATE_VERSION, "2026-09-05T00:02:00Z")
        removed = snapshot(False, None, "2026-09-05T00:03:00Z")
        return [
            self.operation("fresh_install", absent, current, 0, "installed"),
            self.operation("reinstall", current, copy.deepcopy(current), 0, "installed"),
            self.operation("upgrade", old, current, 0, "installed"),
            self.operation("rollback", old, copy.deepcopy(old), 5, "recovered"),
            self.operation("uninstall", current, removed, 0, "removed"),
            self.operation("gui_update", old, current, 0, "installed"),
        ]

    def test_complete_matrix_passes_and_is_payload_free(self) -> None:
        native_path = self.write("native.json", native())
        result = MODULE.assemble(native_path, self.valid_operations())
        MODULE.validate_final(result)
        self.assertEqual(result["checks"]["data_preserved"], "passed")
        self.assertFalse(result["observations"]["payloads_retained"])
        self.assertEqual(result["observations"]["operation_count"], 6)

    def test_missing_operation_fails(self) -> None:
        native_path = self.write("native.json", native())
        with self.assertRaisesRegex(MODULE.EvidenceError, "every required"):
            MODULE.assemble(native_path, self.valid_operations()[:-1])

    def test_upgrade_rejects_changed_configuration(self) -> None:
        before = snapshot(True, OLD_VERSION, "2026-09-05T00:00:00Z")
        after = snapshot(True, CANDIDATE_VERSION, "2026-09-05T00:01:00Z")
        after["preserved_state"]["config_sha256"] = "e" * 64
        operation = self.operation("upgrade", before, after, 0, "installed")
        with self.assertRaisesRegex(MODULE.EvidenceError, "not proven"):
            MODULE.validate_operation(MODULE.read_json(operation), PACKAGE_SHA)

    def test_rollback_requires_helper_recovery_exit_code(self) -> None:
        old = snapshot(True, OLD_VERSION, "2026-09-05T00:00:00Z")
        operation = self.operation("rollback", old, copy.deepcopy(old), 0, "recovered")
        with self.assertRaisesRegex(MODULE.EvidenceError, "not proven"):
            MODULE.validate_operation(MODULE.read_json(operation), PACKAGE_SHA)

    def test_uninstall_requires_user_data_retention(self) -> None:
        before = snapshot(True, CANDIDATE_VERSION, "2026-09-05T00:00:00Z")
        after = snapshot(False, None, "2026-09-05T00:01:00Z")
        after["preserved_state"]["database"] = {"present": False}
        operation = self.operation("uninstall", before, after, 0, "removed")
        with self.assertRaisesRegex(MODULE.EvidenceError, "not proven"):
            MODULE.validate_operation(MODULE.read_json(operation), PACKAGE_SHA)

    def test_snapshot_rejects_portable_platform(self) -> None:
        value = snapshot(True, CANDIDATE_VERSION, "2026-09-05T00:00:00Z")
        value["platform"]["family"] = "other"
        with self.assertRaisesRegex(MODULE.EvidenceError, "Kylin V11"):
            MODULE.validate_snapshot(value)


if __name__ == "__main__":
    unittest.main()
