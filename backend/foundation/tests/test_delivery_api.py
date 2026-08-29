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
from datetime import datetime

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import backend.foundation.api.di as di_module
from backend.foundation.api import app
from backend.foundation.api.monitor_log import MonitorLogStore
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
    di_module._monitor_log_store = None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    di_module._db = None
    di_module._sync_runtime = None
    di_module._delivery_service = None
    di_module._monitor_log_store = None


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


def test_insights_limit_below_one_returns_400(client):
    # Query(ge=1) 校验：limit=0 → RequestValidationError → 400 统一错误体
    resp = client.get("/delivery/insights", params={"limit": 0})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "INVALID_REQUEST"
    assert body["message"]
    assert body["request_id"]


def test_insights_limit_at_max_ok(client):
    # Query(le=10) 边界内：limit=10 → 200，不触发 400
    resp = client.get("/delivery/insights", params={"limit": 10})
    assert resp.status_code == 200
    assert resp.json() == {"insights": []}


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


# ═══════════════════════════════════════════════════════
# GET /delivery/digest（批次④ B4-2）：按日聚合 monitor_log 生成中文简报
# ═══════════════════════════════════════════════════════

def _local_ts(y: int, m: int, d: int, hh: int = 12) -> int:
    """本地时区时间戳（与后端日边界计算同源，断言与运行机时区无关）。"""
    return int(datetime(y, m, d, hh, 0, 0).timestamp())


def test_digest_empty_defaults_to_today(client):
    resp = client.get("/delivery/digest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == datetime.now().strftime("%Y-%m-%d")
    assert data["summary"] == "当日无新记忆"


def test_digest_aggregates_seeded_day(client):
    store = MonitorLogStore(str(di_module.settings.db_path))
    store.write_event(
        source="directory", status="ingested", summary="记住文件 a.txt", ts=_local_ts(2026, 8, 29)
    )
    store.write_event(
        source="directory", status="ingested", summary="记住文件 b.txt", ts=_local_ts(2026, 8, 29)
    )
    store.write_event(
        source="clipboard", status="ingested", summary="剪贴板内容", ts=_local_ts(2026, 8, 29)
    )
    store.write_event(
        source="clipboard", status="sensitive_quarantined", summary="敏感剪贴板", ts=_local_ts(2026, 8, 29)
    )
    resp = client.get("/delivery/digest", params={"date": "2026-08-29"})
    assert resp.status_code == 200
    assert resp.json() == {
        "date": "2026-08-29",
        "summary": "当日新增 3 条记忆（目录 2、剪贴板 1），另有 1 条敏感内容已隔离",
    }


def test_digest_ignores_events_outside_day(client):
    store = MonitorLogStore(str(di_module.settings.db_path))
    store.write_event(
        source="directory", status="ingested", summary="昨日", ts=_local_ts(2026, 8, 28)
    )
    store.write_event(
        source="directory", status="ingested", summary="今日", ts=_local_ts(2026, 8, 29)
    )
    resp = client.get("/delivery/digest", params={"date": "2026-08-29"})
    assert resp.json()["summary"] == "当日新增 1 条记忆（目录 1）"


def test_digest_summary_contains_no_raw_summary(client):
    store = MonitorLogStore(str(di_module.settings.db_path))
    raw = "含医保卡号 12345 的敏感文件内容"
    store.write_event(
        source="directory", status="ingested", summary=raw, ts=_local_ts(2026, 8, 29)
    )
    resp = client.get("/delivery/digest", params={"date": "2026-08-29"})
    assert "12345" not in resp.json()["summary"]


@pytest.mark.parametrize(
    "bad",
    [
        "",             # 空串：显式传空 → 400（区别于缺省回退今天）
        "2026-13-01",   # 月越界
        "2026-02-30",   # 无效日历日
        "2026-1-1",     # 非严格两位
        "20260829",     # 非分隔格式
        "2026/08/29",   # 错误分隔符
        "not-a-date",   # 非日期
    ],
)
def test_digest_invalid_date_returns_400(client, bad):
    resp = client.get("/delivery/digest", params={"date": bad})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "INVALID_REQUEST"
    assert body["message"]
    assert body["request_id"]
