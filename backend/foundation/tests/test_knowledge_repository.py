"""Tests for storage/repository.py — SqliteKnowledgeRepo with FTS5."""

from __future__ import annotations

import time
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.core.models import (
    Evidence,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeStatus,
    SourceType,
)
from backend.foundation.storage.repository import (
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
)
from backend.foundation.storage.schema import init_db_on_connection

NOW = int(time.time())


@pytest_asyncio.fixture
async def repo(tmp_path: Path):
    """临时数据库 + 知识仓储（含基础表，FTS 由仓储惰性创建）。"""
    db_path = str(tmp_path / "test.db")
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")

    import sqlite3 as _sync_sqlite3
    sync_conn = _sync_sqlite3.connect(db_path)
    init_db_on_connection(sync_conn)
    sync_conn.close()

    kr = SqliteKnowledgeRepo(db)
    er = SqliteEvidenceRepo(db)
    yield kr, er, db_path
    await db.close()


def _id(tag: str) -> str:
    body = (tag + "0" * 26)[:26]
    return f"knw_{body}"


def _evd_id(tag: str) -> str:
    body = (tag + "0" * 26)[:26]
    return f"evd_{body}"


def _knw(**kwargs) -> KnowledgeItem:
    defaults = {
        "id": _id("main"),
        "kind": KnowledgeKind.FACT,
        "title": "2026年4月家庭支出清单",
        "scope": "shared:home",
        "created_at": NOW,
        "updated_at": NOW,
    }
    return KnowledgeItem(**(defaults | kwargs))


# ═══════════════════════════════════════════════════════
# Group 1: save + get
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_save_returns_id(repo):
    kr, _, _ = repo
    item = _knw()
    result = await kr.save(item)
    assert result == item.id


@pytest.mark.asyncio
async def test_get_returns_saved(repo):
    kr, _, _ = repo
    item = _knw(
        kind=KnowledgeKind.TEMPLATE,
        body={"description": "报销模板", "fields": ["name", "amount"]},
        status=KnowledgeStatus.ACTIVE,
        version=3,
        scope="user:alice",
    )
    await kr.save(item)

    fetched = await kr.get(item.id)
    assert fetched is not None
    assert fetched.kind == KnowledgeKind.TEMPLATE
    assert fetched.body == {"description": "报销模板", "fields": ["name", "amount"]}
    assert fetched.status == KnowledgeStatus.ACTIVE
    assert fetched.version == 3
    assert fetched.scope == "user:alice"


@pytest.mark.asyncio
async def test_get_missing_returns_none(repo):
    kr, _, _ = repo
    assert (await kr.get(_id("missing"))) is None


# ═══════════════════════════════════════════════════════
# Group 2: evidence association (knowledge_evidence)
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_save_writes_evidence_association(repo):
    kr, er, _ = repo
    evd = Evidence(
        id=_evd_id("evd1"),
        source_type=SourceType.OCR,
        raw={"title": "清单照片"},
        scope="shared:home",
        created_at=NOW,
    )
    await er.save(evd)

    item = _knw(evidence_ids=[evd.id])
    await kr.save(item)

    rows = await kr._db.execute_fetchall(
        "SELECT knowledge_id, evidence_id FROM knowledge_evidence WHERE knowledge_id = ?",
        (item.id,),
    )
    assert len(rows) == 1
    assert rows[0]["evidence_id"] == evd.id


