"""PIXIU Foundation — 依赖注入骨架

本文件是模块 C api/ 层对引擎 Service 的唯一 import 点。
当前引擎包未实现，使用工厂函数返回占位对象。

后续引擎开发完成后，取消注释 import 并替换工厂函数返回体。
"""

from __future__ import annotations

import aiosqlite

from ..core.config import settings
from ..core.logger import get_logger

_log = get_logger(__name__)

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    """获取 aiosqlite 数据库连接（惰性初始化）。

    数据库路径由 PIXIU_DB_PATH 环境变量控制，默认 ./pixiu.db。
    """
    global _db
    if _db is None:
        _db = await aiosqlite.connect(settings.db_path)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
        _log.info("Database connected: %s", db_path)
    return _db


# ─── Service 工厂（当前返回占位对象）───────────────────────
#
# 后续引擎实现后，取消注释并按以下模式注入：
#
#   from backend.engine.ingest import IngestionService
#   from backend.foundation.storage.repository import SqliteEvidenceRepo
#
#   async def get_ingestion_service(db=Depends(get_db)):
#       return IngestionService(evidence_repo=SqliteEvidenceRepo(db))
#

class _Placeholder:
    """占位对象，属性访问始终返回自身。"""

    def __getattr__(self, _name: str):
        return self

    def __call__(self, *args, **kwargs):
        return self


async def get_ingestion_service():
    return _Placeholder()


async def get_preference_service():
    return _Placeholder()


async def get_knowledge_service():
    return _Placeholder()


async def get_conflict_service():
    return _Placeholder()


async def get_security_service():
    return _Placeholder()
