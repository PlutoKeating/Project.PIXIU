from __future__ import annotations

import importlib.util
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "build_source_archive.py"
SPEC = importlib.util.spec_from_file_location("build_source_archive", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
BUILDER_SCRIPT = Path(__file__).resolve().parents[1] / "build_submission.py"
BUILDER_SPEC = importlib.util.spec_from_file_location("build_submission_for_source", BUILDER_SCRIPT)
BUILDER = importlib.util.module_from_spec(BUILDER_SPEC)
assert BUILDER_SPEC.loader is not None
BUILDER_SPEC.loader.exec_module(BUILDER)
MODULE_REQUIRED_SUBMODULES = BUILDER.REQUIRED_SUBMODULES


class SourceArchiveTest(unittest.TestCase):
    def test_tracked_paths_exclude_review_and_final_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "backend/app.py"
            delivery = root / "submission/05-功能演示视频/demo.mp4"
            for path in (source, delivery):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")
            tracked = b"backend/app.py\0submission/05-demo.mp4\0"
            with mock.patch.object(MODULE, "git", return_value=tracked):
                self.assertEqual(MODULE.tracked_paths(root), [Path("backend/app.py")])

    def test_archive_contains_sources_evidence_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            relative_paths = [
                Path("README.md"),
                Path("VERSION"),
                Path("backend/app.py"),
                Path("frontend/app.cpp"),
                Path("integrations/kylin_agent/plugin.py"),
                Path("build/release/README.md"),
                Path("docs/delivery/README.md"),
                Path("third_party/kylin-agent/README.md"),
                Path("third_party/kylin-agent-runtime/README.md"),
                Path("third_party/kylin-coreai-embedding/README.md"),
                Path("third_party/libkysdk-vector-engine-client/README.md"),
            ]
            for relative in relative_paths:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative.as_posix() + "\n", encoding="utf-8")
            evidence = root / "evidence"
            evidence.mkdir()
            (evidence / "NOTICE.agent.txt").write_text("notice\n", encoding="utf-8")
            output = root / "source.tar.gz"
            submodule_status = "".join(
                f" {'1' * 40} {name} (v1)\n"
                for name in sorted(MODULE_REQUIRED_SUBMODULES)
            ).encode()
            with mock.patch.object(
                MODULE,
                "git",
                side_effect=lambda _root, *args: (
                    b"a" * 40 + b"\n"
                    if args[:2] == ("rev-parse", "HEAD")
                    else submodule_status
                ),
            ):
                manifest = MODULE.create_archive(
                    root, output, evidence, relative_paths, 0
                )
            with tarfile.open(output, "r:gz") as archive:
                names = set(archive.getnames())
                embedded = json.load(
                    archive.extractfile(f"{MODULE.ARCHIVE_PREFIX}/SOURCE_MANIFEST.json")
                )
            self.assertIn(f"{MODULE.ARCHIVE_PREFIX}/backend/app.py", names)
            self.assertIn(
                f"{MODULE.ARCHIVE_PREFIX}/release-evidence/agent-supply-chain/NOTICE.agent.txt",
                names,
            )
            self.assertEqual(embedded, manifest)
            self.assertEqual(manifest["release_commit"], "a" * 40)
            expected_sources = {
                relative.as_posix(): {
                    "type": "file",
                    "sha256": MODULE.sha256_file(root / relative),
                }
                for relative in relative_paths
            }
            with (
                mock.patch.object(BUILDER, "git", return_value="1" * 40),
                mock.patch.object(
                    BUILDER, "worktree_source_entries", return_value=expected_sources
                ),
            ):
                self.assertEqual(
                    BUILDER.validate_source_archive(output, release_commit="a" * 40),
                    [],
                )
                changed_sources = dict(expected_sources)
                changed_sources["README.md"] = {
                    "type": "file",
                    "sha256": "f" * 64,
                }
                with mock.patch.object(
                    BUILDER,
                    "worktree_source_entries",
                    return_value=changed_sources,
                ):
                    self.assertIn(
                        "source archive differs from release checkout: README.md",
                        BUILDER.validate_source_archive(
                            output, release_commit="a" * 40
                        ),
                    )

    def test_existing_archive_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "source.tar.gz"
            output.write_bytes(b"owned")
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                MODULE.create_archive(root, output, root, [], 0)


if __name__ == "__main__":
    unittest.main()
