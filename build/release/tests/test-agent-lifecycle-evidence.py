#!/usr/bin/env python3
"""Tests for the real-Agent lifecycle evidence gate."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/agent-lifecycle-evidence.py"
SPEC = importlib.util.spec_from_file_location("agent_lifecycle_evidence", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def scenario() -> dict:
    return {
        "schema_version": 1,
        "turns": [
            "请先了解我的偏好，并自行选择合适方式为后续任务准备上下文。",
            "请检查文件 {{ARTIFACT_PATH}} 的内容，并保留其中随机标记供稍后会话使用。",
            "请联网查询 openKylin 官方站点的项目简介，并保留有长期价值的结论。",
        ],
        "restore_prompt": "请概括我们之前连续对话完成了哪些类别的任务。",
        "cross_session_prompt": "请从长期记忆中找回本次验收保存的随机标记并原样回答。",
    }


def native() -> dict:
    return {
        "evidence_class": "kylin-v11-native-sdk-product-lifecycle",
        "real_device_evidence": True,
        "status": "pass",
        "release": {
            "git_commit": "a" * 40,
            "profile": "kylin-v11-native-x86_64",
            "kysdk": "ON",
            "install_strict": True,
        },
        "candidate_package": {"sha256": "b" * 64},
        "capabilities": {
            "contest_ready": True,
            "platform": {"family": "kylin", "version_major": "11", "v11": True},
            "embedding": {"configured": "kylin", "runtime": "kylin", "compliant": True},
            "vector_store": {"configured": "kylin", "runtime": "kylin", "compliant": True},
        },
        "agent_host": {"available": True},
        "agent_runtime": {"version": "0.9.8"},
        "checks": {
            "contest_ready": "passed",
            "memory_write": "passed",
            "vector_search": "passed",
            "vector_delete": "passed",
            "deleted_memory_hidden": "passed",
        },
    }


def messages(count: int) -> list[dict]:
    return [
        {"role": "user" if index % 2 == 0 else "assistant", "content": f"message-{index}"}
        for index in range(count)
    ]


class FakeBeforeClient:
    def __init__(self, *, remember_last: bool = True) -> None:
        self.index = 0
        self.remember_last = remember_last

    def validate_capabilities(self) -> None:
        pass

    def create_session(self, session_id: str) -> None:
        self.session_id = session_id

    def run(self, session_id: str, prompt: str, approve):
        tools = [["terminal"], ["web_search"], ["pixiu_memory_remember"]][self.index]
        if not self.remember_last:
            tools = [["pixiu_memory_remember"], ["terminal"], ["web_search"]][self.index]
        result = {
            "run_id_digest": str(self.index) * 64,
            "tools": tools,
            "approvals": 1 if self.index == 0 else 0,
            "output": "",
        }
        self.index += 1
        return result

    def messages(self, session_id: str):
        return messages(6)

    def runtime_identity(self) -> str:
        return "c" * 64


class FakeAfterClient:
    def __init__(self, state: dict, *, restarted: bool = True, recalled: bool = True) -> None:
        self.state = state
        self.identity = "d" * 64 if restarted else state["runtime_identity"]
        self.recalled = recalled
        self.run_count = 0

    def validate_capabilities(self) -> None:
        pass

    def runtime_identity(self) -> str:
        return self.identity

    def messages(self, session_id: str):
        if session_id == self.state["session_id"]:
            return messages(8 if self.run_count else 6)
        return messages(2)

    def create_session(self, session_id: str) -> None:
        pass

    def run(self, session_id: str, prompt: str, approve):
        self.run_count += 1
        if self.run_count == 1:
            return {"run_id_digest": "e" * 64, "tools": [], "approvals": 0, "output": "restored"}
        output = self.state["memory_marker"] if self.recalled else "not found"
        return {
            "run_id_digest": "f" * 64,
            "tools": ["pixiu_memory_search"],
            "approvals": 0,
            "output": output,
        }


class _SseResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        event = {"event": "run.completed", "output": "done"}
        return iter([(f"data: {json.dumps(event)}\n").encode("utf-8")])


class RecordingAgentClient(MODULE.AgentClient):
    def __init__(self) -> None:
        super().__init__("http://127.0.0.1:8642")
        self.started_payload = None

    def messages(self, session_id: str):
        return [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "answer"},
            {"role": "tool", "content": "must not be flattened"},
        ]

    def json(self, method: str, path: str, payload=None):
        if method == "POST" and path == "/v1/runs":
            self.started_payload = payload
            return {"run_id": "run_" + "a" * 32}
        if method == "GET" and path.startswith("/v1/runs/"):
            return {"status": "completed"}
        raise AssertionError((method, path))

    def _request(self, method: str, path: str, payload=None):
        return _SseResponse()


class AgentLifecycleEvidenceTest(unittest.TestCase):
    def test_run_forwards_persisted_conversation_history(self) -> None:
        client = RecordingAgentClient()
        result = client.run("session-one", "second", lambda _: True)
        self.assertEqual(result["output"], "done")
        self.assertEqual(
            client.started_payload,
            {
                "input": "second",
                "session_id": "session-one",
                "conversation_history": [
                    {"role": "user", "content": "first"},
                    {"role": "assistant", "content": "answer"},
                ],
            },
        )

    def test_shipped_scenario_is_valid_and_does_not_name_tools(self) -> None:
        shipped = MODULE._read_json(ROOT / "agent-lifecycle-scenario.json")
        self.assertEqual(MODULE.validate_scenario(shipped), shipped)
        self.assertIn("单次确认", shipped["turns"][1])
        self.assertIn("跨会话长期记忆", shipped["turns"][2])

    def test_scenario_rejects_forced_tool_name(self) -> None:
        value = scenario()
        value["turns"][0] += " 请调用 pixiu_memory_remember。"
        with self.assertRaisesRegex(MODULE.EvidenceError, "implementation tool"):
            MODULE.validate_scenario(value)

    def test_native_binding_requires_strict_passing_evidence(self) -> None:
        self.assertEqual(
            MODULE.validate_native_evidence(native()),
            {"git_commit": "a" * 40, "candidate_package_sha256": "b" * 64},
        )
        value = native()
        value["capabilities"]["contest_ready"] = False
        with self.assertRaisesRegex(MODULE.EvidenceError, "not a passing"):
            MODULE.validate_native_evidence(value)

    def test_before_and_after_produce_payload_free_final_evidence(self) -> None:
        controlled = MODULE.validate_scenario(scenario())
        release = MODULE.validate_native_evidence(native())
        release["native_evidence_sha256"] = "c" * 64
        state = MODULE.capture_before(
            FakeBeforeClient(), release, controlled, lambda _: True, host_identity="1" * 64
        )
        evidence = MODULE.capture_after(
            FakeAfterClient(state), state, controlled, lambda _: True, host_identity="2" * 64
        )
        MODULE.validate_final(evidence)
        self.assertEqual(evidence["checks"], {name: "passed" for name in sorted(MODULE.REQUIRED_CHECKS)})
        self.assertFalse(evidence["observations"]["payloads_retained"])
        self.assertNotIn(state["memory_marker"], str(evidence))
        self.assertTrue(evidence["runtime"]["process_changed"])

    def test_before_rejects_memory_write_before_tool_results(self) -> None:
        with self.assertRaisesRegex(MODULE.EvidenceError, "first phase"):
            release = MODULE.validate_native_evidence(native())
            release["native_evidence_sha256"] = "c" * 64
            MODULE.capture_before(
                FakeBeforeClient(remember_last=False),
                release,
                MODULE.validate_scenario(scenario()),
                lambda _: True,
                host_identity="1" * 64,
            )

    def test_after_requires_a_different_runtime_process(self) -> None:
        controlled = MODULE.validate_scenario(scenario())
        release = MODULE.validate_native_evidence(native())
        release["native_evidence_sha256"] = "c" * 64
        state = MODULE.capture_before(
            FakeBeforeClient(), release, controlled, lambda _: True,
            host_identity="1" * 64,
        )
        with self.assertRaisesRegex(MODULE.EvidenceError, "not restarted"):
            MODULE.capture_after(
                FakeAfterClient(state, restarted=False), state, controlled, lambda _: True,
                host_identity="2" * 64,
            )

    def test_after_requires_marker_returned_by_memory_search(self) -> None:
        controlled = MODULE.validate_scenario(scenario())
        release = MODULE.validate_native_evidence(native())
        release["native_evidence_sha256"] = "c" * 64
        state = MODULE.capture_before(
            FakeBeforeClient(), release, controlled, lambda _: True,
            host_identity="1" * 64,
        )
        with self.assertRaisesRegex(MODULE.EvidenceError, "recall was not proven"):
            MODULE.capture_after(
                FakeAfterClient(state, recalled=False), state, controlled, lambda _: True,
                host_identity="2" * 64,
            )

    def test_rejects_non_loopback_gateway(self) -> None:
        with self.assertRaisesRegex(MODULE.EvidenceError, "loopback"):
            MODULE.validate_loopback_url("https://agent.example.test:8642")


if __name__ == "__main__":
    unittest.main()
