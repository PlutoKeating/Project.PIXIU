"""Tests for api/http_app.py — REST 端点端到端（临时 SQLite + 测试桩 embedding）。"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path

import aiosqlite
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import backend.foundation.api.di as di_module
from backend.foundation.api import app
from backend.engine.knowledge import KnowledgeService
from backend.engine.tests.fakes import StubTextEmbedder
from backend.foundation.api.di import (
    get_flow_service,
    get_knowledge_service,
    get_security_service,
)
from backend.foundation.api.capabilities import platform_capability
from backend.foundation.flow import FlowContextNotFound, InvalidFlowTransition
from backend.foundation.storage.repository import (
    SqliteEntityRepo,
    SqliteKnowledgeRepo,
)
from backend.foundation.storage.schema import SCHEMA_VERSION, init_db_on_connection
from backend.foundation.sync import PairingMethod, SqliteSyncStore, SyncService


class _FakeSettings:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.embedding = "portable"
        self.vector_store = "portable"
        self.ocr = "portable"
        self.sync_device_name = "书房工作站"
        self.sync_domain = "shared:home"
        self.sync_key_passphrase = "phase3-api-test-passphrase"
        self.sync_network_enabled = False
        self.monitor_enabled = False  # API 测试不启动 monitor runtime


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(di_module, "settings", _FakeSettings(str(tmp_path / "pixiu.db")))
    di_module._db = None
    di_module._sync_runtime = None  # 防测试间 sync runtime 泄漏

    # 无麒麟 SDK 的开发机上，用测试专用桩注入 KnowledgeService
    async def _override_knowledge():
        db = await di_module.get_db()
        return KnowledgeService(
            knw_repo=SqliteKnowledgeRepo(db),
            entity_repo=SqliteEntityRepo(db),
            embedder=StubTextEmbedder(dim=32),
        )

    app.dependency_overrides[get_knowledge_service] = _override_knowledge
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    di_module._db = None
    di_module._sync_runtime = None


OCR_RAW = {
    "title": "2026年4月家庭支出清单",
    "body": {
        "items": [
            {"category": "水电燃气", "vendor": "国家电网", "amount": 210.0}
        ]
    },
}


@pytest.mark.parametrize("scope", ["user:project\n", "shared:*", " user:project", "", 7])
def test_invalid_scopes_are_rejected_at_http_boundary(client, scope):
    requests = [
        ("/memory/write", {"source_type": "OCR", "raw": OCR_RAW, "scope": scope}),
        ("/memory/update", {"knowledge_id": "knw_01KYSVDG0739TWR7179BEYETVT",
                            "expected_version": 1, "scope": scope, "title": "scope test",
                            "idempotency_key": "invalid-scope-update"}),
        ("/forget", {"command": "forget scope test", "scope": scope}),
        ("/memory/query", {"text": "scope test", "context_hint": {"scope": scope}}),
        ("/agent/context", {"query": "scope test", "scope": scope,
                            "session_id": "session-test", "turn_id": "turn-test"}),
        ("/agent/lifecycle", {"event": "TURN_START", "scope": scope,
                              "session_id": "session-test", "run_id": "run-test",
                              "turn_id": "turn-test", "data": {"text": "scope test"},
                              "occurred_at": 1700000000,
                              "idempotency_key": "invalid-scope-lifecycle"}),
        ("/memory/flow/promote", {"source": "SHORT_TERM", "context_ids": ["ctx-test"],
                                 "scope": scope}),
    ]
    with sqlite3.connect(di_module.settings.db_path) as db:
        before = list(db.iterdump())
    for path, payload in requests:
        response = client.post(path, json=payload)
        assert response.status_code == 400, (path, response.text)
        assert response.json()["error"] == "INVALID_REQUEST"
    for path in ["/preferences", "/memory/items/knw_01KYSVDG0739TWR7179BEYETVT"]:
        response = client.get(path, params={"scope": scope})
        assert response.status_code == 400, (path, response.text)
        assert response.json()["error"] == "INVALID_REQUEST"
    with sqlite3.connect(di_module.settings.db_path) as db:
        assert list(db.iterdump()) == before


@pytest.mark.parametrize("scope", ["user:project.2025", "shared:project.2025"])
def test_dotted_scope_round_trip_keeps_exact_domain(client, scope):
    if scope.startswith("shared:"):
        di_module.settings.sync_domain = scope
    knowledge_id = _write_knowledge_id(client, title="dotted scope target", scope=scope)
    path = f"/memory/items/{knowledge_id}"
    response = client.get(path, params={"scope": scope})
    assert response.status_code == 200
    assert response.json()["scope"] == scope
    wrong_scope = scope.replace("project.2025", "project_2025")
    assert client.get(path, params={"scope": wrong_scope}).status_code == 404


def test_wrong_shared_domain_write_is_rejected_before_any_database_change(client):
    with sqlite3.connect(di_module.settings.db_path) as db:
        before = list(db.iterdump())
    # Return the real HTTP error instead of re-raising the server exception.
    client._transport.raise_server_exceptions = False
    response = client.post("/memory/write", json={
        "source_type": "OCR", "raw": OCR_RAW, "scope": "shared:other.domain",
        "idempotency_key": "wrong-shared-domain",
    })
    with sqlite3.connect(di_module.settings.db_path) as db:
        after = list(db.iterdump())
    assert after == before, "rejected shared write left persisted side effects"
    assert response.status_code == 403
    assert response.json()["error"] == "SHARED_SCOPE_MISMATCH"


def test_wrong_shared_domain_update_preserves_record_and_receipts(client):
    knowledge_id = _write_knowledge_id(client, title="shared update domain guard",
                                      scope="shared:home")
    # Historical data can remain after a configuration change. Do not rewrite it.
    di_module.settings.sync_domain = "shared:new-domain"
    with sqlite3.connect(di_module.settings.db_path) as db:
        before = list(db.iterdump())
    response = client.post("/memory/update", json={
        "knowledge_id": knowledge_id, "expected_version": 1, "scope": "shared:home",
        "title": "must not replace", "idempotency_key": "wrong-domain-update",
    })
    assert response.status_code == 403
    assert response.json()["error"] == "SHARED_SCOPE_MISMATCH"
    with sqlite3.connect(di_module.settings.db_path) as db:
        assert list(db.iterdump()) == before


@pytest.mark.parametrize("scope", [None, "shared:home"])
def test_wrong_shared_domain_forget_preserves_records_and_consumes_preview(client, scope):
    knowledge_id = _write_knowledge_id(client, title="shared forget domain guard",
                                      scope="shared:home")
    private_id = _write_knowledge_id(client, title="shared forget domain guard",
                                    scope="user:private")
    request = {"command": "忘记shared forget domain guard", "scope": scope}
    preview_response = client.post("/forget", json=request)
    assert preview_response.status_code == 200
    preview = preview_response.json()
    expected_ids = {knowledge_id, private_id} if scope is None else {knowledge_id}
    assert {item["id"] for item in preview["targets"]} == expected_ids
    di_module.settings.sync_domain = "shared:new-domain"
    with sqlite3.connect(di_module.settings.db_path) as db:
        before = list(db.iterdump())
    client._transport.raise_server_exceptions = False
    payload = {**request, "confirm": True,
               "confirmation_token": preview["confirmation_token"]}
    response = client.post("/forget", json=payload)
    with sqlite3.connect(di_module.settings.db_path) as db:
        assert list(db.iterdump()) == before, "failed confirmation changed stored memory"
    assert response.status_code == 403
    assert response.json()["error"] == "SHARED_SCOPE_MISMATCH"
    assert client.post("/forget", json=payload).status_code == 409


def test_capabilities_exposes_actual_noncompliant_portable_runtime(client):
    response = client.get("/capabilities")

    assert response.status_code == 200
    data = response.json()
    assert data["embedding"]["configured"] == "portable"
    assert data["embedding"]["runtime"] == "portable"
    assert data["embedding"]["compliant"] is False
    assert data["vector_store"]["configured"] == "portable"
    assert data["vector_store"]["runtime"] == "portable"
    assert data["vector_store"]["compliant"] is False
    assert data["contest_ready"] is False


def test_version_distinguishes_product_api_and_schema_versions(client, monkeypatch):
    monkeypatch.setenv("PIXIU_PRODUCT_VERSION", "0.1.7")

    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {
        "product_version": "0.1.7",
        "component": "pixiu-memory-backend",
        "api_version": "0.5.0",
        "agent_memory_api": 1,
        "schema_version": SCHEMA_VERSION,
    }


def test_health_proves_database_migration_and_component_identity(client, monkeypatch):
    monkeypatch.setenv("PIXIU_PRODUCT_VERSION", "0.1.7")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "product_version": "0.1.7",
        "component": "pixiu-memory-backend",
        "database": "ok",
        "schema_version": SCHEMA_VERSION,
    }


def test_health_fails_closed_when_database_schema_is_stale(client):
    with sqlite3.connect(di_module.settings.db_path) as conn:
        conn.execute("DELETE FROM _schema_version WHERE version = ?", (SCHEMA_VERSION,))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["error"] == "SCHEMA_NOT_READY"


def test_platform_capability_only_reports_acceptance_identity():
    data = platform_capability(
        {
            "ID": "openkylin",
            "NAME": "openKylin",
            "VERSION_ID": "11.2",
            "HOSTNAME": "must-not-leak",
        }
    )

    assert data == {"family": "kylin", "version_major": "11", "v11": True}


def test_platform_capability_accepts_kylin_v_prefixed_version():
    data = platform_capability(
        {"ID": "kylin", "NAME": "Kylin", "VERSION_ID": "V11"}
    )

    assert data == {"family": "kylin", "version_major": "11", "v11": True}


def test_memory_write_returns_accepted(client):
    resp = client.post(
        "/memory/write",
        json={"source_type": "OCR", "raw": OCR_RAW, "scope": "shared:home"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["evidence_id"].startswith("evd_")
    assert data["quality_score"] > 0
    assert data["latency_ms"] >= 0


def test_events_websocket_is_registered(client):
    with client.websocket_connect("/events") as websocket:
        assert websocket.receive_json() == {"event": "connected", "data": {}}


def test_evidence_detail_returns_raw(client):
    write = client.post(
        "/memory/write",
        json={"source_type": "OCR", "raw": OCR_RAW, "scope": "shared:home"},
    ).json()
    resp = client.get(f"/evidence/{write['evidence_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == write["evidence_id"]
    assert data["source_type"] == "OCR"
    assert data["raw"]["title"] == OCR_RAW["title"]
    assert data["scope"] == "shared:home"


def test_memory_write_accepts_conversation_with_agent_provenance(client):
    response = client.post(
        "/memory/write",
        json={
            "source_type": "CONVERSATION",
            "raw": {"user": "我喜欢简洁回答", "assistant": "我会记住"},
            "scope": "user:alice",
            "idempotency_key": "turn-session-1-1",
            "provenance": {
                "session_id": "session-1",
                "run_id": "run-1",
                "turn_id": "turn-1",
                "occurred_at": 1700000000,
            },
        },
    )

    assert response.status_code == 200
    evidence_id = response.json()["evidence_id"]
    evidence = client.get(f"/evidence/{evidence_id}").json()
    assert evidence["source_type"] == "CONVERSATION"
    assert evidence["provenance"]["session_id"] == "session-1"


def test_memory_write_rejects_conversation_without_turn_provenance(client):
    response = client.post(
        "/memory/write",
        json={
            "source_type": "CONVERSATION",
            "raw": {"user": "hello", "assistant": "hi"},
            "scope": "user:alice",
            "idempotency_key": "turn-session-1-2",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_REQUEST"


def test_agent_tool_result_requires_complete_audit_provenance(client):
    response = client.post(
        "/memory/write",
        json={
            "source_type": "TOOL_RESULT",
            "raw": {"tool_name": "shell", "body": {"result": "done"}},
            "scope": "user:alice",
            "idempotency_key": "tool-call-incomplete-1",
            "provenance": {
                "session_id": "session-1",
                "run_id": "run-1",
                "turn_id": "turn-1",
                "tool_call_id": "call-1",
                "occurred_at": 1700000000
            },
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_REQUEST"


def test_agent_tool_result_persists_complete_audit_provenance(client):
    response = client.post(
        "/memory/write",
        json={
            "source_type": "TOOL_RESULT",
            "raw": {"tool_name": "shell", "body": {"result": "done"}},
            "scope": "user:alice",
            "idempotency_key": "tool-call-1",
            "provenance": {
                "session_id": "session-1",
                "run_id": "run-1",
                "turn_id": "turn-1",
                "tool_call_id": "call-1",
                "tool_name": "shell",
                "approved": True,
                "occurred_at": 1700000000
            },
        },
    )

    assert response.status_code == 200
    evidence = client.get(
        f"/evidence/{response.json()['evidence_id']}"
    ).json()
    assert evidence["provenance"]["tool_call_id"] == "call-1"
    assert evidence["provenance"]["approved"] is True


def test_agent_memory_write_requires_idempotency_key(client):
    response = client.post(
        "/memory/write",
        json={
            "source_type": "CONVERSATION",
            "raw": {"user": "hello", "assistant": "hi"},
            "scope": "user:alice",
            "provenance": {
                "session_id": "session-1",
                "run_id": "run-1",
                "turn_id": "turn-2",
                "occurred_at": 1700000001,
            },
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_REQUEST"


def test_agent_memory_write_replay_returns_original_without_duplicates(client):
    payload = {
        "source_type": "CONVERSATION",
        "raw": {"user": "remember this", "assistant": "stored"},
        "scope": "user:alice",
        "idempotency_key": "turn-session-2-1",
        "provenance": {
            "session_id": "session-2",
            "run_id": "run-2",
            "turn_id": "turn-1",
            "occurred_at": 1700000002,
        },
    }

    first = client.post("/memory/write", json=payload)
    replay = client.post("/memory/write", json=payload)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == first.json()
    with sqlite3.connect(di_module.settings.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM knowledge_items").fetchone()[0] == 1


def test_agent_memory_write_rejects_key_reuse_with_different_payload(client):
    payload = {
        "source_type": "CONVERSATION",
        "raw": {"user": "first", "assistant": "stored"},
        "scope": "user:alice",
        "idempotency_key": "turn-session-3-1",
        "provenance": {
            "session_id": "session-3",
            "run_id": "run-3",
            "turn_id": "turn-1",
            "occurred_at": 1700000003,
        },
    }
    first = client.post("/memory/write", json=payload)
    payload["raw"]["user"] = "different"

    conflict = client.post("/memory/write", json=payload)

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "IDEMPOTENCY_CONFLICT"


def test_failed_agent_memory_write_requires_explicit_audited_recovery(client):
    payload = {
        "source_type": "CONVERSATION",
        "raw": {"user": "remember recovery", "assistant": "stored"},
        "scope": "user:alice",
        "idempotency_key": "turn-recovery-1",
        "provenance": {
            "session_id": "session-recovery",
            "run_id": "run-recovery",
            "turn_id": "turn-1",
            "occurred_at": 1700000004,
        },
    }

    class _FailingKnowledge:
        async def structure(self, evidence):
            raise HTTPException(status_code=503, detail="INJECTED_FAILURE")

    working_knowledge = app.dependency_overrides[get_knowledge_service]
    app.dependency_overrides[get_knowledge_service] = lambda: _FailingKnowledge()
    try:
        failed = client.post("/memory/write", json=payload)
    finally:
        app.dependency_overrides[get_knowledge_service] = working_knowledge

    assert failed.status_code == 503
    blocked = client.post("/memory/write", json=payload)
    assert blocked.status_code == 409
    assert blocked.json()["error"] == "IDEMPOTENCY_FAILED"

    rejected = client.post(
        "/agent/idempotency/recover",
        json={
            "operation": "MEMORY_WRITE",
            "original_request": payload,
            "confirm_duplicate_risk": False,
            "reason": "verified no completed downstream write",
        },
    )
    assert rejected.status_code == 400
    assert rejected.json()["error"] == "INVALID_REQUEST"

    recovered = client.post(
        "/agent/idempotency/recover",
        json={
            "operation": "MEMORY_WRITE",
            "original_request": payload,
            "confirm_duplicate_risk": True,
            "reason": "verified no completed downstream write",
        },
    )
    assert recovered.status_code == 200
    assert recovered.json() == {
        "operation": "MEMORY_WRITE",
        "idempotency_key": "turn-recovery-1",
        "status": "RETRY_AUTHORIZED",
        "recovery_count": 1,
        "authorized_at": recovered.json()["authorized_at"],
    }

    retry = client.post("/memory/write", json=payload)
    assert retry.status_code == 200
    with sqlite3.connect(di_module.settings.db_path) as conn:
        row = conn.execute(
            """SELECT state, retry_authorized, recovery_count, recovery_reason
               FROM agent_ingest_receipts WHERE idempotency_key = ?""",
            (payload["idempotency_key"],),
        ).fetchone()
    assert row == (
        "COMPLETED",
        0,
        1,
        "verified no completed downstream write",
    )


def test_retry_recovery_rejects_changed_original_request(client):
    payload = {
        "source_type": "CONVERSATION",
        "raw": {"user": "original", "assistant": "stored"},
        "scope": "user:alice",
        "idempotency_key": "turn-recovery-conflict",
        "provenance": {
            "session_id": "session-recovery",
            "run_id": "run-recovery",
            "turn_id": "turn-2",
            "occurred_at": 1700000005,
        },
    }

    class _FailingKnowledge:
        async def structure(self, evidence):
            raise HTTPException(status_code=503, detail="INJECTED_FAILURE")

    working_knowledge = app.dependency_overrides[get_knowledge_service]
    app.dependency_overrides[get_knowledge_service] = lambda: _FailingKnowledge()
    try:
        assert client.post("/memory/write", json=payload).status_code == 503
    finally:
        app.dependency_overrides[get_knowledge_service] = working_knowledge
    payload["raw"]["user"] = "changed"

    response = client.post(
        "/agent/idempotency/recover",
        json={
            "operation": "MEMORY_WRITE",
            "original_request": payload,
            "confirm_duplicate_risk": True,
            "reason": "attempt changed payload",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"] == "IDEMPOTENCY_CONFLICT"


def test_agent_context_returns_budgeted_cited_memory(client):
    write = client.post(
        "/memory/write",
        json={
            "source_type": "CONVERSATION",
            "raw": {"user": "我偏好简洁回答", "assistant": "已记住"},
            "scope": "user:alice",
            "idempotency_key": "session-context:turn-1",
            "provenance": {
                "session_id": "session-context",
                "run_id": "run-context",
                "turn_id": "turn-1",
                "occurred_at": 1700000010,
            },
        },
    )
    assert write.status_code == 200
    with sqlite3.connect(di_module.settings.db_path) as conn:
        knowledge_id = conn.execute(
            "SELECT knowledge_id FROM knowledge_evidence WHERE evidence_id = ?",
            (write.json()["evidence_id"],),
        ).fetchone()[0]
        conn.execute(
            "UPDATE knowledge_items SET updated_at = 1 WHERE id = ?",
            (knowledge_id,),
        )
        conn.execute(
            """INSERT INTO conflict_records
               (id, target_knowledge, field, old_value, new_value,
                resolution, created_at, source, severity)
               VALUES (?, ?, 'body', '{}', '{}', 'MANUAL', 1, 'write', 'high')""",
            ("cfl_" + "A" * 26, knowledge_id),
        )

    response = client.post(
        "/agent/context",
        json={
            "query": "简洁回答",
            "scope": "user:alice",
            "session_id": "session-context",
            "turn_id": "turn-2",
            "max_chars": 1024,
            "top_k": 5,
            "freshness_seconds": 60,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "session-context"
    assert data["turn_id"] == "turn-2"
    assert "我偏好简洁回答" in data["context"]
    assert data["items"][0]["evidence_ids"] == [write.json()["evidence_id"]]
    assert data["items"][0]["version"] == 1
    assert data["items"][0]["scope"] == "user:alice"
    assert data["items"][0]["freshness"] == "stale"
    assert data["items"][0]["conflict_status"] == "manual"
    assert data["truncated"] is False


def test_agent_context_enforces_scope_and_character_budget(client):
    for scope, suffix in (("user:alice", "alice"), ("user:bob", "bob")):
        result = client.post(
            "/memory/write",
            json={
                "source_type": "CONVERSATION",
                "raw": {
                    "user": f"项目代号是长城-{suffix}" + "甲" * 120,
                    "assistant": "已记住",
                },
                "scope": scope,
                "idempotency_key": f"session-{suffix}:turn-1",
                "provenance": {
                    "session_id": f"session-{suffix}",
                    "run_id": f"run-{suffix}",
                    "turn_id": "turn-1",
                    "occurred_at": 1700000011,
                },
            },
        )
        assert result.status_code == 200

    response = client.post(
        "/agent/context",
        json={
            "query": "项目代号长城",
            "scope": "user:alice",
            "session_id": "session-alice",
            "turn_id": "turn-2",
            "max_chars": 96,
            "top_k": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["context"]) <= 96
    assert "bob" not in data["context"]
    assert all(item["scope"] == "user:alice" for item in data["items"])
    assert data["truncated"] is True


def test_agent_context_requires_stable_turn_identifiers(client):
    response = client.post(
        "/agent/context",
        json={"query": "anything", "scope": "user:alice", "max_chars": 1000},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_REQUEST"


def test_agent_context_excludes_sensitive_evidence(client):
    write = client.post(
        "/memory/write",
        json={
            "source_type": "CONVERSATION",
            "raw": {
                "user": "我的手机号是 13812345678",
                "assistant": "不会主动展示",
            },
            "scope": "user:alice",
            "idempotency_key": "session-sensitive:turn-1",
            "provenance": {
                "session_id": "session-sensitive",
                "run_id": "run-sensitive",
                "turn_id": "turn-1",
                "occurred_at": 1700000012,
            },
        },
    )
    assert write.status_code == 200
    assert write.json()["sensitivity"] == 2
    evidence = client.get(f"/evidence/{write.json()['evidence_id']}").json()
    assert evidence["sensitivity"] == 2

    response = client.post(
        "/agent/context",
        json={
            "query": "手机号 13812345678",
            "scope": "user:alice",
            "session_id": "session-sensitive",
            "turn_id": "turn-2",
        },
    )

    assert response.status_code == 200
    assert response.json()["context"] == ""
    assert response.json()["items"] == []


def test_memory_write_rejects_sensitive_content_in_shared_scope(client):
    response = client.post(
        "/memory/write",
        json={
            "source_type": "OCR",
            "raw": {"text": "联系人手机号 13812345678"},
            "scope": "shared:home",
            "idempotency_key": "shared-sensitive-1",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"] == "SENSITIVE_SHARED_SCOPE"
    with sqlite3.connect(di_module.settings.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM agent_ingest_receipts"
        ).fetchone()[0] == 0


def test_memory_write_fails_closed_when_sensitivity_check_fails(client):
    class _FailingSecurity:
        async def detect_sensitivity(self, raw):
            raise RuntimeError("detector unavailable")

    app.dependency_overrides[get_security_service] = lambda: _FailingSecurity()
    response = client.post(
        "/memory/write",
        json={
            "source_type": "OCR",
            "raw": {"text": "ordinary text"},
            "scope": "user:alice",
            "idempotency_key": "security-failure-1",
        },
    )

    assert response.status_code == 503
    assert response.json()["error"] == "SENSITIVITY_CHECK_FAILED"
    with sqlite3.connect(di_module.settings.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM agent_ingest_receipts"
        ).fetchone()[0] == 0


@pytest.mark.parametrize(
    ("event", "expected_tier"),
    [
        ("TURN_START", "SHORT_TERM"),
        ("TURN_END", "SHORT_TERM"),
        ("PRE_COMPRESS", "MID_TERM"),
        ("SESSION_SWITCH", "MID_TERM"),
        ("SESSION_END", "MID_TERM"),
        ("DELEGATION", "MID_TERM"),
    ],
)
def test_agent_lifecycle_persists_server_selected_tier(client, event, expected_tier):
    payload = {
        "event": event,
        "scope": "user:alice",
        "session_id": "session-lifecycle",
        "run_id": "run-lifecycle",
        "turn_id": "turn-1",
        "occurred_at": 1700000020,
        "idempotency_key": f"lifecycle:{event.lower()}:1",
        "data": {"summary": f"event {event}"},
    }

    response = client.post("/agent/lifecycle", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["event"] == event
    assert data["tier"] == expected_tier
    assert data["context_id"].startswith("ctx_")
    with sqlite3.connect(di_module.settings.db_path) as conn:
        row = conn.execute(
            "SELECT tier, scope, payload FROM memory_contexts WHERE id = ?",
            (data["context_id"],),
        ).fetchone()
    assert row[0] == expected_tier
    assert row[1] == "user:alice"
    assert json.loads(row[2])["session_id"] == "session-lifecycle"


def test_agent_lifecycle_replay_does_not_duplicate_context(client):
    payload = {
        "event": "PRE_COMPRESS",
        "scope": "user:alice",
        "session_id": "session-lifecycle",
        "run_id": "run-lifecycle",
        "turn_id": "turn-2",
        "occurred_at": 1700000021,
        "idempotency_key": "lifecycle:pre-compress:2",
        "data": {"summary": "compact this turn"},
    }

    first = client.post("/agent/lifecycle", json=payload)
    replay = client.post("/agent/lifecycle", json=payload)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == first.json()
    with sqlite3.connect(di_module.settings.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM memory_contexts").fetchone()[0] == 1


def test_failed_lifecycle_request_uses_independent_recovery_namespace(client):
    payload = {
        "event": "PRE_COMPRESS",
        "scope": "user:alice",
        "session_id": "session-lifecycle-recovery",
        "run_id": "run-lifecycle-recovery",
        "turn_id": "turn-1",
        "occurred_at": 1700000022,
        "idempotency_key": "same-external-key",
        "data": {"summary": "recover lifecycle"},
    }

    class _FailingFlow:
        async def remember(self, *args, **kwargs):
            raise HTTPException(status_code=503, detail="INJECTED_FAILURE")

    app.dependency_overrides[get_flow_service] = lambda: _FailingFlow()
    try:
        assert client.post("/agent/lifecycle", json=payload).status_code == 503
    finally:
        app.dependency_overrides.pop(get_flow_service, None)

    recovered = client.post(
        "/agent/idempotency/recover",
        json={
            "operation": "LIFECYCLE",
            "original_request": payload,
            "confirm_duplicate_risk": True,
            "reason": "verified lifecycle context was not completed",
        },
    )
    assert recovered.status_code == 200
    assert recovered.json()["idempotency_key"] == "same-external-key"
    assert client.post("/agent/lifecycle", json=payload).status_code == 200

    with sqlite3.connect(di_module.settings.db_path) as conn:
        rows = conn.execute(
            """SELECT idempotency_key, state, recovery_count
               FROM agent_ingest_receipts ORDER BY idempotency_key"""
        ).fetchall()
    assert rows == [("lifecycle:same-external-key", "COMPLETED", 1)]


def test_agent_lifecycle_turn_event_requires_turn_id(client):
    response = client.post(
        "/agent/lifecycle",
        json={
            "event": "TURN_END",
            "scope": "user:alice",
            "session_id": "session-lifecycle",
            "run_id": "run-lifecycle",
            "occurred_at": 1700000022,
            "idempotency_key": "lifecycle:turn-end:missing",
            "data": {"summary": "done"},
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_REQUEST"


def test_evidence_detail_404(client):
    resp = client.get("/evidence/evd_AAAAAAAAAAAAAAAAAAAAAAAAAA")
    assert resp.status_code == 404
    assert resp.json()["error"] == "NOT_FOUND"


def test_preferences_list_returns_extracted(client):
    write = client.post(
        "/memory/write",
        json={
            "source_type": "MANUAL_CONFIG",
            "raw": {
                "title": "output_style.compact",
                "key": "output_style.compact",
                "enabled": True,
            },
            "scope": "user:alice",
        },
    ).json()
    extracted = client.post(
        "/preference/extract", json={"evidence_ids": [write["evidence_id"]]}
    ).json()["extracted_preferences"]
    assert extracted

    resp = client.get("/preferences", params={"scope": "user:alice"})
    assert resp.status_code == 200
    prefs = resp.json()["preferences"]
    assert any(p["id"] == extracted[0]["id"] for p in prefs)
    assert all(p["scope"] == "user:alice" for p in prefs)


def test_sync_token_returns_usable_token(client):
    resp = client.post("/sync/token", json={"method": "QR", "ttl_seconds": 60})
    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "QR"
    assert data["ttl_seconds"] == 60
    # 生成的令牌可被 /sync/pair 校验格式（自配对会被拒绝但不是 INVALID_REQUEST）
    paired = client.post("/sync/pair", json={"method": "QR", "token": data["token"]})
    assert paired.status_code in (200, 422)


def _install_ocr_override(backend_engine):
    from backend.foundation.api.di import get_ocr_service

    async def _override():
        return backend_engine

    app.dependency_overrides[get_ocr_service] = _override


def test_memory_ocr_rejects_ambiguous_payload(client):
    resp = client.post("/memory/ocr", json={})
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_REQUEST"

    resp = client.post(
        "/memory/ocr",
        json={"image_base64": "aGVsbG8=", "image_path": "/tmp/x.png"},
    )
    assert resp.status_code == 400

    resp = client.post("/memory/ocr", json={"image_base64": "!!!not-base64!!!"})
    assert resp.status_code == 400


def test_memory_ocr_reports_unavailable_without_sdk(client):
    from backend.engine.kylin.errors import KylinSDKUnavailableError
    from backend.foundation.api.di import get_ocr_service

    class _Stub:
        def recognize(self, image_path, nums=4):
            raise KylinSDKUnavailableError("no sdk")

    _install_ocr_override(_Stub())
    try:
        resp = client.post("/memory/ocr", json={"image_path": "/tmp/none.png"})
        assert resp.status_code == 503
        assert resp.json()["error"] == "OCR_UNAVAILABLE"
    finally:
        app.dependency_overrides.pop(get_ocr_service, None)


def test_memory_ocr_returns_lines_with_sdk_stub(client):
    from backend.foundation.api.di import get_ocr_service

    class _Stub:
        def recognize(self, image_path, nums=4):
            assert image_path.endswith(".img")
            return ["2026年4月家庭支出清单", "电费 210 元"]

    _install_ocr_override(_Stub())
    try:
        import base64 as b64

        resp = client.post(
            "/memory/ocr", json={"image_base64": b64.b64encode(b"fake").decode()}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["text_lines"] == ["2026年4月家庭支出清单", "电费 210 元"]
        assert data["text"].startswith("2026年")
        assert data["latency_ms"] >= 0
    finally:
        app.dependency_overrides.pop(get_ocr_service, None)


def test_preference_extract_and_history(client):
    write = client.post(
        "/memory/write",
        json={
            "source_type": "MANUAL_CONFIG",
            "raw": {
                "title": "output_style.compact",
                "key": "output_style.compact",
                "enabled": True,
                "detail_level": "concise",
            },
            "scope": "user:alice",
        },
    ).json()
    evidence_id = write["evidence_id"]

    resp = client.post("/preference/extract", json={"evidence_ids": [evidence_id]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["extracted_preferences"]
    pref = data["extracted_preferences"][0]
    assert pref["category"] == "OUTPUT_STYLE"

    history = client.get(f"/preference/{pref['id']}/history")
    assert history.status_code == 200
    assert history.json()["current_version"] >= 1


def test_preference_history_404(client):
    resp = client.get("/preference/pref_AAAAAAAAAAAAAAAAAAAAAAAAAA/history")
    assert resp.status_code == 404


def test_forget_requires_scoped_single_use_preview(client):
    command = "忘记那张4月支出清单"
    assert client.post("/forget", json={"command": command, "confirm": True}).status_code == 409
    client.post("/memory/write", json={"source_type": "OCR", "raw": OCR_RAW, "scope": "user:alice"})
    preview = client.post("/forget", json={"command": command, "scope": "user:alice"}).json()
    token = preview["confirmation_token"]
    assert preview["targets"][0]["scope"] == "user:alice"
    assert client.post("/forget", json={"command": command, "scope": "shared:home", "confirm": True,
        "confirmation_token": token}).status_code == 409
    preview = client.post("/forget", json={"command": command, "scope": "user:alice"}).json()
    payload = {"command": command, "scope": "user:alice", "confirm": True,
        "confirmation_token": preview["confirmation_token"]}
    assert client.post("/forget", json=payload).status_code == 200
    assert client.post("/forget", json=payload).status_code == 409


def test_forget_pending_then_confirm(client):
    client.post(
        "/memory/write",
        json={
            "source_type": "OCR",
            "raw": OCR_RAW,
            "scope": "user:alice",
        },
    )

    pending = client.post(
        "/forget", json={"command": "忘记那张4月支出清单", "confirm": False}
    )
    assert pending.status_code == 200
    pdata = pending.json()
    assert pdata["targets"]
    assert pdata["irreversible"] is True

    done = client.post(
        "/forget", json={"command": "忘记那张4月支出清单", "confirm": True,
                          "confirmation_token": pdata["confirmation_token"]}
    )
    assert done.status_code == 200
    ddata = done.json()
    assert ddata["status"] == "forgotten"
    assert ddata["forgotten_ids"]


def test_conflicts_lists_records(client):
    changed = dict(OCR_RAW)
    changed["body"] = {
        "items": [
            {"category": "水电燃气", "vendor": "国家电网", "amount": 186.0}
        ]
    }
    client.post("/memory/write", json={"source_type": "OCR", "raw": OCR_RAW, "scope": "shared:home"})
    client.post("/memory/write", json={"source_type": "OCR", "raw": changed, "scope": "shared:home"})

    resp = client.get("/conflicts")
    assert resp.status_code == 200
    conflicts = resp.json()["conflicts"]
    assert conflicts
    assert "amount" in conflicts[0]["field"]


def test_conflicts_serialize_severity(client):
    """B3-3：GET /conflicts 每项携带 severity（NEW_WINS → medium）。"""
    changed = dict(OCR_RAW)
    changed["body"] = {
        "items": [
            {"category": "水电燃气", "vendor": "国家电网", "amount": 186.0}
        ]
    }
    client.post("/memory/write", json={"source_type": "OCR", "raw": OCR_RAW, "scope": "shared:home"})
    client.post("/memory/write", json={"source_type": "OCR", "raw": changed, "scope": "shared:home"})

    resp = client.get("/conflicts")
    assert resp.status_code == 200
    conflicts = resp.json()["conflicts"]
    assert conflicts
    for item in conflicts:
        assert "severity" in item
    assert conflicts[0]["severity"] == "medium"


def test_conflict_detected_ws_frame_includes_severity(client):
    """B3-3：conflict_detected WS 帧 data 携带 severity（NEW_WINS → medium）。"""
    changed = dict(OCR_RAW)
    changed["body"] = {
        "items": [
            {"category": "水电燃气", "vendor": "国家电网", "amount": 186.0}
        ]
    }
    with client.websocket_connect("/events") as ws:
        assert ws.receive_json() == {"event": "connected", "data": {}}

        client.post("/memory/write", json={"source_type": "OCR", "raw": OCR_RAW, "scope": "shared:home"})
        assert ws.receive_json()["event"] == "memory_ready"  # 首次写入无冲突

        client.post("/memory/write", json={"source_type": "OCR", "raw": changed, "scope": "shared:home"})
        assert ws.receive_json()["event"] == "memory_ready"
        frame = ws.receive_json()
        assert frame["event"] == "conflict_detected"
        assert frame["data"]["severity"] == "medium"


def test_flow_promote_contract(client):
    # 先触发数据库迁移，再从会话生产者边界写入一个短期上下文。
    assert client.get("/conflicts").status_code == 200
    context_id = "ctx_AAAAAAAAAAAAAAAAAAAAAAAAAA"
    now = int(time.time())
    conn = sqlite3.connect(di_module.settings.db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        """INSERT INTO memory_contexts
           (id, tier, payload, scope, status, created_at, updated_at, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            context_id,
            "SHORT_TERM",
            json.dumps({"source_type": "MANUAL_CONFIG", "raw": {"title": "沉淀测试"}}),
            "user:alice",
            "ACTIVE",
            now,
            now,
            now + 60,
        ),
    )
    conn.commit()
    conn.close()

    response = client.post(
        "/memory/flow/promote",
        json={
            "source": "SHORT_TERM",
            "context_ids": [context_id],
            "scope": "user:alice",
        },
    )
    assert response.status_code == 200
    assert response.json()["promoted_count"] == 1
    assert response.json()["knowledge_ids"][0].startswith("knw_")
    assert response.json()["latency_ms"] >= 0

    conn = sqlite3.connect(di_module.settings.db_path)
    row = conn.execute(
        "SELECT status, knowledge_id, expires_at FROM memory_contexts WHERE id = ?",
        (context_id,),
    ).fetchone()
    conn.close()
    assert row == ("PROMOTED", response.json()["knowledge_ids"][0], None)


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (FlowContextNotFound("ctx_missing"), 404, "NOT_FOUND"),
        (InvalidFlowTransition("expired"), 400, "INVALID_REQUEST"),
    ],
)
def test_flow_promote_maps_domain_errors(client, error, status, detail):
    class _Flow:
        async def promote(self, source, context_ids, scope):
            raise error

    async def _override_flow():
        return _Flow()

    app.dependency_overrides[get_flow_service] = _override_flow
    response = client.post(
        "/memory/flow/promote",
        json={
            "source": "MID_TERM",
            "context_ids": ["ctx_AAAAAAAAAAAAAAAAAAAAAAAAAA"],
            "scope": "shared:home",
        },
    )
    assert response.status_code == status
    # API.md §5：错误响应为 {"error", "message", "request_id"}
    assert response.json()["error"] == detail
    assert response.json()["request_id"]


