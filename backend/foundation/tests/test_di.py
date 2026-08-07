"""Tests for api/di.py — 依赖注入与数据库初始化。"""

from __future__ import annotations

import pytest

import backend.foundation.api.di as di_module
from backend.engine.conflict import ConflictService
from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.preference import PreferenceService
from backend.engine.security import SecurityService
from backend.foundation.api.di import (
    get_conflict_repo,
    get_conflict_service,
    get_db,
    get_evidence_repo,
    get_ingestion_service,
    get_knowledge_service,
    get_preference_repo,
    get_preference_service,
    get_security_service,
)
from backend.foundation.storage.repository import (
    SqliteConflictRepo,
    SqliteEvidenceRepo,
    SqlitePreferenceRepo,
)


class _FakeSettings:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path


@pytest.fixture()
def fresh_di(tmp_path, monkeypatch):
    """替换 settings.db_path 并重置 get_db 单例。"""
    monkeypatch.setattr(di_module, "settings", _FakeSettings(str(tmp_path / "pixiu.db")))
    di_module._db = None
    yield
    di_module._db = None


@pytest.mark.asyncio
async def test_get_db_runs_migrations(fresh_di, tmp_path):
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence'"
        )
        assert len(rows) == 1
        version_rows = await db.execute_fetchall(
            "SELECT MAX(version) FROM _schema_version"
        )
        assert version_rows[0][0] == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_service_factories_return_real_services(fresh_di):
    db = await get_db()
    try:
        assert isinstance(await get_ingestion_service(db), IngestionService)
        assert isinstance(await get_preference_service(db), PreferenceService)
        assert isinstance(await get_knowledge_service(db), KnowledgeService)
        assert isinstance(await get_conflict_service(db), ConflictService)
        assert isinstance(await get_security_service(db), SecurityService)
        assert isinstance(await get_evidence_repo(db), SqliteEvidenceRepo)
        assert isinstance(await get_preference_repo(db), SqlitePreferenceRepo)
        assert isinstance(await get_conflict_repo(db), SqliteConflictRepo)
    finally:
        await db.close()
