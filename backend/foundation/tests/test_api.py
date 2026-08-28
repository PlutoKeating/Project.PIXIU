"""Tests for api/http_app.py — REST 端点端到端（临时 SQLite + 测试桩 embedding）。"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import backend.foundation.api.di as di_module
from backend.foundation.api import app
from backend.engine.knowledge import KnowledgeService
from backend.engine.tests.fakes import StubTextEmbedder
from backend.foundation.api.di import get_flow_service, get_knowledge_service
from backend.foundation.flow import FlowContextNotFound, InvalidFlowTransition
from backend.foundation.storage.repository import (
    SqliteEntityRepo,
    SqliteKnowledgeRepo,
)
from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.sync import PairingMethod, SqliteSyncStore, SyncService


class _FakeSettings:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.embedding = "portable"
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


OCR_RAW = {
    "title": "2026年4月家庭支出清单",
    "body": {
        "items": [
            {"category": "水电燃气", "vendor": "国家电网", "amount": 210.0}
        ]
    },
}


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
        "/forget", json={"command": "忘记那张4月支出清单", "confirm": True}
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
    response = client.post(
        "/forget", json={"command": "\u5fd8\u8bb0\u90a3\u5f204\u6708\u652f\u51fa\u6e05\u5355", "confirm": True}
    )
    assert response.status_code == 200
    tombstones = [
        payload
        for entity, payload in _sync_rows()
        if entity.startswith("knowledge:") and payload.get("deleted") is True
    ]
    assert len(tombstones) == 1
    assert tombstones[0]["scope"] == "shared:home"
