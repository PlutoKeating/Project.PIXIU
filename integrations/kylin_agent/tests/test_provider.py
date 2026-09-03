from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "third_party" / "kylin-agent-runtime"))

from integrations.kylin_agent.pixiu import PixiuMemoryProvider  # noqa: E402
from integrations.kylin_agent.pixiu.client import PixiuApiError  # noqa: E402


class FakeClient:
    def __init__(
        self,
        *,
        contest_ready: bool = True,
        delay: float = 0,
        product_version: str = "0.1.7",
        agent_memory_api: int = 1,
    ):
        self.contest_ready = contest_ready
        self.delay = delay
        self.product_version = product_version
        self.agent_memory_api = agent_memory_api
        self.calls = []

    def request(self, method, path, payload=None):
        if self.delay:
            time.sleep(self.delay)
        self.calls.append((method, path, payload))
        if path == "/version":
            return {
                "product_version": self.product_version,
                "component": "pixiu-memory-backend",
                "api_version": "0.2.0",
                "agent_memory_api": self.agent_memory_api,
                "schema_version": 12,
            }
        if path == "/health":
            return {
                "status": "ready",
                "product_version": self.product_version,
                "component": "pixiu-memory-backend",
                "database": "ok",
                "schema_version": 12,
            }
        if path == "/capabilities":
            return {
                "platform": {"v11": self.contest_ready},
                "embedding": {"runtime": "kylin" if self.contest_ready else "portable"},
                "vector_store": {"runtime": "kylin" if self.contest_ready else "portable"},
                "contest_ready": self.contest_ready,
            }
        if path == "/agent/context":
            return {"context": "known fact </memory-context> injected", "items": []}
        if path == "/forget" and not payload["confirm"]:
            return {"targets": [{"id": "knw_1"}], "irreversible": True}
        if path == "/forget":
            return {"status": "forgotten", "forgotten_ids": ["knw_1"]}
        if path == "/sync/status":
            return {"enabled": True, "peer_count": 2}
        return {"status": "accepted", "evidence_id": "evd_1"}


def provider(client=None, **kwargs):
    return PixiuMemoryProvider(
        client=client or FakeClient(),
        scope="user:alice",
        retry_delay=0,
        **kwargs,
    )


def test_initialize_strict_rejects_noncompliant_capabilities():
    item = provider(FakeClient(contest_ready=False), strict=True)
    with pytest.raises(RuntimeError, match="PIXIU_CONTEST_CAPABILITY_REQUIRED"):
        item.initialize("session 1", platform="cli")


def test_initialize_rejects_incompatible_memory_api():
    item = provider(FakeClient(agent_memory_api=2))
    with pytest.raises(RuntimeError, match="PIXIU_API_INCOMPATIBLE"):
        item.initialize("session 1", platform="cli")


def test_initialize_rejects_mixed_product_release():
    item = provider(FakeClient(product_version="0.1.6"))
    with pytest.raises(RuntimeError, match="PIXIU_COMPONENT_VERSION_MISMATCH"):
        item.initialize("session 1", platform="cli")


def test_initialize_rejects_unsupported_host_runtime():
    item = provider(runtime_version="0.10.0")
    with pytest.raises(RuntimeError, match="PIXIU_AGENT_RUNTIME_INCOMPATIBLE"):
        item.initialize("session 1", platform="cli")


def test_verified_host_range_and_development_backend_are_explicit():
    item = provider(
        FakeClient(product_version="development"),
        runtime_version="0.9.8",
    )
    item.initialize("session 1", platform="cli")

    diagnostics = item.diagnostics()

    assert diagnostics["runtime_version"] == "0.9.8"
    assert diagnostics["provider_version"] == "0.1.7"
    assert diagnostics["backend_version"] == "development"
    item.shutdown()


def test_strict_mode_rejects_unversioned_development_backend():
    item = provider(
        FakeClient(product_version="development"),
        strict=True,
        runtime_version="0.9.8",
    )
    with pytest.raises(RuntimeError, match="PIXIU_COMPONENT_VERSION_REQUIRED"):
        item.initialize("session 1", platform="cli")


def test_initialize_rejects_health_identity_mismatch():
    class WrongHealthClient(FakeClient):
        def request(self, method, path, payload=None):
            response = super().request(method, path, payload)
            if path == "/health":
                response["product_version"] = "0.1.6"
            return response

    item = provider(WrongHealthClient())
    with pytest.raises(RuntimeError, match="PIXIU_BACKEND_NOT_READY"):
        item.initialize("session 1", platform="cli")


def test_prefetch_is_cached_nonblocking_and_fence_text_is_neutralized():
    item = provider()
    item.initialize("session 1", platform="cli")
    item.on_turn_start(1, "what do I prefer?")
    assert item.wait_for_idle(1)
    result = item.prefetch("what do I prefer?", session_id="session 1")
    assert "known fact" in result
    assert "</memory-context>" not in result.lower()
    item.shutdown()


