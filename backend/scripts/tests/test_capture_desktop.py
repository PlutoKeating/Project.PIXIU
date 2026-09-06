"""Local-only safety tests; do not connect to a desktop or synthesize evidence."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "capture_desktop", Path(__file__).resolve().parents[1] / "capture_desktop.py"
)
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)


class CaptureSafetyTests(unittest.TestCase):
    def reject(self, arguments):
        argv = ["capture_desktop.py", "--guest", "example", "--domain", "example", *arguments]
        with patch("sys.argv", argv), patch.object(CAPTURE.subprocess, "run") as run:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                CAPTURE.main()
            self.assertEqual(error.exception.code, 2)
            run.assert_not_called()

    def test_invalid_dimensions(self):
        self.reject(["--width", "1", "move", "0", "0"])

    def test_negative_coordinate(self):
        self.reject(["click", "-1", "0"])

    def test_outside_display(self):
        self.reject(["move", "1440", "0"])

    def test_existing_output(self):
        self.reject(["capture", __file__])

    def test_missing_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.reject(["capture", str(Path(temporary) / "absent" / "screen.png")])

    def test_wrong_extension(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.reject(["capture", str(Path(temporary) / "screen.jpg")])

    def test_absolute_pointer_mapping(self):
        argv = ["capture_desktop.py", "--guest", "example", "--domain", "example",
                "move", "1439", "899"]
        with patch("sys.argv", argv), patch.object(CAPTURE.subprocess, "run") as run:
            CAPTURE.main()
        import json
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["virsh", "qemu-monitor-command", "example"])
        events = json.loads(command[3])["arguments"]["events"]
        self.assertEqual([event["data"]["value"] for event in events], [32767, 32767])


if __name__ == "__main__":
    unittest.main()
