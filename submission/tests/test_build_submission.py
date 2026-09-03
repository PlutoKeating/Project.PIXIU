from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "build_submission.py"
SPEC = importlib.util.spec_from_file_location("build_submission", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SubmissionBuilderTest(unittest.TestCase):
    def test_repository_plan_is_structurally_valid(self) -> None:
        self.assertEqual(MODULE.validate_plan(MODULE.load_plan(), require_ready=False), [])

    def test_pending_plan_refuses_final_package(self) -> None:
        errors = MODULE.validate_plan(MODULE.load_plan(), require_ready=True)
        self.assertIn("release_ready is false", errors)
        self.assertTrue(any(error.startswith("release gates not passed:") for error in errors))

    def test_package_contains_checksums_but_not_itself_in_checksum_list(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "entry"
            package.mkdir()
            (package / "document.pdf").write_bytes(b"document")
            with mock.patch.object(MODULE, "FINAL_ROOT", root):
                output = MODULE.write_checksums_and_zip({"submission_name": "entry"})
            self.assertTrue(output.is_file())
            checksums = (package / "SHA256SUMS").read_text(encoding="utf-8")
            self.assertIn("document.pdf", checksums)
            self.assertIn("SUBMISSION_MANIFEST.json", checksums)
            self.assertNotIn("SHA256SUMS", checksums)


if __name__ == "__main__":
    unittest.main()