def test_flow_promote_rejects_empty_context_ids(client):
    response = client.post(
        "/memory/flow/promote",
        json={"source": "SHORT_TERM", "context_ids": [], "scope": "user:alice"},
    )
    # API.md §5：请求体不符合 Schema → INVALID_REQUEST (400)
    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_REQUEST"
    assert response.json()["request_id"]


def _create_remote_pairing_token(db_path: str) -> str:
    async def _create() -> str:
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            service = SyncService(
                SqliteSyncStore(db),
                device_name="客厅一体机",
                domain="shared:home",
                key_passphrase="phase3-remote-test-passphrase",
            )
            return await service.create_pairing_token(PairingMethod.QR)
        finally:
            await db.close()

    sync_db = sqlite3.connect(db_path)
    init_db_on_connection(sync_db)
    sync_db.close()
    return asyncio.run(_create())


def test_sync_pair_peers_status_and_revoke(client):
    initial = client.get("/sync/status")
    assert initial.status_code == 200
    assert initial.json() == {
        "domain": "shared:home",
        "peers_online": 1,
        "peers_total": 1,
        "pending_outgoing_ops": 0,
        "last_anti_entropy_ts": None,
        "total_ops_synced": 0,
        "enabled": False,  # SN-4：KV 未写时回 env 默认（测试桩 sync_network_enabled=False）
        "paused": False,
    }

    remote_path = str(Path(di_module.settings.db_path).with_name("remote.db"))
    token = _create_remote_pairing_token(remote_path)
    paired = client.post(
        "/sync/pair", json={"method": "QR", "token": token, "pin": None}
    )
    assert paired.status_code == 200
    peer = paired.json()
    assert peer["device_name"] == "客厅一体机"
    assert peer["domain"] == "shared:home"
    assert peer["status"] == "paired"

    peers = client.get("/sync/peers").json()["peers"]
    assert len(peers) == 2
    assert sum(item["is_self"] for item in peers) == 1

    revoked = client.post(f"/sync/peers/{peer['peer_id']}/revoke")
    assert revoked.status_code == 200
    assert revoked.json() == {
        "status": "revoked",
        "peer_id": peer["peer_id"],
        "domain": "shared:home",
    }
    assert client.post(f"/sync/peers/{peer['peer_id']}/revoke").status_code == 404


