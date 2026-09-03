#!/usr/bin/env python3
"""Unit tests for the sanitized native acceptance evidence collector."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/native-sdk-smoke.py"
SPEC = importlib.util.spec_from_file_location("native_sdk_smoke", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NativeSdkSmokeTest(unittest.TestCase):
    def test_main_binds_runtime_operations_to_installed_release(self) -> None:
        manifest = {
            "manifest_schema": 1,
            "product": {
                "name": "pixiu",
                "version": "0.1.7",
                "revision": "1",
                "debian_version": "0.1.7-1",
            },
            "build": {
                "git_commit": "a" * 40,
                "source_tree_clean": True,
                "architecture": "amd64",
                "profile": "kylin-v11-native-x86_64",
                "kysdk": "ON",
                "install_strict": True,
            },
            "interfaces": {
                "http_api": "v1",
                "agent_memory_api": 1,
                "database_schema": 12,
            },
        }
        capabilities = {
            "platform": {"family": "kylin", "version_major": "11", "v11": True},
            "embedding": {"configured": "kylin", "runtime": "kylin", "compliant": True},
            "vector_store": {"configured": "kylin", "runtime": "kylin", "compliant": True},
            "contest_ready": True,
        }
        responses = [
            {"product_version": "0.1.7", "component": "pixiu-memory-backend", "api_version": "v1", "agent_memory_api": 1, "schema_version": 12},
            {"status": "ready", "product_version": "0.1.7", "component": "pixiu-memory-backend", "database": "ok", "schema_version": 12},
            {"evidence_id": "evd_native", "status": "accepted"},
            {"source_knowledge": "knw_native"},
            {"targets": [{"id": "knw_native"}], "irreversible": True},
            {"status": "forgotten", "forgotten_ids": ["knw_native"]},
            {"source_knowledge": ""},
        ]
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            manifest_path = tmp / "release-manifest.json"
            output = tmp / "evidence.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            deb = tmp / "pixiu_0.1.7-1_amd64.deb"
            deb.write_bytes(b"test package")
            argv = [
                str(SCRIPT),
                "--deb",
                str(deb),
                "--expected-commit",
                "a" * 40,
                "--release-manifest",
                str(manifest_path),
                "--output",
                str(output),
            ]
            with (
                patch.object(MODULE, "wait_for_capabilities", return_value=capabilities),
                patch.object(MODULE, "request_json", side_effect=responses),
                patch.object(
                    MODULE,
                    "verify_candidate_package",
                    return_value={"sha256": "b" * 64},
                ),
                patch.object(
                    MODULE,
                    "run_direct_sdk_lifecycle",
                    return_value={
                        "collection_create": "passed",
                        "collection_load": "passed",
                        "vector_upsert": "passed",
                        "vector_search": "passed",
                        "vector_delete": "passed",
                        "collection_drop": "passed",
                    },
                ),
                patch.object(
                    MODULE,
                    "collect_installed_components",
                    return_value={
                        "architecture": "amd64",
                        "packages": {
                            "pixiu": "0.1.7-1",
                            "libkylin-coreai-embedding": "2.0.0",
                            "libkysdk-vector-engine-client": "1.4.0",
                        },
                        "agent_runtime": {"command": "hermes", "version": "0.9.8"},
                        "agent_host": {"command": "kylin-agent", "available": True},
                    },
                ),
                patch("builtins.print"),
                patch.object(sys, "argv", argv),
            ):
                self.assertEqual(MODULE.main(), 0)

            evidence = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(evidence["evidence_schema"], 1)
            self.assertEqual(evidence["release"]["git_commit"], "a" * 40)
            self.assertTrue(evidence["release"]["install_strict"])
            self.assertEqual(evidence["installed"]["packages"]["pixiu"], "0.1.7-1")
            self.assertEqual(evidence["agent_runtime"]["version"], "0.9.8")
            self.assertEqual(evidence["checks"]["vector_delete"], "passed")
            self.assertEqual(evidence["candidate_package"]["sha256"], "b" * 64)
            self.assertEqual(evidence["direct_sdk"]["collection_create"], "passed")
            self.assertNotIn("base_url", evidence)

    def test_release_identity_rejects_non_strict_manifest(self) -> None:
        manifest = {
            "product": {"name": "pixiu", "version": "0.1.7", "debian_version": "0.1.7-1"},
            "build": {"kysdk": "OFF", "install_strict": False},
        }
        with self.assertRaisesRegex(RuntimeError, "strict native"):
            MODULE.validate_release_identity(
                manifest,
                {"architecture": "amd64", "packages": {"pixiu": "0.1.7-1"}},
                {"product_version": "0.1.7"},
            )

    def test_direct_sdk_lifecycle_uses_and_removes_isolated_collection(self) -> None:
        calls: list[str] = []
        behavior = {"delete_count": 1}
        connection: dict[str, object] = {}

        class Embedder:
            def embed(self, text: str) -> list[float]:
                calls.append("embed")
                return [0.25, 0.75]

        class Client:
            def load_db_file(self, path: str) -> None:
                self.database_path = path
                calls.append("load_db")

            def disconnect(self) -> None:
                calls.append("disconnect")

            def has_collection(self, name: str) -> bool:
                calls.append("has")
                return getattr(self, "created", False)

            def create_collection(self, name: str, dimension: int, *flags: bool) -> None:
                self.name = name
                self.created = True
                calls.append("create")

            def load_collection(self, name: str) -> None:
                calls.append("load")

            def upsert(self, name: str, vectors: list, ids: list[int]) -> int:
                self.vector_id = ids[0]
                calls.append("upsert")
                return 1

            def search(self, name: str, vector: list[float], limit: int) -> list[dict]:
                calls.append("search")
                if getattr(self, "deleted", False):
                    return []
                return [{"id": self.vector_id, "score": 1.0}]

            def delete(self, name: str, ids: list[int]) -> int:
                calls.append("delete")
                self.deleted = True
                return behavior["delete_count"]

            def drop_collection(self, name: str) -> None:
                calls.append("drop")
                self.created = False

        clients: list[Client] = []

        def client_factory(**kwargs):
            connection.update(kwargs)
            client = Client()
            clients.append(client)
            return client

        result = MODULE.run_direct_sdk_lifecycle(
            embedder_factory=Embedder,
            client_factory=client_factory,
        )
        self.assertEqual(connection, {"app_id": "pixiu"})
        self.assertEqual(
            calls,
            [
                "embed",
                "load_db",
                "has",
                "create",
                "load",
                "upsert",
                "search",
                "delete",
                "search",
                "has",
                "drop",
                "has",
                "disconnect",
            ],
        )
        self.assertFalse(Path(clients[0].database_path).exists())
        self.assertEqual(result["collection_drop"], "passed")

        calls.clear()
        behavior["delete_count"] = 0
        with self.assertRaisesRegex(RuntimeError, "did not affect one row"):
            MODULE.run_direct_sdk_lifecycle(
                embedder_factory=Embedder,
                client_factory=client_factory,
            )
        self.assertEqual(calls[-4:], ["has", "drop", "has", "disconnect"])

    def test_rejects_non_loopback_service_url(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "loopback"):
            MODULE.validate_base_url("https://example.com:8765")

    def test_installed_package_path_precedes_checkout(self) -> None:
        original = list(sys.path)
        try:
            sys.path[:] = ["", "/usr/lib/pixiu", "/checkout", "/usr/lib/pixiu"]
            MODULE.prioritize_installed_root()
            self.assertEqual(sys.path[0], "/usr/lib/pixiu")
            self.assertEqual(sys.path.count("/usr/lib/pixiu"), 1)
        finally:
            sys.path[:] = original

    def test_memory_failure_triggers_best_effort_cleanup(self) -> None:
        calls: list[tuple[str, dict | None]] = []

        def request(url: str, *, payload: dict | None = None) -> dict:
            calls.append((url, payload))
            if url.endswith("/memory/write"):
                return {"status": "accepted", "evidence_id": "evd_cleanup"}
            if url.endswith("/memory/query"):
                raise RuntimeError("query failed")
            return {"status": "forgotten", "forgotten_ids": []}

        with patch.object(MODULE, "request_json", side_effect=request):
            with self.assertRaisesRegex(RuntimeError, "query failed"):
                MODULE.run_memory_lifecycle("http://127.0.0.1:8765")
        self.assertEqual(calls[-1][0], "http://127.0.0.1:8765/forget")
        self.assertTrue(calls[-1][1]["confirm"])

    def test_candidate_package_binds_checksum_commit_and_installed_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            deb = tmp / "pixiu_0.1.7-1_amd64.deb"
            deb.write_bytes(b"candidate")
            digest = hashlib.sha256(b"candidate").hexdigest()
            Path(f"{deb}.sha256").write_text(
                f"{digest}  {deb.name}\n", encoding="utf-8"
            )
            installed_manifest = tmp / "release-manifest.json"
            installed_manifest.write_text('{"manifest_schema": 1}\n', encoding="utf-8")
            manifest = {
                "product": {"debian_version": "0.1.7-1"},
                "build": {"git_commit": "a" * 40, "architecture": "amd64"},
            }

            def extract(command: list[str], **kwargs) -> None:
                extracted = Path(command[-1]) / "usr/share/pixiu"
                extracted.mkdir(parents=True)
                (extracted / "release-manifest.json").write_bytes(
                    installed_manifest.read_bytes()
                )

            with (
                patch.object(
                    MODULE,
                    "command_output",
                    side_effect=["pixiu", "0.1.7-1", "amd64"],
                ),
                patch.object(MODULE.subprocess, "run", side_effect=extract),
            ):
                result = MODULE.verify_candidate_package(
                    deb, installed_manifest, manifest, "a" * 40
                )
            self.assertEqual(result["sha256"], digest)
            self.assertEqual(result["filename"], deb.name)


if __name__ == "__main__":
    unittest.main()
