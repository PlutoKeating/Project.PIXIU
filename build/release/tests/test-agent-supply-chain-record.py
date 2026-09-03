#!/usr/bin/env python3
"""Integration tests for Agent supply-chain evidence recording."""

from __future__ import annotations

import json
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RECORDER = ROOT / "build/release/scripts/record-agent-supply-chain.py"
AUDITOR = ROOT / "build/release/scripts/audit-agent-supply-chain.py"


def wheel(path: Path, name: str, version: str, license_id: str = "MIT") -> None:
    metadata_dir = f"{name.replace('-', '_')}-{version}.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"{metadata_dir}/METADATA",
            f"Name: {name}\nVersion: {version}\nLicense-Expression: {license_id}\n",
        )


class AgentSupplyChainRecordTest(unittest.TestCase):
    def run_record(self, evidence: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(RECORDER),
                "--root",
                str(ROOT),
                "--evidence-dir",
                str(evidence),
                *args,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_records_artifact_backed_documents_accepted_by_auditor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            evidence, inputs = work / "evidence", work / "inputs"
            inputs.mkdir()
            artifact, source, build_log = inputs / "kylin-agent", inputs / "source.tar.gz", inputs / "build.log"
            artifact.write_bytes(b"host artifact")
            source_file = inputs / "source.txt"
            source_file.write_text("corresponding source\n", encoding="utf-8")
            with tarfile.open(source, "w:gz") as archive:
                archive.add(source_file, arcname="source.txt")
            build_log.write_text("offline build passed\n", encoding="utf-8")
            result = self.run_record(
                evidence,
                "host-build",
                "--target-arch", "amd64",
                "--artifact", str(artifact),
                "--source-archive", str(source),
                "--build-log", str(build_log),
                "--network-isolated",
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            wheels = inputs / "wheels"
            wheels.mkdir()
            wheel(wheels / "runtime.whl", "kylin-agent-runtime", "0.9.8")
            wheel(wheels / "aiohttp.whl", "aiohttp", "3.13.3", "Apache-2.0")
            lock, install_log = inputs / "runtime.lock", inputs / "install.log"
            lock.write_text("locked\n", encoding="utf-8")
            install_log.write_text("offline install passed\n", encoding="utf-8")
            result = self.run_record(
                evidence,
                "runtime-wheelhouse",
                "--target-arch", "amd64",
                "--python-abi", "cp311",
                "--wheelhouse", str(wheels),
                "--lockfile", str(lock),
                "--offline-install-log", str(install_log),
                "--network-isolated",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            result = self.run_record(evidence, "legal")
            self.assertEqual(result.returncode, 0, result.stderr)

            audit = work / "audit.json"
            subprocess.run(
                ["python3", str(AUDITOR), "--root", str(ROOT), "--evidence-dir", str(evidence), "--output", str(audit)],
                check=True,
            )
            report = json.loads(audit.read_text(encoding="utf-8"))
            self.assertTrue(all(item.get("valid") for item in report["evidence"].values()))
            self.assertEqual(report["blockers"], ["authenticated-url-detected"])

    def test_rejects_authenticated_url_in_log(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            for name in ("artifact", "source"):
                (work / name).write_bytes(name.encode())
            log = work / "build.log"
            log.write_text("https://user:token@example.invalid/repo\n", encoding="utf-8")
            result = self.run_record(
                work / "evidence",
                "host-build",
                "--target-arch", "amd64",
                "--artifact", str(work / "artifact"),
                "--source-archive", str(work / "source"),
                "--build-log", str(log),
                "--network-isolated",
            )
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("token", result.stderr)


if __name__ == "__main__":
    unittest.main()