def test_sync_pair_maps_invalid_token(client):
    response = client.post(
        "/sync/pair", json={"method": "QR", "token": "not-a-token"}
    )
    assert response.status_code == 422
    assert response.json()["error"] == "PAIRING_FAILED"
    assert response.json()["request_id"]


def test_sync_pair_request_rejects_invalid_target_id(client):
    response = client.post(
        "/sync/pair/request", json={"target_device_id": "not-a-device-id"}
    )
    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_REQUEST"
    assert response.json()["request_id"]


def test_sync_pair_confirm_unknown_request_not_found(client):
    response = client.post(
        "/sync/pair/confirm",
        json={"request_id": "req_missing_0001", "accept": True},
    )
    assert response.status_code == 404
    assert response.json()["error"] == "REQUEST_NOT_FOUND"


def test_sync_pair_confirm_accept_returns_status(client):
    created = client.post(
        "/sync/pair/request", json={"target_device_id": "dev_" + "B" * 26}
    )
    assert created.status_code == 200
    response = client.post(
        "/sync/pair/confirm",
        json={"request_id": created.json()["request_id"], "accept": True},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}


def test_sync_settings_put_persists_and_status_reflects(client):
    current = client.get("/sync/status").json()
    assert current["enabled"] is False
    assert current["paused"] is False

    updated = client.put("/sync/settings", json={"enabled": False, "paused": True})
    assert updated.status_code == 200
    assert updated.json() == {"enabled": False, "paused": True}

    status = client.get("/sync/status").json()
    assert status["enabled"] is False
    assert status["paused"] is True

    # 部分更新：只改 enabled，paused 保留
    reenabled = client.put("/sync/settings", json={"enabled": True})
    assert reenabled.status_code == 200
    assert reenabled.json() == {"enabled": True, "paused": True}
    status = client.get("/sync/status").json()
    assert status["enabled"] is True
    assert status["paused"] is True
    # SN-4 I-1：env=false 时 KV enabled=true 不再被 env 守卫否决，但测试桩
    # 无 TLS 配置 → di 装配降级，runtime 实际未启动；PUT/status 如实反映 KV。
    assert di_module._sync_runtime is None

    # 关闭后状态回读持久化
    off = client.put("/sync/settings", json={"enabled": False, "paused": False})
    assert off.json() == {"enabled": False, "paused": False}
    assert client.get("/sync/status").json()["enabled"] is False


