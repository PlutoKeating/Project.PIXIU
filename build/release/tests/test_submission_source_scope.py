"""Verify the delivery filter retains build inputs and rejects development payloads."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'build/release/scripts'))
spec = importlib.util.spec_from_file_location('prepare_submission', ROOT / 'build/release/scripts/prepare-submission.py')
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


class SourceScopeTests(unittest.TestCase):
    def test_required_host_adaptation_inputs(self):
        for name in source.FRONTEND_INPUTS:
            self.assertTrue(source.selected(name), name)

    def test_development_trees_excluded_at_any_depth(self):
        for name in ['.github/workflows/build.yml', 'website/package.json',
                     'frontend/tests/test.cpp', 'backend/tests/test_api.py',
                     'backend/foundation/docs/ARCHITECTURE.md',
                     'backend/foundation/evidence/pressure_test_report.md',
                     'backend/foundation/eval/tests/test_eval.py',
                     'frontend/src/.git/config', 'build/release/out/pixiu.deb']:
            self.assertFalse(source.selected(name), name)

    def test_product_runtime_assets_kept(self):
        for name in ['gateway/web_dist/index.html', 'skills/tools/SKILL.md',
                     'plugins/search/plugin.yaml', 'agent/redact.py', 'setup.py']:
            self.assertTrue(source.upstream_selected('third_party/kylin-agent-runtime/', name), name)

    def test_runtime_development_artifacts_removed(self):
        for name in ['website/index.html', '.github/workflows/ci.yml',
                     'skills/.curator_backups/old/skills.tar.gz', 'skills/.usage.json',
                     'plugins/example/tests/test_plugin.py',
                     'plugins/example/docs/assets/demo.png']:
            self.assertFalse(source.upstream_selected('third_party/kylin-agent-runtime/', name), name)

    def test_sdk_headers_and_licenses_only(self):
        for prefix in ['third_party/kylin-coreai-embedding/', 'third_party/libkysdk-vector-engine-client/']:
            self.assertTrue(source.upstream_selected(prefix, 'include/api.h'))
            self.assertTrue(source.upstream_selected(prefix, 'LICENSE'))
            self.assertFalse(source.upstream_selected(prefix, 'examples/demo.cpp'))
        self.assertTrue(source.upstream_selected('third_party/kreuzberg/', 'LICENSE'))
        self.assertFalse(source.upstream_selected('third_party/kreuzberg/', 'crates/src/lib.rs'))


if __name__ == '__main__':
    unittest.main()
