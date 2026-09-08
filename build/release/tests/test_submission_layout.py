"""Reject plausible but invalid competition submission trees."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location("submission_layout", Path(__file__).resolve().parents[1] / "scripts/submission_layout.py")
layout = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(layout)


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.outer = self.root / "submission/申报目录"
        self.materials = self.outer / "申报目录"
        self.source = self.outer / "源代码"
        self.materials.mkdir(parents=True)
        self.source.mkdir()
        self.doc = self.materials / "技术方案.doc"
        self.doc.write_bytes(bytes.fromhex("d0cf11e0a1b11ae1"))
        (self.source / "PIXIU源代码.tar.gz").write_bytes(b"fixture")
        with zipfile.ZipFile(self.materials / "项目报告.pptx", "w") as archive:
            archive.writestr("ppt/presentation.xml", "<presentation/>")
        self.patcher = patch.object(layout, "paths", return_value=(self.outer, self.materials, self.source))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_only_video_may_be_pending(self):
        self.assertEqual(len(layout.validate(self.root)), 1)
        with self.assertRaises(ValueError):
            layout.validate(self.root, require_video=True)

    def test_extra_readme_rejected(self):
        (self.outer / "README.md").write_text("说明")
        with self.assertRaises(ValueError):
            layout.validate(self.root)

    def test_authorized_video_workspace_excluded_from_formal_tree(self):
        work = self.root / "submission/video-production/raw/screenshots"
        work.mkdir(parents=True)
        (work / "sample.png").write_bytes(b"production-only")
        self.assertEqual(len(layout.validate(self.root)), 1)
        # Excluding the workspace must not allow extra content in the submission.
        (self.materials / "sample.png").write_bytes(b"not-a-deliverable")
        with self.assertRaises(ValueError):
            layout.validate(self.root)

    def test_unexpected_sibling_rejected(self):
        (self.root / "submission/extra").mkdir()
        with self.assertRaises(ValueError):
            layout.validate(self.root)

    def test_video_workspace_symlink_rejected(self):
        (self.root / "submission/video-production").symlink_to(self.outer, target_is_directory=True)
        with self.assertRaises(ValueError):
            layout.validate(self.root)

    def test_empty_extra_directory_rejected(self):
        (self.outer / "原始截图").mkdir()
        with self.assertRaises(ValueError):
            layout.validate(self.root)

    def test_renamed_docx_rejected(self):
        with zipfile.ZipFile(self.doc, "w") as archive:
            archive.writestr("word/document.xml", "<document/>")
        with self.assertRaises(ValueError):
            layout.validate(self.root)

    def test_wrong_filename_rejected(self):
        self.doc.rename(self.doc.with_name("技术方案及测试结果.doc"))
        with self.assertRaises(ValueError):
            layout.validate(self.root)

    def test_empty_video_zip_rejected(self):
        with zipfile.ZipFile(self.materials / "演示视频.zip", "w"):
            pass
        with self.assertRaises(ValueError):
            layout.validate(self.root)


if __name__ == "__main__":
    unittest.main()