def _sync_rows() -> list[tuple[str, dict]]:
    connection = sqlite3.connect(di_module.settings.db_path)
    rows = connection.execute(
        "SELECT entity, payload FROM sync_oplog ORDER BY ts, op_id"
    ).fetchall()
    connection.close()
    return [(entity, json.loads(payload)) for entity, payload in rows]


def test_shared_write_queues_only_signed_shared_operations(client):
    response = client.post(
        "/memory/write",
        json={"source_type": "OCR", "raw": OCR_RAW, "scope": "shared:home"},
    )
    assert response.status_code == 200
    rows = _sync_rows()
    assert {entity.split(":", 1)[0] for entity, _ in rows} >= {
        "evidence",
        "knowledge",
    }
    assert all(payload["scope"] == "shared:home" for _, payload in rows)
    assert all(isinstance(payload.get("signature"), str) for _, payload in rows)


def test_shared_merge_broadcasts_persisted_resolution_not_stale_input(client):
    first = client.post(
        "/memory/write",
        json={
            "source_type": "MANUAL_CONFIG",
            "raw": {
                "title": "shared invoice baseline",
                "body": {"vendor": "Acme", "amount": 10, "old_note": "baseline"},
            },
            "scope": "shared:home",
        },
    )
    second = client.post(
        "/memory/write",
        json={
            "source_type": "MANUAL_CONFIG",
            "raw": {
                "title": "shared invoice extension",
                "body": {"vendor": "Acme", "amount": 10, "new_note": "extension"},
            },
            "scope": "shared:home",
        },
    )

    assert first.status_code == second.status_code == 200
    assert second.json()["conflict_detected"] is True
    with sqlite3.connect(di_module.settings.db_path) as connection:
        row = connection.execute(
            """SELECT id, body FROM knowledge_items
               WHERE status = 'ACTIVE' AND body LIKE '%old_note%'
                 AND body LIKE '%new_note%'"""
        ).fetchone()
    assert row is not None
    knowledge_id, body_text = row
    persisted_body = json.loads(body_text)
    matching_ops = [
        payload
        for entity, payload in _sync_rows()
        if entity == f"knowledge:{knowledge_id}"
    ]
    assert matching_ops
    assert matching_ops[-1]["value"]["body"] == persisted_body
    assert matching_ops[-1]["value"]["version"] == 2


