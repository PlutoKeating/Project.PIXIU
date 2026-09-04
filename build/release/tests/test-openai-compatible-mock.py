#!/usr/bin/env python3
"""Public-contract tests for the deterministic OpenAI-compatible test node."""

from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "build/release/testing/openai-compatible-mock.py"
RUNNER = ROOT / "build/release/testing/run-agent-mock-acceptance.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("pixiu_mock_acceptance", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load mock acceptance runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class MockNodeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.ready = Path(self.temp.name) / "ready.json"
        self.process = subprocess.Popen(
            [
                sys.executable,
                str(SERVER),
                "--host",
                "127.0.0.1",
                "--port",
                "0",
                "--api-key",
                "test-secret",
                "--ready-file",
                str(self.ready),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not self.ready.exists():
            if self.process.poll() is not None:
                break
            time.sleep(0.02)
        if not self.ready.exists():
            stdout, stderr = self.process.communicate(timeout=1)
            self.fail(f"mock node did not start: {stdout}\n{stderr}")
        self.base_url = json.loads(self.ready.read_text(encoding="utf-8"))["base_url"]

    def tearDown(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
        self.process.communicate(timeout=3)
        self.temp.cleanup()

    def request(self, method: str, path: str, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            self.base_url + path,
            method=method,
            data=data,
            headers={
                "Authorization": "Bearer test-secret",
                "Content-Type": "application/json",
            },
        )
        return urllib.request.urlopen(request, timeout=3)

    def test_models_and_streaming_tool_call_are_openai_compatible(self) -> None:
        with self.request("GET", "/v1/models") as response:
            models = json.load(response)
        self.assertEqual(models["object"], "list")
        self.assertEqual(models["data"][0]["id"], "pixiu-e2e-mock")

        payload = {
            "model": "pixiu-e2e-mock",
            "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [
                {"role": "system", "content": "You are an OS Agent with tools and memory."},
                {"role": "user", "content": "请使用系统命令读取文件 /tmp/pixiu-safe-marker.txt 的内容。"},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "terminal",
                        "parameters": {"type": "object"},
                    },
                }
            ],
        }
        with self.request("POST", "/v1/chat/completions", payload) as response:
            body = response.read().decode()
        self.assertIn('"name": "terminal"', body)
        self.assertIn('"finish_reason": "tool_calls"', body)
        self.assertTrue(body.rstrip().endswith("data: [DONE]"))

        with self.request("GET", "/_test/trace") as response:
            trace = json.load(response)
        self.assertEqual(trace["requests"][0]["selected_tool"], "terminal")
        self.assertEqual(trace["requests"][0]["system_message_count"], 1)
        self.assertEqual(trace["requests"][0]["user_turn_count"], 1)
        self.assertNotIn("test-secret", json.dumps(trace))
        self.assertNotIn("pixiu-safe-marker", json.dumps(trace))

    def test_gateway_server_agent_model_alias_is_accepted(self) -> None:
        payload = {
            "model": "hermes-agent",
            "messages": [
                {"role": "system", "content": "System Agent"},
                {"role": "user", "content": "普通多轮对话"},
            ],
        }
        with self.request("POST", "/v1/chat/completions", payload) as response:
            completion = json.load(response)
        self.assertEqual(completion["model"], "hermes-agent")
        self.assertEqual(completion["choices"][0]["finish_reason"], "stop")

    def test_desktop_cloud_model_identifier_is_accepted_for_test_routing(self) -> None:
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "System Agent"},
                {"role": "user", "content": "你好"},
            ],
        }
        with self.request("POST", "/v1/chat/completions", payload) as response:
            completion = json.load(response)
        self.assertEqual(completion["model"], "deepseek-chat")

    def test_generic_summary_word_uses_retained_context_response(self) -> None:
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "System Agent"},
                {"role": "user", "content": "第一轮：请记住偏好。"},
                {"role": "assistant", "content": "已保存。"},
                {"role": "user", "content": "请概括我们刚才连续两轮完成了什么。"},
            ],
        }
        with self.request("POST", "/v1/chat/completions", payload) as response:
            completion = json.load(response)
        content = completion["choices"][0]["message"]["content"]
        self.assertIn("偏好保存", content)

    def test_memory_suite_covers_shared_memory_without_repeating_network(self) -> None:
        runner = load_runner()
        scenario = runner.scenario_for_suite(
            "memory", "PIXIU-" + "A" * 32, Path("/tmp/unused-marker.txt")
        )
        self.assertEqual(
            scenario.required_tools,
            {
                "pixiu_memory_remember",
                "pixiu_memory_search",
                "pixiu_memory_update",
                "pixiu_sync_status",
            },
        )
        self.assertNotIn("web_search", scenario.required_tools)
        self.assertNotIn("terminal", scenario.required_tools)
        self.assertEqual(len(scenario.prompts), 4)
        self.assertEqual(scenario.search_run_index, 1)

    def test_full_suite_keeps_real_web_and_terminal_coverage(self) -> None:
        runner = load_runner()
        scenario = runner.scenario_for_suite(
            "full", "PIXIU-" + "B" * 32, Path("/tmp/marker.txt")
        )
        self.assertIn("web_search", scenario.required_tools)
        self.assertIn("terminal", scenario.required_tools)
        self.assertEqual(len(scenario.prompts), 6)
        self.assertEqual(scenario.search_run_index, 3)

    def test_unknown_suite_fails_closed(self) -> None:
        runner = load_runner()
        with self.assertRaisesRegex(runner.AcceptanceError, "unsupported acceptance suite"):
            runner.scenario_for_suite(
                "unknown", "PIXIU-" + "C" * 32, Path("/tmp/unused-marker.txt")
            )


if __name__ == "__main__":
    unittest.main()
