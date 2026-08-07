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


MIGRATIONS: list[tuple[int, str, str | Callable[[sqlite3.Connection], None]]] = [
    (1, "initial_schema", _apply_initial_schema),
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