def _write_knowledge_id(client, *, title: str, scope: str) -> str:
    written = client.post(
        "/memory/write",
        json={
            "source_type": "MANUAL_CONFIG",
            "raw": {"title": title, "body": {"value": "before"}},
            "scope": scope,
        },
    )
    assert written.status_code == 200
    queried = client.post(
        "/memory/query", json={"text": title, "context_hint": {"top_k": 1, "scope": scope}}
    )
    assert queried.status_code == 200
    knowledge_id = queried.json()["source_knowledge"]
    assert knowledge_id
    return knowledge_id


def test_memory_item_reads_complete_versioned_snapshot_without_writes(client):
    knowledge_id = _write_knowledge_id(
        client, title="editable full snapshot", scope="user:alice"
    )
    complete_body = {"text": "完整正文" * 5000, "nested": {"items": [1, False, None]}}
    with sqlite3.connect(di_module.settings.db_path) as connection:
        connection.execute(
            "UPDATE knowledge_items SET body = ? WHERE id = ?",
            (json.dumps(complete_body), knowledge_id),
        )
        before = list(connection.iterdump())
    response = client.get(f"/memory/items/{knowledge_id}", params={"scope": "user:alice"})
    assert response.status_code == 200
    assert response.json() == {
        "knowledge_id": knowledge_id,
        "scope": "user:alice",
        "version": 1,
        "title": "editable full snapshot",
        "body": complete_body,
        "evidence_ids": response.json()["evidence_ids"],
        "updated_at": response.json()["updated_at"],
    }
    assert response.json()["evidence_ids"]
    with sqlite3.connect(di_module.settings.db_path) as connection:
        assert list(connection.iterdump()) == before


