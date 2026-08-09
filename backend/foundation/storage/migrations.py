"""PIXIU Foundation — 数据库迁移骨架

提供版本表、版本号管理和迁移注册机制。
每个迁移用 (version, description, sql_up) 元组注册，按序执行。
"""

from __future__ import annotations

import sqlite3
from typing import Callable


def _apply_initial_schema(conn: sqlite3.Connection) -> None:
    """迁移 #1：建立全部基础表。"""
    from .schema import DDL_STATEMENTS

    for stmt in DDL_STATEMENTS:
        conn.execute(stmt)


def _add_knowledge_entities(conn: sqlite3.Connection) -> None:
    """迁移 #2：持久化知识与实体的多对多关联。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_entities (
            knowledge_id TEXT NOT NULL,
            entity_id    TEXT NOT NULL,
            PRIMARY KEY (knowledge_id, entity_id),
            FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
            FOREIGN KEY (entity_id)    REFERENCES entities(id)        ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_knw_entity_entity "
        "ON knowledge_entities(entity_id)"
    )


def _add_memory_contexts(conn: sqlite3.Connection) -> None:
    """迁移 #3：持久化短/中期记忆及其 TTL/沉淀状态。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_contexts (
            id           TEXT PRIMARY KEY,
            tier         TEXT NOT NULL CHECK (tier IN ('SHORT_TERM', 'MID_TERM')),
            payload      TEXT NOT NULL DEFAULT '{}',
            scope        TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'ACTIVE'
                         CHECK (status IN ('ACTIVE', 'PROMOTED', 'EXPIRED')),
            created_at   INTEGER NOT NULL,
            updated_at   INTEGER NOT NULL,
            expires_at   INTEGER,
            knowledge_id TEXT,
            FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ctx_scope_tier "
        "ON memory_contexts(scope, tier)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ctx_expiry "
        "ON memory_contexts(status, expires_at)"
    )


MIGRATIONS: list[tuple[int, str, str | Callable[[sqlite3.Connection], None]]] = [
    (1, "initial_schema", _apply_initial_schema),
    (2, "knowledge_entity_links", _add_knowledge_entities),
    (3, "memory_contexts", _add_memory_contexts),
]


def _create_version_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _schema_version (
            version   INTEGER PRIMARY KEY,
            applied_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
        )
    """)


def _current_version(conn: sqlite3.Connection) -> int:
    """返回当前数据库已应用的版本号（未初始化返回 0）。"""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='_schema_version'"
    )
    if not cursor.fetchone():
        return 0
    cursor = conn.execute("SELECT COALESCE(MAX(version), 0) FROM _schema_version")
    row = cursor.fetchone()
    return row[0] if row else 0


def apply_pending(conn: sqlite3.Connection) -> int:
    """按序执行未应用的迁移，返回本次应用的版本数。

    调用方负责 commit 和关闭连接。
    """
    import time

    _create_version_table(conn)
    current = _current_version(conn)
    applied = 0

    for version, description, action in MIGRATIONS:
        if version <= current:
            continue
        if callable(action):
            action(conn)
        else:
            conn.executescript(action)
        conn.execute(
            "INSERT INTO _schema_version (version, applied_at) VALUES (?, ?)",
            (version, int(time.time())),
        )
        applied += 1

    return applied


def latest_version() -> int:
    """返回代码定义的最新迁移版本号。"""
    if not MIGRATIONS:
        return 0
    return max(v for v, _, _ in MIGRATIONS)
