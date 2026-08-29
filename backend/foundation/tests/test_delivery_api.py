"""GET /delivery/insights 端点契约（批次④ B4-1）：真实 SQLite 仓储端到端。

对齐 docs/compose/specs/2026-08-29-batch4-delivery-layer-design.md [S3]：
  - limit 缺省 3、上限 10（>10 → 400 INVALID_REQUEST，错误体 {error, message, request_id}）；
  - 空库/无候选 → {"insights": []}；
  - 洞察面向本机用户域（user:local），按关联证据质量降序、过滤敏感、MANUAL 待处理抑制。
"""

from __future__ import annotations

import asyncio
import sqlite3
import time

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import backend.foundation.api.di as di_module
from backend.foundation.api import app
from backend.foundation.core.idgen import gen_conflict_id, gen_evidence_id, gen_knowledge_id
from backend.foundation.core.models import (
    ConflictRecord,
    Evidence,
    KnowledgeItem,
    KnowledgeKind,
    SourceType,
)
from backend.foundation.storage.repository import (
    SqliteConflictRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
)
from backend.foundation.storage.schema import init_db_on_connection


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
    di_module._sync_runtime = None
    di_module._delivery_service = None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    di_module._db = None
    di_module._sync_runtime = None
    di_module._delivery_service = None


def _seed(
    db_path: str,
    items: list[dict] | None = None,
    conflicts: list[str] | None = None,
) -> None:
    """用真实 Sqlite 仓储写入种子数据（独立连接 + 幂等建表）。"""

    async def _run() -> None:
        sync_conn = sqlite3.connect(db_path)
        init_db_on_connection(sync_conn)
        sync_conn.close()
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            ev_repo = SqliteEvidenceRepo(db)
            kn_repo = SqliteKnowledgeRepo(db)
            cf_repo = SqliteConflictRepo(db)
            for it in items or []:
                eid = gen_evidence_id()
                kid = gen_knowledge_id()
                raw = {"title": it["title"], "body": {"text": it["body_text"]}}
                await ev_repo.save(
                    Evidence(
                        id=eid,
                        source_type=SourceType.MANUAL_CONFIG,
                        raw=raw,
                        quality_score=it["quality"],
                        sensitivity=it["sensitivity"],
                        scope=it["scope"],
                        created_at=it["created_at"],
                    )
                )
                await kn_repo.save(
                    KnowledgeItem(
                        id=kid,
                        kind=KnowledgeKind.FACT,
                        title=it["title"],
                        body={"text": it["body_text"]},
                        scope=it["scope"],
                        created_at=it["created_at"],
                        updated_at=it["created_at"],
                        evidence_ids=[eid],
                    )
                )
            for resolution in conflicts or []:
                await cf_repo.save(
                    ConflictRecord(
                        id=gen_conflict_id(),
                        target_knowledge="knw_seed",
                        field="body",
                        old_value={},
                        new_value={},
                        resolution=resolution,
                        created_at=int(time.time()),
                        source="write",
                    )
                )
        finally:
            await db.close()

    asyncio.run(_run())


def _item(
    title: str,
    *,
    quality: float = 0.5,
    sensitivity: int = 0,
    scope: str = "user:local",
    created_at: int | None = None,
    body_text: str = "正文",
) -> dict:
    return {
        "title": title,
        "body_text": body_text,
        "quality": quality,
        "sensitivity": sensitivity,
        "scope": scope,
        "created_at": created_at if created_at is not None else int(time.time()),
    }


def test_insights_empty_when_no_data(client):
    resp = client.get("/delivery/insights")
    assert resp.status_code == 200
    assert resp.json() == {"insights": []}


def test_insights_default_limit_three_ranked_by_quality(client):
    db_path = di_module.settings.db_path
    _seed(
        db_path,
        items=[
            _item("低分", quality=0.2),
            _item("中分", quality=0.5),
            _item("最高分", quality=0.95),
            _item("次高分", quality=0.7),
            _item("最低分", quality=0.1),
        ],
    )
    resp = client.get("/delivery/insights")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["insights"]) == 3  # 缺省 limit=3
    assert [i["title"] for i in data["insights"]] == ["最高分", "次高分", "中分"]
    assert all(i["kind"] == "recent" for i in data["insights"])
    assert all(i["knowledge_id"].startswith("knw_") for i in data["insights"])
    assert [i["score"] for i in data["insights"]] == [0.95, 0.7, 0.5]


def test_insights_explicit_limit(client):
    db_path = di_module.settings.db_path
    _seed(
        db_path,
        items=[
            _item("A", quality=0.9),
            _item("B", quality=0.8),
            _item("C", quality=0.7),
        ],
    )
    resp = client.get("/delivery/insights", params={"limit": 2})
    assert resp.status_code == 200
    titles = [i["title"] for i in resp.json()["insights"]]
    assert titles == ["A", "B"]


def test_insights_filters_sensitive_evidence(client):
    db_path = di_module.settings.db_path
    _seed(
        db_path,
        items=[
            _item("敏感高分", quality=0.95, sensitivity=3),
            _item("普通低分", quality=0.4),
        ],
    )
    resp = client.get("/delivery/insights")
    assert resp.status_code == 200
    titles = [i["title"] for i in resp.json()["insights"]]
    assert titles == ["普通低分"]


def test_insights_scope_is_local_only(client):
    db_path = di_module.settings.db_path
    _seed(
        db_path,
        items=[
            _item("本机记忆", quality=0.9, scope="user:local"),
            _item("他人记忆", quality=0.99, scope="user:alice"),
            _item("共享记忆", quality=0.98, scope="shared:home"),
        ],
    )
    resp = client.get("/delivery/insights")
    titles = [i["title"] for i in resp.json()["insights"]]
    assert titles == ["本机记忆"]


def test_insights_24h_window_excludes_stale(client):
    db_path = di_module.settings.db_path
    _seed(
        db_path,
        items=[
            _item("过期记忆", quality=0.99, created_at=int(time.time()) - 25 * 3600),
            _item("新记忆", quality=0.5),
        ],
    )
    resp = client.get("/delivery/insights")
    titles = [i["title"] for i in resp.json()["insights"]]
    assert titles == ["新记忆"]


def test_insights_suppressed_when_manual_conflict_pending(client):
    db_path = di_module.settings.db_path
    _seed(
        db_path,
        items=[_item("高分记忆", quality=0.99)],
        conflicts=["MANUAL"],
    )
    resp = client.get("/delivery/insights")
    assert resp.status_code == 200
    assert resp.json() == {"insights": []}


def test_insights_not_suppressed_when_auto_resolved_conflicts(client):
    db_path = di_module.settings.db_path
    _seed(
        db_path,
        items=[_item("高分记忆", quality=0.99)],
        conflicts=["NEW_WINS", "MERGE"],
    )
    resp = client.get("/delivery/insights")
    assert len(resp.json()["insights"]) == 1


def test_insights_limit_above_max_returns_400(client):
    resp = client.get("/delivery/insights", params={"limit": 11})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "INVALID_REQUEST"
    assert body["message"]
    assert body["request_id"]


def test_insights_summary_contains_title_and_body_prefix(client):
    db_path = di_module.settings.db_path
    _seed(
        db_path,
        items=[
            _item("标题甲", quality=0.5, body_text="x" * 100),
        ],
    )
    resp = client.get("/delivery/insights")
    assert resp.json()["insights"][0]["summary"] == "标题甲：" + "x" * 60