def test_memory_item_requires_scope_and_hides_unavailable_records(client):
    knowledge_id = _write_knowledge_id(
        client, title="scoped edit target", scope="user:alice"
    )
    url = f"/memory/items/{knowledge_id}"
    assert client.get(url).status_code == 400
    assert client.get(url, params={"scope": "all"}).status_code == 400
    for scope in ("user:bob", "shared:home"):
        response = client.get(url, params={"scope": scope})
        assert response.status_code == 404
        assert response.json()["error"] == "NOT_FOUND"
    assert client.get("/memory/items/knw_nonexistent", params={"scope": "user:alice"}).status_code == 404
    assert client.get("/memory/items/not-a-knowledge-id", params={"scope": "user:alice"}).status_code == 400
    for status in ("SUPERSEDED", "FORGOTTEN"):
        with sqlite3.connect(di_module.settings.db_path) as connection:
            connection.execute("UPDATE knowledge_items SET status = ? WHERE id = ?", (status, knowledge_id))
        response = client.get(url, params={"scope": "user:alice"})
        assert response.status_code == 404
        assert response.json()["error"] == "NOT_FOUND"


def test_memory_item_snapshot_version_rejects_intervening_update(client):
    knowledge_id = _write_knowledge_id(client, title="snapshot race target", scope="user:alice")
    url = f"/memory/items/{knowledge_id}"
    snapshot = client.get(url, params={"scope": "user:alice"}).json()
    payload = {"knowledge_id": knowledge_id, "scope": snapshot["scope"],
               "expected_version": snapshot["version"], "title": "first editor",
               "idempotency_key": "snapshot-first"}
    assert client.post("/memory/update", json=payload).status_code == 200
    stale = client.post("/memory/update", json={**payload, "title": "stale editor", "idempotency_key": "snapshot-stale"})
    assert stale.status_code == 409
    assert stale.json()["error"] == "VERSION_CONFLICT"
    current = client.get(url, params={"scope": "user:alice"}).json()
    assert current["version"] == snapshot["version"] + 1
    assert current["title"] == "first editor"


