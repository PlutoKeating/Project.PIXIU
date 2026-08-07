"""Tests for api/http_app.py — REST 端点端到端（临时 SQLite + mock embedding）。"""

from __future__ import annotations

import os

os.environ.setdefault("PIXIU_EMBEDDING", "mock")

import pytest
from fastapi.testclient import TestClient

import backend.foundation.api.di as di_module
from backend.foundation.api import app


class _FakeSettings:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(di_module, "settings", _FakeSettings(str(tmp_path / "pixiu.db")))
    di_module._db = None
    with TestClient(app) as c:
        yield c
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


def test_unimplemented_endpoints_keep_placeholder(client):
    assert client.post("/memory/query", json={}).json()["status"] == "not_implemented"
    assert client.post("/memory/flow/promote", json={}).json()["status"] == "not_implemented"
    assert client.post("/sync/pair", json={}).json()["status"] == "not_implemented"
    assert client.get("/sync/peers").json()["status"] == "not_implemented"
    assert client.get("/sync/status").json()["status"] == "not_implemented"
