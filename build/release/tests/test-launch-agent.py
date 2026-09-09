"""The desktop bootstrap reads the profile, never evaluates shell input."""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "backend/platform/session/launch-agent.py"
spec = importlib.util.spec_from_file_location("pixiu_launch_agent", SCRIPT)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LaunchAgentTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.profile = Path(self.directory.name)
        self.env_file = self.profile / ".env"
        self.environment = {"HERMES_HOME": str(self.profile), "LANG": "C.UTF-8"}

    def write(self, text):
        self.env_file.write_text(text, encoding="utf-8")

    def test_profile_precedes_shell_and_only_connection_values_are_exported(self):
        self.write("PIXIU_AGENT_SCOPE='user:alice'\n"
                   "PIXIU_AGENT_ENDPOINT=https://memory.example.test/\n"
                   "EXAMPLE_API_KEY=synthetic-secret\nLD_PRELOAD=not-a-library\n")
        before = self.env_file.read_bytes()
        self.environment.update(PIXIU_AGENT_SCOPE="user:stale",
                                PIXIU_AGENT_ENDPOINT="http://stale.example.test")
        result = launcher.resolve_environment(self.environment)
        self.assertEqual(result["PIXIU_AGENT_SCOPE"], "user:alice")
        self.assertEqual(result["PIXIU_BACKEND_URL"], "https://memory.example.test")
        self.assertEqual(result["PIXIU_AGENT_ENDPOINT"], result["PIXIU_BACKEND_URL"])
        self.assertEqual(result["LANG"], "C.UTF-8")
        self.assertNotIn("EXAMPLE_API_KEY", result)
        self.assertNotIn("LD_PRELOAD", result)
        self.assertEqual(self.env_file.read_bytes(), before)

    def test_defaults_and_shared_scope_are_not_rewritten(self):
        self.write("")
        self.assertEqual(launcher.resolve_environment(self.environment)["PIXIU_AGENT_SCOPE"], "user:default")
        self.write("export PIXIU_AGENT_SCOPE=shared:team\n")
        self.assertEqual(launcher.resolve_environment(self.environment)["PIXIU_AGENT_SCOPE"], "shared:team")

    def test_shell_substitution_is_never_executed(self):
        marker = self.profile / "must-not-exist"
        self.write(f"PIXIU_AGENT_SCOPE=$(touch {marker})\n")
        with self.assertRaises(ValueError):
            launcher.resolve_environment(self.environment)
        self.assertFalse(marker.exists())

    def test_interpolation_and_duplicate_values_follow_runtime_dotenv_semantics(self):
        self.write("DOMAIN=alice\nPIXIU_AGENT_SCOPE=user:old\n"
                   "PIXIU_AGENT_SCOPE=user:${DOMAIN}\n")
        with patch.dict(os.environ, self.environment, clear=True):
            self.assertEqual(launcher.resolve_environment(self.environment)["PIXIU_AGENT_SCOPE"], "user:alice")

    def test_missing_invalid_and_conflicting_configuration_fails_closed(self):
        with self.assertRaises(OSError):
            launcher.resolve_environment(self.environment)
        for contents in ("PIXIU_AGENT_SCOPE='unterminated\n", "PIXIU_AGENT_SCOPE=\n",
                         "PIXIU_AGENT_ENDPOINT=https://user:secret@example.test\n",
                         "PIXIU_AGENT_ENDPOINT=file:///tmp/memory\n",
                         "PIXIU_AGENT_ENDPOINT=http://example.test:99999\n",
                         "PIXIU_AGENT_ENDPOINT=http://example.test/?token=secret\n"):
            with self.subTest(contents=contents):
                self.write(contents)
                with self.assertRaises(ValueError):
                    launcher.resolve_environment(self.environment)
        self.write("PIXIU_AGENT_ENDPOINT=http://example.test\n")
        self.environment["PIXIU_BACKEND_URL"] = "http://different.example.test"
        with self.assertRaises(ValueError):
            launcher.resolve_environment(self.environment)

    def test_exec_preserves_arguments_and_does_not_create_another_frontend(self):
        self.write("PIXIU_AGENT_SCOPE=user:alice\n")
        with patch.dict(os.environ, self.environment, clear=True), \
                patch.object(launcher.sys, "argv", [str(SCRIPT), "--show"]), \
                patch.object(launcher.os, "execve") as execute:
            self.assertEqual(launcher.main(), 0)
        self.assertEqual(execute.call_args.args[:2], ("/usr/bin/kylin-agent", ["kylin-agent", "--show"]))
        self.assertEqual(execute.call_args.args[2]["PIXIU_AGENT_SCOPE"], "user:alice")


if __name__ == "__main__":
    unittest.main()
