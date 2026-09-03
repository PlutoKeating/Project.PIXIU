#!/usr/bin/env python3
"""Tests for the frozen final dataset manifest."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/final-dataset-manifest.py"
SPEC = importlib.util.spec_from_file_location("final_dataset_manifest", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def native() -> dict:
    return {
        "evidence_class": "kylin-v11-native-sdk-product-lifecycle",
        "real_device_evidence": True,
        "status": "pass",
        "release": {"git_commit": "a" * 40, "profile": "kylin-v11-native-x86_64", "kysdk": "ON", "install_strict": True},
        "candidate_package": {"sha256": "b" * 64},
    }


class Dataset:
    def model_dump(self, mode: str) -> dict:
        cases = []
        for kind, count in (("retrieval", 50), ("preference", 15), ("conflict", 25)):
            cases.extend({"id": f"{kind}-{index}", "task": kind} for index in range(count))
        return {
            "schema_version": "1.0",
            "name": "pixiu-family-expense-v1",
            "profile": "acceptance",
            "retrieval_repetitions": 20,
            "fixtures": [{"id": index} for index in range(50)],
            "cases": cases,
            "thresholds": {},
            "metadata": {"synthetic": True},
        }


class FinalDatasetManifestTest(unittest.TestCase):
    def test_builds_honest_frozen_test_only_manifest(self) -> None:
        rendered, manifest = MODULE.build_manifest(
            Dataset(), native(), MODULE.OFFICIAL_SOURCE_SHA256
        )
        MODULE.validate_manifest(manifest)
        self.assertEqual(manifest["provenance"]["kind"], "team-authored-synthetic-corpus")
        self.assertFalse(manifest["provenance"]["third_party_dataset"])
        self.assertEqual(manifest["split"]["test_count"], 90)
        self.assertEqual(manifest["dataset"]["artifact_sha256"], MODULE.sha256_bytes(rendered))

    def test_rejects_changed_official_source(self) -> None:
        with self.assertRaisesRegex(MODULE.EvidenceError, "official problem"):
            MODULE.build_manifest(Dataset(), native(), "0" * 64)

    def test_rejects_sensitive_dataset_value(self) -> None:
        class SensitiveDataset(Dataset):
            def model_dump(self, mode: str) -> dict:
                value = super().model_dump(mode)
                value["metadata"]["token"] = "Bearer example-sensitive-token"
                return value

        with self.assertRaisesRegex(MODULE.EvidenceError, "sensitive"):
            MODULE.build_manifest(
                SensitiveDataset(), native(), MODULE.OFFICIAL_SOURCE_SHA256
            )

    def test_atomic_pair_refuses_existing_output(self) -> None:
        rendered, manifest = MODULE.build_manifest(
            Dataset(), native(), MODULE.OFFICIAL_SOURCE_SHA256
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset_path = root / "dataset.json"
            manifest_path = root / "manifest.json"
            MODULE.write_pair(dataset_path, rendered, manifest_path, manifest)
            self.assertEqual(json.loads(manifest_path.read_text()), manifest)
            with self.assertRaisesRegex(MODULE.EvidenceError, "must not already exist"):
                MODULE.write_pair(dataset_path, rendered, manifest_path, manifest)


if __name__ == "__main__":
    unittest.main()
