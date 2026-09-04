#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "build/release/agent-runtime/make-wheel-lock.py"


class WheelLockTest(unittest.TestCase):
    def test_generates_sorted_hash_locked_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for filename, name, version in (
                ("zeta.whl", "Zeta_Pkg", "2.0"),
                ("alpha.whl", "alpha", "1.0"),
            ):
                with zipfile.ZipFile(root / filename, "w") as archive:
                    archive.writestr(
                        f"{name}-{version}.dist-info/METADATA",
                        f"Name: {name}\nVersion: {version}\n",
                    )
            output = root / "runtime.lock"
            subprocess.run(["python3", str(SCRIPT), str(root), str(output)], check=True)
            lines = [line for line in output.read_text().splitlines() if not line.startswith("#")]
            self.assertEqual([line.split("==", 1)[0] for line in lines], ["alpha", "zeta-pkg"])
            for line in lines:
                name = line.split("==", 1)[0]
                wheel = root / ("alpha.whl" if name == "alpha" else "zeta.whl")
                self.assertIn(hashlib.sha256(wheel.read_bytes()).hexdigest(), line)


if __name__ == "__main__":
    unittest.main()