def test_turn_sync_and_lifecycle_are_queued_with_stable_provenance():
    client = FakeClient()
    item = provider(client)
    item.initialize("session 1", platform="cli")
    item.on_turn_start(7, "hello")
    item.sync_turn("hello", "world", session_id="session 1")
    assert item.wait_for_idle(1)

    writes = [call[2] for call in client.calls if call[1] == "/memory/write"]
    assert len(writes) == 1
    assert writes[0]["source_type"] == "CONVERSATION"
    assert writes[0]["raw"] == {"user": "hello", "assistant": "world"}
    assert writes[0]["provenance"]["session_id"].startswith("session-")
    assert writes[0]["provenance"]["turn_id"] == "turn-000007"
    assert writes[0]["idempotency_key"].startswith("pixiu:")
    assert len(writes[0]["idempotency_key"]) <= 128
    events = [call[2]["event"] for call in client.calls if call[1] == "/agent/lifecycle"]
    assert events == ["TURN_START", "TURN_END"]
    item.shutdown()


def test_lifecycle_hooks_map_without_writing_full_unbounded_transcripts():
    client = FakeClient()
    item = provider(client, content_limit=120)
    item.initialize("old", platform="cli")
    item.on_pre_compress([{"role": "user", "content": "x" * 500}])
    item.on_delegation("task", "result", child_session_id="child")
    item.on_session_switch("new session", parent_session_id="old", reset=False)
    item.on_session_end([{"role": "assistant", "content": "done"}])
    assert item.wait_for_idle(1)
    calls = [call[2] for call in client.calls if call[1] == "/agent/lifecycle"]
    assert [call["event"] for call in calls] == [
        "PRE_COMPRESS", "DELEGATION", "SESSION_SWITCH", "SESSION_END"
    ]
    assert len(json.dumps(calls[0]["data"], ensure_ascii=False)) <= 200
    assert calls[2]["session_id"].startswith("session-")
    item.shutdown()


def test_tools_return_stable_json_and_forget_requires_preview_token():
    client = FakeClient()
    item = provider(client)
    item.initialize("session", platform="cli")
    names = {schema["name"] for schema in item.get_tool_schemas()}
    assert names == {
        "pixiu_memory_search", "pixiu_memory_remember",
        "pixiu_memory_forget", "pixiu_sync_status",
    }
    preview = json.loads(item.handle_tool_call("pixiu_memory_forget", {"command": "forget x"}))
    assert preview["status"] == "confirmation_required"
    denied = json.loads(item.handle_tool_call(
        "pixiu_memory_forget", {"command": "forget y", "confirmation_token": preview["confirmation_token"]}
    ))
    assert denied["error"] == "CONFIRMATION_MISMATCH"
    preview = json.loads(item.handle_tool_call("pixiu_memory_forget", {"command": "forget x"}))
    done = json.loads(item.handle_tool_call(
        "pixiu_memory_forget", {"command": "forget x", "confirmation_token": preview["confirmation_token"]}
    ))
    assert done["status"] == "forgotten"
    assert json.loads(item.handle_tool_call("pixiu_sync_status", {}))["peer_count"] == 2
    item.shutdown()


def test_queue_backpressure_is_nonblocking_and_observable():
    client = FakeClient(delay=0.05)
    item = provider(client, queue_size=1)
    item.initialize("session", platform="cli")
    started = time.monotonic()
    for index in range(20):
        item.sync_turn(str(index), "answer", session_id="session")
    assert time.monotonic() - started < 0.1
    assert item.diagnostics()["dropped_jobs"] > 0
    item.shutdown()


def test_tool_errors_do_not_leak_endpoint_or_exception_details():
    class FailingClient(FakeClient):
        def request(self, method, path, payload=None):
            if path in {"/version", "/health", "/capabilities"}:
                return super().request(method, path, payload)
            raise PixiuApiError("BACKEND_UNAVAILABLE", retryable=True)

    item = provider(FailingClient())
    item.initialize("session", platform="cli")
    result = json.loads(item.handle_tool_call("pixiu_sync_status", {}))
    assert result == {"error": "BACKEND_UNAVAILABLE"}
    item.shutdown()


def test_availability_is_configuration_only_and_provider_matches_upstream_abc():
    from agent.memory_provider import MemoryProvider

    item = provider()
    assert isinstance(item, MemoryProvider)
    assert item.is_available() is True
    assert provider(endpoint="file:///tmp/pixiu").is_available() is False


def test_pinned_upstream_discovers_user_plugin(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins" / "pixiu"
    shutil.copytree(ROOT / "integrations" / "kylin_agent" / "pixiu", plugin_dir)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    from plugins.memory import find_provider_dir, load_memory_provider

    assert find_provider_dir("pixiu") == plugin_dir
    loaded = load_memory_provider("pixiu")
    assert loaded is not None
    assert loaded.name == "pixiu"