def test_memory_update_reindexes_and_replays_completed_request(client):
    knowledge_id = _write_knowledge_id(
        client, title="update target alpha", scope="user:alice"
    )
    request = {
        "knowledge_id": knowledge_id,
        "expected_version": 1,
        "scope": "user:alice",
        "title": "updated searchable beta",
        "body": {"value": "after"},
        "idempotency_key": "update-alpha-1",
    }

    first = client.post("/memory/update", json=request)
    replay = client.post("/memory/update", json=request)

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert first.json()["knowledge_id"] == knowledge_id
    assert first.json()["version"] == 2
    evidence = client.get(f"/evidence/{first.json()['evidence_id']}")
    assert evidence.status_code == 200
    assert evidence.json()["raw"]["body"]["operation"] == "knowledge_update"
    queried = client.post(
        "/memory/query",
        json={"text": "updated searchable beta", "context_hint": {"top_k": 1}},
    )
    assert queried.json()["source_knowledge"] == knowledge_id


def test_shared_memory_update_queues_same_entity_version(client):
    knowledge_id = _write_knowledge_id(
        client, title="shared update target", scope="shared:home"
    )
    response = client.post(
        "/memory/update",
        json={
            "knowledge_id": knowledge_id,
            "expected_version": 1,
            "scope": "shared:home",
            "body": {"value": "concurrent-ready"},
            "idempotency_key": "shared-update-1",
        },
    )

    assert response.status_code == 200
    matching = [
        payload
        for entity, payload in _sync_rows()
        if entity == f"knowledge:{knowledge_id}"
    ]
    assert len(matching) == 2
    assert matching[-1]["value"]["id"] == knowledge_id
    assert matching[-1]["value"]["version"] == 2
    assert matching[-1]["signature"]


def test_memory_update_rejects_version_scope_and_sensitive_shared_data(client):
    knowledge_id = _write_knowledge_id(
        client, title="guarded shared update", scope="shared:home"
    )
    base = {
        "knowledge_id": knowledge_id,
        "expected_version": 2,
        "scope": "shared:home",
        "title": "safe title",
        "idempotency_key": "guard-update-version",
    }
    version = client.post("/memory/update", json=base)
    assert version.status_code == 409
    assert version.json()["error"] == "VERSION_CONFLICT"

    wrong_scope = client.post(
        "/memory/update",
        json={**base, "scope": "user:alice", "idempotency_key": "guard-update-scope"},
    )
    assert wrong_scope.status_code == 404

    before_rows = _sync_rows()
    sensitive = client.post(
        "/memory/update",
        json={
            **base,
            "expected_version": 1,
            "title": "call 13800138000",
            "idempotency_key": "guard-update-sensitive",
        },
    )
    assert sensitive.status_code == 422
    assert sensitive.json()["error"] == "SENSITIVE_SHARED_SCOPE"
    assert _sync_rows() == before_rows


def test_failed_memory_update_requires_explicit_recovery(client):
    knowledge_id = _write_knowledge_id(
        client, title="recoverable update target", scope="user:alice"
    )
    payload = {
        "knowledge_id": knowledge_id,
        "expected_version": 1,
        "scope": "user:alice",
        "title": "recovered update",
        "idempotency_key": "update-recovery-1",
    }

    class _FailingKnowledge:
        async def update(self, item, *, expected_version=None):
            raise HTTPException(status_code=503, detail="INJECTED_FAILURE")

    working_knowledge = app.dependency_overrides[get_knowledge_service]
    app.dependency_overrides[get_knowledge_service] = lambda: _FailingKnowledge()
    try:
        failed = client.post("/memory/update", json=payload)
    finally:
        app.dependency_overrides[get_knowledge_service] = working_knowledge

    assert failed.status_code == 503
    blocked = client.post("/memory/update", json=payload)
    assert blocked.status_code == 409
    assert blocked.json()["error"] == "IDEMPOTENCY_FAILED"
    recovered = client.post(
        "/agent/idempotency/recover",
        json={
            "operation": "MEMORY_UPDATE",
            "original_request": payload,
            "confirm_duplicate_risk": True,
            "reason": "verified update did not complete",
        },
    )
    assert recovered.status_code == 200
    assert recovered.json()["operation"] == "MEMORY_UPDATE"
    assert client.post("/memory/update", json=payload).status_code == 200


def test_user_write_never_enters_sync_oplog(client):
    response = client.post(
        "/memory/write",
        json={"source_type": "OCR", "raw": OCR_RAW, "scope": "user:alice"},
    )
    assert response.status_code == 200
    assert _sync_rows() == []


def test_shared_forget_queues_knowledge_tombstone(client):
    client.post(
        "/memory/write",
        json={"source_type": "OCR", "raw": OCR_RAW, "scope": "shared:home"},
    )
    preview = client.post("/forget", json={"command": "忘记那张4月支出清单"}).json()
    response = client.post(
        "/forget", json={"command": "忘记那张4月支出清单", "confirm": True,
                          "confirmation_token": preview["confirmation_token"]}
    )
    assert response.status_code == 200
    tombstones = [
        payload
        for entity, payload in _sync_rows()
        if entity.startswith("knowledge:") and payload.get("deleted") is True
    ]
    assert len(tombstones) == 1
    assert tombstones[0]["scope"] == "shared:home"


def test_sync_knowledge_state_exposes_tombstone_without_payload(client):
    missing = client.get("/sync/state/knowledge/knw_MMMMMMMMMMMMMMMMMMMMMMMMMM")
    assert missing.status_code == 200
    assert missing.json() == {
        "present": False,
        "tombstone": False,
        "clock_entries": 0,
        "clock_total": 0,
        "operation_digest": None,
        "updated_at": None,
    }
    assert client.get("/sync/state/knowledge/not-valid").status_code == 400

    knowledge_id = _write_knowledge_id(
        client, title="shared state marker", scope="shared:home"
    )
    active = client.get(f"/sync/state/knowledge/{knowledge_id}")
    assert active.status_code == 200
    assert active.json()["present"] is True
    assert active.json()["tombstone"] is False
    assert active.json()["clock_entries"] == 1
    assert active.json()["clock_total"] == 1
    assert len(active.json()["operation_digest"]) == 64
    assert "payload" not in active.json()

    forgotten = client.post(
        "/forget", json={"command": "忘记shared state marker", "confirm": True,
                          "confirmation_token": client.post("/forget", json={"command": "忘记shared state marker"}).json()["confirmation_token"]}
    )
    assert forgotten.status_code == 200
    deleted = client.get(f"/sync/state/knowledge/{knowledge_id}")
    assert deleted.status_code == 200
    assert deleted.json()["present"] is True
    assert deleted.json()["tombstone"] is True
    assert deleted.json()["clock_total"] == 2
    assert deleted.json()["operation_digest"] != active.json()["operation_digest"]
    encoded = json.dumps(deleted.json(), ensure_ascii=False)
    assert "shared state marker" not in encoded
    assert "shared:home" not in encoded