@pytest.mark.asyncio
async def test_link_evidence_manual(repo):
    kr, er, _ = repo
    evd = Evidence(
        id=_evd_id("evd2"),
        source_type=SourceType.TOOL_RESULT,
        raw={},
        scope="user:alice",
        created_at=NOW,
    )
    await er.save(evd)
    item = _knw()
    await kr.save(item)

    await kr.link_evidence(item.id, evd.id)

    rows = await kr._db.execute_fetchall(
        "SELECT * FROM knowledge_evidence WHERE knowledge_id = ? AND evidence_id = ?",
        (item.id, evd.id),
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_link_evidence_ignores_duplicate(repo):
    kr, er, _ = repo
    evd = Evidence(
        id=_evd_id("evd3"),
        source_type=SourceType.MANUAL_CONFIG,
        raw={},
        scope="user:alice",
        created_at=NOW,
    )
    await er.save(evd)
    item = _knw()
    await kr.save(item)

    await kr.link_evidence(item.id, evd.id)
    await kr.link_evidence(item.id, evd.id)

    rows = await kr._db.execute_fetchall(
        "SELECT COUNT(*) AS c FROM knowledge_evidence WHERE knowledge_id = ?",
        (item.id,),
    )
    assert rows[0]["c"] == 1


# ═══════════════════════════════════════════════════════
# Group 3: Chinese keyword search via FTS5 (trigram)
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_search_fts_chinese_substring(repo):
    kr, _, _ = repo
    await kr.save(_knw(title="2026年4月家庭支出清单", body={"description": "水电燃气支出记录"}))
    await kr.save(_knw(id=_id("other"), title="项目周报", body={"description": "工作内容汇总"}))

    results = await kr.search_fts("家庭支出", limit=10)
    assert len(results) == 1
    assert results[0].title == "2026年4月家庭支出清单"


@pytest.mark.asyncio
async def test_search_fts_matches_body(repo):
    kr, _, _ = repo
    await kr.save(_knw(title="支出清单", body={"description": "国家电网电费210元"}))

    results = await kr.search_fts("国家电网", limit=10)
    assert len(results) == 1
    assert results[0].title == "支出清单"


@pytest.mark.asyncio
async def test_search_fts_no_match_returns_empty(repo):
    kr, _, _ = repo
    await kr.save(_knw(title="日常记录"))

    results = await kr.search_fts("不存在的词汇", limit=10)
    assert results == []


@pytest.mark.asyncio
async def test_search_fts_returns_models_not_rows(repo):
    kr, _, _ = repo
    await kr.save(_knw(title="测试标题"))

    results = await kr.search_fts("测试标题", limit=10)
    assert len(results) == 1
    assert isinstance(results[0], KnowledgeItem)
    assert not hasattr(results[0], "keys")  # not a dict/row


# ═══════════════════════════════════════════════════════
# Group 4: index update (re-save with new title)
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_resave_updates_fts_index(repo):
    kr, _, _ = repo
    item_id = _id("update")
    await kr.save(_knw(id=item_id, title="旧标题"))

    # FTS finds old title
    assert len(await kr.search_fts("旧标题", 10)) == 1

    # Re-save with new title (same id)
    await kr.save(_knw(id=item_id, title="新标题", updated_at=NOW + 1))

    # New title found
    new_hits = await kr.search_fts("新标题", 10)
    assert len(new_hits) == 1
    assert new_hits[0].title == "新标题"

    # Old title no longer found
    assert (await kr.search_fts("旧标题", 10)) == []


@pytest.mark.asyncio
async def test_resave_does_not_duplicate_rows(repo):
    kr, _, _ = repo
    item_id = _id("dup")
    await kr.save(_knw(id=item_id, title="第一版"))
    await kr.save(_knw(id=item_id, title="第二版", version=2))

    rows = await kr._db.execute_fetchall(
        "SELECT COUNT(*) AS c FROM knowledge_items WHERE id = ?", (item_id,)
    )
    assert rows[0]["c"] == 1
    fts_rows = await kr._db.execute_fetchall(
        "SELECT COUNT(*) AS c FROM knowledge_fts WHERE title = ?", ("第二版",)
    )
    assert fts_rows[0]["c"] == 1


# ═══════════════════════════════════════════════════════
# Group 5: transaction rollback
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_save_rolls_back_on_fts_failure(repo):
    """knowledge_items 写入成功但 FTS 写入失败 → 全部回滚。"""
    kr, _, _ = repo
    item_id = _id("rollback")
    await kr.save(_knw(id=item_id, title="稳定记录"))

    # 破坏 FTS 表，使下一次 save 的 FTS 写入失败
    await kr._db.execute("DROP TABLE knowledge_fts")
    await kr._db.commit()

    # _fts_ready 缓存为 True，不会重建 → FTS 写入抛异常
    with pytest.raises(Exception):
        await kr.save(_knw(id=_id("rollback2"), title="失败记录"))

    # 重建 FTS 表后验证：成功保存的记录仍在，失败记录不存在
    await kr._db.execute(
        "CREATE VIRTUAL TABLE knowledge_fts USING fts5(title, body_text, tokenize='trigram')"
    )
    await kr._db.commit()
    kr._fts_ready = True

    assert (await kr.get(item_id)) is not None
    assert (await kr.get(_id("rollback2"))) is None


@pytest.mark.asyncio
async def test_save_rolls_back_on_closed_connection(repo, tmp_path):
    kr, _, db_path = repo
    item_id = _id("stable")
    await kr.save(_knw(id=item_id, title="完好记录"))

    await kr._db.close()
    with pytest.raises(Exception):
        await kr.save(_knw(id=_id("fail"), title="失败"))

    db2 = await aiosqlite.connect(db_path)
    db2.row_factory = aiosqlite.Row
    kr2 = SqliteKnowledgeRepo(db2)
    assert (await kr2.get(item_id)) is not None
    assert (await kr2.get(_id("fail"))) is None
    await db2.close()


# ═══════════════════════════════════════════════════════
# Group 6: repeat initialization
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_repeat_init_then_save(repo, tmp_path):
    kr, _, _ = repo
    await kr.save(_knw(title="重复初始化测试"))

    # 再次 init（幂等）后仍可正常工作
    import sqlite3 as _sync_sqlite3
    sync_conn = _sync_sqlite3.connect(str(tmp_path / "test.db"))
    init_db_on_connection(sync_conn)
    sync_conn.close()

    results = await kr.search_fts("重复初始化", 10)
    assert len(results) == 1


# ═══════════════════════════════════════════════════════
# Group 7: search_by_title / update_status / save_vector
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_search_by_title_like(repo):
    kr, _, _ = repo
    await kr.save(_knw(id=_id("title1"), title="2026年4月家庭支出清单"))
    await kr.save(_knw(id=_id("title2"), title="2026年5月水电燃气清单"))

    results = await kr.search_by_title("4月", 10)
    assert len(results) == 1
    assert results[0].id == _id("title1")


@pytest.mark.asyncio
async def test_update_status(repo):
    kr, _, _ = repo
    item_id = _id("status")
    await kr.save(_knw(id=item_id, title="状态测试"))

    await kr.update_status(item_id, KnowledgeStatus.FORGOTTEN)

    fetched = await kr.get(item_id)
    assert fetched is not None
    assert fetched.status == KnowledgeStatus.FORGOTTEN


@pytest.mark.asyncio
async def test_list_active_only_returns_active(repo):
    kr, _, _ = repo
    await kr.save(_knw(id=_id("act1"), title="活动知识1"))
    await kr.save(_knw(id=_id("act2"), title="活动知识2"))
    await kr.save(
        _knw(id=_id("for1"), title="已遗忘知识", status=KnowledgeStatus.FORGOTTEN)
    )

    active = await kr.list_active()
    ids = {item.id for item in active}
    assert ids == {_id("act1"), _id("act2")}


@pytest.mark.asyncio
async def test_save_vector(repo):
    kr, _, _ = repo
    item_id = _id("vec")
    await kr.save(_knw(id=item_id, title="向量测试"))

    vec = bytes(range(256))
    await kr.save_vector(item_id, 256, vec)

    rows = await kr._db.execute_fetchall(
        "SELECT dim, vec FROM knowledge_vec WHERE knowledge_id = ?", (item_id,)
    )
    assert len(rows) == 1
    assert rows[0]["dim"] == 256
    assert rows[0]["vec"] == vec


# ═══════════════════════════════════════════════════════
# Group 8: search text extraction rule
# ═══════════════════════════════════════════════════════

def test_search_text_uses_description():
    from backend.foundation.storage.repository import _knowledge_search_text

    item = _knw(body={"description": "关键描述文本", "other": "x"})
    text = _knowledge_search_text(item)
    assert "关键描述文本" in text
    assert "other" not in text  # description 优先，其余字段不进索引


def test_search_text_falls_back_to_full_json():
    from backend.foundation.storage.repository import _knowledge_search_text

    item = _knw(body={"a": 1, "b": "hello"})
    text = _knowledge_search_text(item)
    assert "hello" in text  # 无 description 时整个 body 序列化
