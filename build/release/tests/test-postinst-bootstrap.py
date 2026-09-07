"""Execute postinst's bootstrap boundary without root or host filesystem writes."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
POSTINST = ROOT / "build/release/debian/postinst"


class BootstrapTests(unittest.TestCase):
    def test_dependency_installations_have_no_online_fallback(self):
        source = POSTINST.read_text(encoding="utf-8")
        calls = [line.strip() for line in source.splitlines()
                 if line.strip().startswith("install_reqs ")]
        self.assertEqual(len(calls), 3)
        self.assertTrue(all("--no-index" in call for call in calls))
        self.assertNotIn("get-pip.py", source)
        self.assertNotIn("--break-system-packages", source)
        self.assertIn('"${VPY}" -m pip check', source)

    def run_bootstrap(self, *, existing=False, system_abi=True, venv_abi=True,
                      pip=True, create=True):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / "pixiu"
            venv = library / "venv"
            calls = root / "calls"
            fake = root / "python"
            fake.write_text("""#!/bin/sh
printf '%s|%s\n' "$0" "$*" >> "$TEST_CALLS"
if [ "$1" = -c ]; then
    case "$0" in
        */venv/bin/python) exit "$TEST_VENV_ABI" ;;
        *) exit "$TEST_SYSTEM_ABI" ;;
    esac
fi
if [ "$1 $2" = '-m venv' ]; then
    [ "$TEST_CREATE" = 0 ] || exit 9
    mkdir -p "$3/bin"
    cp "$0" "$3/bin/python"
    exit 0
fi
if [ "$1 $2 $3" = '-m pip --version' ]; then
    exit "$TEST_PIP"
fi
exit 88
""", encoding="utf-8")
            fake.chmod(0o755)
            if existing:
                (venv / "bin").mkdir(parents=True)
                (venv / "bin/python").write_bytes(fake.read_bytes())
                (venv / "bin/python").chmod(0o755)
                (venv / "preserve").write_text("installed data", encoding="utf-8")
            # Test the production bootstrap, stopping before dependency installs
            # and service operations. No test-path overrides enter shipped code.
            source = POSTINST.read_text(encoding="utf-8")
            prefix, delimiter, _ = source.partition('REQ="${PIXIU_LIB}/backend/requirements.txt"')
            self.assertTrue(delimiter)
            script = root / "postinst"
            script.write_text(prefix.replace("PIXIU_LIB=/usr/lib/pixiu", f'PIXIU_LIB="{library}"')
                              .replace("PY=/usr/bin/python3", f'PY="{fake}"'), encoding="utf-8")
            env = dict(os.environ, TEST_CALLS=str(calls),
                       TEST_SYSTEM_ABI=str(int(not system_abi)),
                       TEST_VENV_ABI=str(int(not venv_abi)),
                       TEST_PIP=str(int(not pip)), TEST_CREATE=str(int(not create)))
            result = subprocess.run(["sh", str(script)], env=env, capture_output=True,
                                    text=True, timeout=10)
            log = calls.read_text(encoding="utf-8")
            self.assertNotIn("install", log)
            if existing:
                self.assertEqual((venv / "preserve").read_text(), "installed data")
                self.assertNotIn("-m venv", log)
            if not system_abi:
                self.assertFalse(venv.exists())
            return result, log

    def test_fresh_venv_without_system_pip(self):
        result, log = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-m venv", log)
        self.assertIn("/venv/bin/python|-m pip --version", log)

    def test_existing_venv_is_preserved(self):
        result, _ = self.run_bootstrap(existing=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failures_do_not_fall_back(self):
        for options in ({"system_abi": False}, {"create": False},
                        {"existing": True, "venv_abi": False},
                        {"existing": True, "pip": False}):
            with self.subTest(options=options):
                result, _ = self.run_bootstrap(**options)
                self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