def test_agent_authorized_capture_and_shared_spaces(client):
    for scope in ('user:local', 'shared:home', 'user:other'):
        response = client.post('/memory/write', json={
            'source_type': 'MANUAL_CONFIG',
            'raw': {'title': '家庭会议安排', 'body': {'text': '周五讨论采购'}},
            'scope': scope,
        })
        assert response.status_code == 200
    request = {'query': '家庭会议安排', 'scope': 'user:default',
               'session_id': 'session-access', 'turn_id': 'turn-1', 'use_settings': True}
    result = client.post('/agent/context', json=request).json()
    assert {item['scope'] for item in result['items']} == {'user:local'}
    saved = client.put('/agent/settings', json={
        'include_capture': True, 'shared_scopes': ['shared:home'], 'write_scope': 'user:local'})
    assert saved.status_code == 200
    result = client.post('/agent/context', json=request).json()
    assert {item['scope'] for item in result['items']} == {'user:local', 'shared:home'}
    # Explicit low-level calls preserve the original one-space contract.
    request['use_settings'] = False
    assert client.post('/agent/context', json=request).json()['items'] == []
    assert client.put('/agent/settings', json={'shared_scopes': ['user:other']}).status_code == 400


def test_conversation_preference_applies_in_new_session_and_updates(client):
    for index, (text, style) in enumerate([('以后请简洁回答', 'compact'), ('以后请详细回答', 'verbose')]):
        response = client.post('/memory/write', json={
            'source_type': 'CONVERSATION', 'raw': {'user': text, 'assistant': '我可以简洁也可以详细回答'},
            'scope': 'user:default', 'idempotency_key': f'preference-turn-{index}',
            'provenance': {'session_id': 'preference-session', 'run_id': f'run-{index}',
                           'turn_id': f'turn-{index}', 'occurred_at': 1700000011 + index}})
        assert response.status_code == 200
        result = client.post('/agent/context', json={'query': '帮我准备采购计划',
            'scope': 'user:default', 'session_id': f'new-session-{index}', 'turn_id': 'turn-1',
            'use_settings': True}).json()
        assert result['preferences'][0]['value']['verbosity'] == style
        assert result['preferences'][0]['version'] == index + 1
        assert ('简洁回答' if style == 'compact' else '详细回答') in result['context']
    history = client.get('/preference/' + result['preferences'][0]['id'] + '/history').json()
    assert history


def test_stage_memory_can_be_reviewed_and_kept(client):
    response = client.post('/agent/lifecycle', json={'event': 'PRE_COMPRESS', 'scope': 'user:alice',
        'session_id': 'stage-session', 'run_id': 'run-1', 'turn_id': 'turn-1',
        'occurred_at': 1700000020, 'idempotency_key': 'stage-promote',
        'data': {'summary': '采购流程：确认预算，再比较报价'}})
    assert response.status_code == 200
    contexts = client.get('/memory/flow/contexts', params={'scope': 'user:alice'}).json()['contexts']
    entry = next(x for x in contexts if x['id'] == response.json()['context_id'])
    kept = client.post('/memory/flow/promote', json={'source': entry['tier'],
        'scope': 'user:alice', 'context_ids': [entry['id']]})
    assert kept.status_code == 200
    context = client.post('/agent/context', json={'query': '采购流程', 'scope': 'user:alice',
        'session_id': 'another-session', 'turn_id': 'turn-1'}).json()
    assert '比较报价' in context['context']


def test_manual_conflict_review_retains_chosen_memory(client):
    ids = []
    for amount in (156, 186):
        response = client.post("/memory/write", json={
            "source_type": "OCR", "scope": "user:alice",
            "raw": {"title": "燃气账单待确认", "body": {
                "items": [{"vendor": "新奥燃气", "amount": amount}]}},
        })
        assert response.status_code == 200, response.text
    records = client.get("/conflicts").json()["conflicts"]
    record = next(item for item in records if item["resolution"] == "MANUAL")
    path = "/conflicts/" + record["id"]
    review = client.get(path + "/review")
    assert review.status_code == 200, review.text
    candidates = review.json()["candidates"]
    assert len(candidates) == 2
    keep = next(item for item in candidates if item["body"]["items"][0]["amount"] == 186)
    versions = {item["id"]: item["version"] for item in candidates}
    stale = dict(versions)
    stale[keep["id"]] += 1
    assert client.post(path + "/resolve", json={"keep_id": keep["id"], "versions": stale}).status_code == 409
    resolved = client.post(path + "/resolve", json={"keep_id": keep["id"], "versions": versions})
    assert resolved.status_code == 200, resolved.text
    with sqlite3.connect(di_module.settings.db_path) as db:
        active = db.execute("SELECT id FROM knowledge_items WHERE status = 'ACTIVE' AND scope = 'user:alice'").fetchall()
    assert active == [(keep["id"],)]
    assert client.get(path + "/review").status_code == 409


def test_automatic_sources_only_show_consumed_context_and_active_memories(client):
    written = client.post("/memory/write", json={"source_type": "OCR", "scope": "user:alice", "raw": OCR_RAW})
    assert written.status_code == 200
    request = {"query": "家庭支出", "scope": "user:alice", "session_id": "source-session", "turn_id": "turn-1", "trace": True}
    context = client.post("/agent/context", json=request).json()
    assert context["items"]
    params = {"session_id": "source-session", "scope": "user:alice"}
    assert client.get("/agent/sources", params=params).json()["references"] == []
    assert client.post("/agent/sources/" + context["trace_id"] + "/consume").status_code == 200
    sources = client.get("/agent/sources", params=params).json()["references"]
    assert sources[0]["evidence_id"] == context["items"][0]["evidence_ids"][0]
    assert client.get("/memory/flow/contexts", params={"scope": "user:alice"}).json()["contexts"] == []
    assert client.get("/agent/sources", params={**params, "session_id": "another-session"}).json()["references"] == []
    with sqlite3.connect(di_module.settings.db_path) as db:
        db.execute("UPDATE knowledge_items SET status = 'SUPERSEDED' WHERE id = ?", (sources[0]["knowledge_id"],))
    assert client.get("/agent/sources", params=params).json()["references"] == []


def test_confirmed_image_bill_keeps_image_and_uses_edited_amount(client):
    from backend.foundation.api.di import get_ocr_service
    image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aSAAAAABJRU5ErkJggg=="
    class Ocr:
        def recognize(self, path):
            return ["2026年4月家庭账单", "燃气费 156元", "电费 210元", "合计 366元"]
    _install_ocr_override(Ocr())
    try:
        draft = client.post("/memory/ocr", json={"image_base64": image}).json()
    finally:
        app.dependency_overrides.pop(get_ocr_service, None)
    assert len(draft["items"]) == 2
    # User corrects the OCR draft before explicitly saving it.
    draft["items"][0]["amount"] = 186
    saved = client.post("/memory/write", json={"scope": "user:alice", "source_type": "OCR", "raw": {
        "title": "2026年4月家庭账单", "body": {"text": draft["text"], "items": draft["items"]},
        "original_image": {"name": "bill.png", "base64": image}}})
    assert saved.status_code == 200, saved.text
    evidence = client.get("/evidence/" + saved.json()["evidence_id"])
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["raw"]["original_image"]["base64"] == image
    result = client.post("/memory/query", json={"text": "2026年4月燃气费多少", "context_hint": {"scope": "user:alice"}})
    assert result.status_code == 200
    assert "186" in result.json()["answer"]
