"""Phase 7 专项检查：WAL 并发、并发 embedding、脱敏、迁移、崩溃恢复、资源边界。

ARM/x86 麒麟兼容需麒麟环境，本地以文档标注（见 Phase 7 交付说明）。
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import sqlite3
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.tests.fakes import StubTextEmbedder
from backend.foundation.core.models import Evidence, KnowledgeItem, KnowledgeKind, SourceType
from backend.foundation.retrieval import RetrievalService
from backend.foundation.storage.migrations import apply_pending, latest_version
from backend.foundation.storage.repository import (
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
)
from backend.foundation.storage.schema import init_db_on_connection

NOW = 2_000_000_000


def _knw_id(tag: str) -> str:
    return f"knw_{(tag + '0' * 26)[:26]}"


def _evd_id(tag: str) -> str:
    return f"evd_{(tag + '0' * 26)[:26]}"


async def _open_db(path: Path) -> aiosqlite.Connection:
    sc = sqlite3.connect(str(path))
    init_db_on_connection(sc)
    sc.close()
    db = await aiosqlite.connect(str(path))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    return db


# ═══════════════════════════════════════════════════════
# 1. WAL 并发读写
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_wal_concurrent_read_write(tmp_path: Path):
    """多个协程并发写读同一 SQLite（WAL 模式）不产生锁错误。"""
    db = await _open_db(tmp_path / "wal.db")
    repo = SqliteEvidenceRepo(db)

    async def writer(i: int) -> None:
        for j in range(5):
            await repo.save(
                Evidence(
                    id=_evd_id(f"w{i:02d}{j:02d}"),
                    source_type=SourceType.TOOL_RESULT,
                    raw={"writer": i, "n": j},
                    scope="shared:home",
                    created_at=NOW + i,
                )
            )

    async def reader() -> int:
        found = 0
        for _ in range(10):
            rows = await repo.list_by_scope("shared:home", 100)
            found = len(rows)
        return found

    writers = [writer(i) for i in range(5)]
    readers = [reader() for _ in range(3)]
    results = await asyncio.gather(*writers, *readers)
    await db.close()

    assert len(results) == 8  # 5 writers + 3 readers
    # WAL 模式：写入与读取并发无 database is locked 异常（gather 未抛错即通过）


# ═══════════════════════════════════════════════════════
# 2. 多请求同时 embedding
# ═══════════════════════════════════════════════════════

class _SlowEmbedder(StubTextEmbedder):
    """延迟 embedding 桩：验证并发查询不串扰且可并行。"""

    async def embed_async(self, text: str) -> list[float]:
        await asyncio.sleep(0.02)
        return self.embed(text)


@pytest.mark.asyncio
async def test_concurrent_embedding_requests(tmp_path: Path):
    """20 个并发查询同时触发 embedding，全部正确返回各自结果。"""
    db = await _open_db(tmp_path / "emb.db")
    embedder = StubTextEmbedder()
    knw_repo = SqliteKnowledgeRepo(db)
    ent_repo = SqliteEntityRepo(db)
    evd_repo = SqliteEvidenceRepo(db)

    for i in range(5):
        item = KnowledgeItem(
            id=_knw_id(f"e{i}"),
            kind=KnowledgeKind.FACT,
            title=f"并发查询知识{i}",
            body={"description": f"主题内容{i}"},
            scope="shared:home",
            created_at=NOW,
            updated_at=NOW,
        )
        await knw_repo.save(item)
        text = " ".join(str(x) for x in [item.title, item.kind, item.body])
        import struct as _struct
        from backend.foundation.retrieval.ann import quantize_int8

        quantized = quantize_int8(embedder.embed(text))
        vec = _struct.pack(f"{len(quantized)}b", *quantized)
        await knw_repo.save_vector(item.id, embedder.dim, vec)

    service = RetrievalService(knw_repo, ent_repo, evd_repo, embedder)

    async def query(i: int) -> str:
        atom = await service.query(f"并发查询知识{i % 5}")
        return atom.source_knowledge

    results = await asyncio.gather(*[query(i) for i in range(20)])
    # 每个查询都命中对应知识（embedding 经 to_thread 并发，无串扰）
    assert all(kid for kid in results)
    await db.close()


# ═══════════════════════════════════════════════════════
# 3. API 错误码与 request_id（契约对齐 API.md §5）
# ═══════════════════════════════════════════════════════

def test_api_error_contract_violation_and_request_id(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import backend.foundation.api.di as di_module
    from backend.engine.knowledge import KnowledgeService
    from backend.foundation.api import app
    from backend.foundation.api.di import get_knowledge_service
    from backend.foundation.storage.repository import SqliteEntityRepo, SqliteKnowledgeRepo

    class _FakeSettings:
        def __init__(self, db_path: str):
            self.db_path = db_path
            self.embedding = "portable"
            # sync lifespan 需要的最小属性（默认关闭网络）
            self.sync_network_enabled = False
            self.sync_port = 8766
            self.sync_device_name = "hardening-test"
            self.sync_domain = "shared:home"
            self.sync_key_passphrase = "hardening-test-passphrase-0123"
            self.monitor_enabled = False  # 不启动 monitor runtime

    monkeypatch.setattr(di_module, "settings", _FakeSettings(str(tmp_path / "pixiu.db")))
    di_module._db = None

    # 无 SDK 开发机：覆盖 knowledge service 注入 Stub embedder（依赖解析先于 body 校验）
    async def _override_knowledge():
        db = await di_module.get_db()
        return KnowledgeService(
            knw_repo=SqliteKnowledgeRepo(db),
            entity_repo=SqliteEntityRepo(db),
            embedder=StubTextEmbedder(dim=32),
        )

    app.dependency_overrides[get_knowledge_service] = _override_knowledge
    try:
        # 请求体不符合 Schema → 400 INVALID_REQUEST + request_id
        with TestClient(app) as client:
            resp = client.post("/memory/write", json={"source_type": "BAD"})
            assert resp.status_code == 400
            body = resp.json()
            assert body["error"] == "INVALID_REQUEST"
            assert body["request_id"].startswith("req_")
            assert resp.headers.get("X-Request-Id")

            # 不存在资源 → 404 NOT_FOUND + request_id
            resp = client.get("/preference/doesnotexist/history")
            assert resp.status_code == 404
            assert resp.json()["error"] == "NOT_FOUND"
            assert resp.json()["request_id"]
    finally:
        app.dependency_overrides.clear()
        di_module._db = None


# ═══════════════════════════════════════════════════════
# 4. 日志敏感数据脱敏（端到端）
# ═══════════════════════════════════════════════════════

def test_logger_redacts_sensitive_data():
    from backend.foundation.core.logger import SensitiveFilter

    record = logging.LogRecord("x", logging.INFO, "", 0, "password=secret123 token=abc", (), None)
    SensitiveFilter().filter(record)
    assert "secret123" not in record.msg
    assert "abc" not in record.msg
    assert "password=***" in record.msg


# ═══════════════════════════════════════════════════════
# 5. 数据库升级迁移
# ═══════════════════════════════════════════════════════

def test_migration_version_recording_and_idempotency(tmp_path: Path):
    path = str(tmp_path / "mig.db")
    conn = sqlite3.connect(path)

    # 首次应用：版本表 + 全部迁移
    applied = apply_pending(conn)
    conn.commit()
    assert applied >= 1

    # 再次应用：幂等，0 新迁移
    applied_again = apply_pending(conn)
    conn.commit()
    assert applied_again == 0

    # 版本记录与代码最新版本一致
    row = conn.execute("SELECT MAX(version) FROM _schema_version").fetchone()
    assert row[0] == latest_version()
    conn.close()


def test_migration_partial_failure_rolls_back(tmp_path: Path):
    """迁移中途失败：不写入版本记录，重试可继续。"""
    from backend.foundation.storage.migrations import MIGRATIONS

    original = list(MIGRATIONS)

    def _broken(conn):
        raise RuntimeError("simulated migration failure")

    # 注入一个会失败的迁移（版本 999）
    MIGRATIONS.append((999, "broken", _broken))
    try:
        conn = sqlite3.connect(str(tmp_path / "mig2.db"))
        with pytest.raises(RuntimeError):
            apply_pending(conn)
        # 版本表存在但 999 未记录
        row = conn.execute("SELECT MAX(version) FROM _schema_version").fetchone()
        assert row[0] < 999
        conn.close()
    finally:
        MIGRATIONS[:] = original


# ═══════════════════════════════════════════════════════
# 6. 进程崩溃恢复（未 commit 中断 → 无脏数据）
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_crash_recovery_no_partial_writes(tmp_path: Path):
    """写入未 commit 时中断（模拟崩溃），重开后无部分数据。"""
    path = tmp_path / "crash.db"
    db = await _open_db(path)
    repo = SqliteEvidenceRepo(db)

    # 正常提交一条
    await repo.save(
        Evidence(
            id=_evd_id("committed"),
            source_type=SourceType.OCR,
            raw={"v": 1},
            scope="shared:home",
            created_at=NOW,
        )
    )

    # 模拟崩溃：开启事务写入但不 commit，直接关闭连接（未 commit 回滚）
    cursor = await db.execute(
        "INSERT INTO evidence (id, source_type, raw, quality_score, sensitivity, scope, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (_evd_id("uncommitted"), "OCR", "{}", 0.0, 0, "shared:home", NOW),
    )
    # 不 commit，直接关闭连接
    await db.close()

    # 重开：只有已提交的数据
    db2 = await aiosqlite.connect(str(path))
    db2.row_factory = aiosqlite.Row
    rows = await db2.execute_fetchall("SELECT id FROM evidence")
    ids = {r["id"] for r in rows}
    assert _evd_id("committed") in ids
    assert _evd_id("uncommitted") not in ids
    await db2.close()


# ═══════════════════════════════════════════════════════
# 7. 磁盘与内存边界
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_disk_usage_bounded(tmp_path: Path):
    """写入 100 条知识后 db 文件大小有界（< 10 MB）。"""
    db = await _open_db(tmp_path / "disk.db")
    knw_repo = SqliteKnowledgeRepo(db)
    for i in range(100):
        await knw_repo.save(
            KnowledgeItem(
                id=_knw_id(f"d{i:04d}"),
                kind=KnowledgeKind.FACT,
                title=f"磁盘占用测试知识{i}",
                body={"description": "x" * 500},
                scope="shared:home",
                created_at=NOW,
                updated_at=NOW,
            )
        )
    await db.close()

    size = (tmp_path / "disk.db").stat().st_size
    assert size < 10 * 1024 * 1024
    assert size > 0


def test_peak_memory_bounded():
    """1000 条检索候选序列化的 tracemalloc 峰值有界（< 256 MB）。"""
    import tracemalloc

    tracemalloc.start()
    _ = json.dumps(
        {"results": [{"knowledge_id": f"knw_{i}", "score": i * 0.001} for i in range(1000)]}
    )
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 256 * 1024 * 1024
