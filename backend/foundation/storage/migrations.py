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


def _add_sync_foundation(conn: sqlite3.Connection) -> None:
    """迁移 #4：加密设备身份、peer、CRDT 状态、ACK 与同步元数据。"""
    statements = [
        """CREATE TABLE IF NOT EXISTS sync_identity (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            device_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL, domain TEXT NOT NULL,
            encrypted_private_key BLOB NOT NULL, public_key BLOB NOT NULL,
            created_at INTEGER NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS sync_peers (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, domain TEXT NOT NULL,
            public_key BLOB NOT NULL,
            status TEXT NOT NULL DEFAULT 'OFFLINE'
                   CHECK (status IN ('ONLINE', 'OFFLINE', 'REVOKED')),
            paired_at INTEGER NOT NULL, last_seen_ts INTEGER, last_sync_ts INTEGER,
            total_ops_synced INTEGER NOT NULL DEFAULT 0
        )""",
        "CREATE INDEX IF NOT EXISTS idx_sync_peer_domain ON sync_peers(domain, status)",
        """CREATE TABLE IF NOT EXISTS sync_state (
            entity TEXT PRIMARY KEY, payload TEXT NOT NULL DEFAULT '{}',
            vclock TEXT NOT NULL DEFAULT '{}', ts INTEGER NOT NULL, op_id TEXT NOT NULL,
            tombstone INTEGER NOT NULL DEFAULT 0 CHECK (tombstone IN (0, 1)),
            FOREIGN KEY (op_id) REFERENCES sync_oplog(op_id) ON DELETE CASCADE
        )""",
        "CREATE INDEX IF NOT EXISTS idx_sync_state_tombstone ON sync_state(tombstone, ts)",
        """CREATE TABLE IF NOT EXISTS sync_peer_acks (
            peer_id TEXT NOT NULL, op_id TEXT NOT NULL, acked_at INTEGER NOT NULL,
            PRIMARY KEY (peer_id, op_id),
            FOREIGN KEY (peer_id) REFERENCES sync_peers(id) ON DELETE CASCADE,
            FOREIGN KEY (op_id) REFERENCES sync_oplog(op_id) ON DELETE CASCADE
        )""",
        "CREATE INDEX IF NOT EXISTS idx_sync_ack_op ON sync_peer_acks(op_id)",
        "CREATE TABLE IF NOT EXISTS sync_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    ]
    for statement in statements:
        conn.execute(statement)


def _add_monitor_config(conn: sqlite3.Connection) -> None:
    """迁移 #5：监视服务配置 KV 表（MonitorConfigStore 持久化）。"""
    from .schema import MONITOR_CONFIG_DDL

    conn.execute(MONITOR_CONFIG_DDL)


def _add_monitor_log(conn: sqlite3.Connection) -> None:
    """迁移 #6：监视活动日志表（monitor_log，BE-3 写 + 分页查询）。"""
    from .schema import MONITOR_LOG_DDL, MONITOR_LOG_INDEX_DDL

    conn.execute(MONITOR_LOG_DDL)
    conn.execute(MONITOR_LOG_INDEX_DDL)


def _add_conflict_source(conn: sqlite3.Connection) -> None:
    """迁移 #7：conflict_records.source —— 区分同步分叉（sync）与本地写入（write）。

    SN-3 mainline 转人工仲裁时生成的 ConflictRecord 带 source="sync"。
    新库由初始 DDL 直接建出该列；旧库（<= v6）此处补列。幂等守卫：
    - 表不存在（v1 精简库等场景）→ 跳过，由完整初始 DDL 兜底；
    - 列已存在（新库）→ 跳过，避免 duplicate column。
    """
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "conflict_records" not in tables:
        return
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(conflict_records)").fetchall()
    }
    if "source" not in columns:
        conn.execute(
            "ALTER TABLE conflict_records "
            "ADD COLUMN source TEXT NOT NULL DEFAULT 'write'"
        )


def _add_conflict_severity(conn: sqlite3.Connection) -> None:
    """迁移 #8：conflict_records.severity —— 冲突打扰分级（B3-3 S3.1）。

    MERGE→low / NEW_WINS→medium / MANUAL→high。新库由初始 DDL 直接建出该列；
    旧库（<= v7）此处补列，SQL 默认 'high'（最保守兜底；回读时按 resolution
    派生修正，见 repository._row_to_conflict 的说明）。幂等守卫同 #7：
    - 表不存在（v1 精简库等场景）→ 跳过，由完整初始 DDL 兜底；
    - 列已存在（新库）→ 跳过，避免 duplicate column。
    """
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "conflict_records" not in tables:
        return
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(conflict_records)").fetchall()
    }
    if "severity" not in columns:
        conn.execute(
            "ALTER TABLE conflict_records "
            "ADD COLUMN severity TEXT NOT NULL DEFAULT 'high'"
        )


def _add_vector_id_map(conn: sqlite3.Connection) -> None:
    """迁移 #9：持久化 Vector Engine int64 与知识字符串 ID 的双向映射。"""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS vector_id_map (
            knowledge_id TEXT PRIMARY KEY,
            vector_id    INTEGER NOT NULL UNIQUE
        )"""
    )


def _add_agent_provenance(conn: sqlite3.Connection) -> None:
    """Migration #10: persist session/run/turn/tool provenance on evidence."""
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "evidence" not in tables:
        return
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(evidence)").fetchall()
    }
    if "provenance" not in columns:
        conn.execute(
            "ALTER TABLE evidence "
            "ADD COLUMN provenance TEXT NOT NULL DEFAULT '{}'"
        )


MIGRATIONS: list[tuple[int, str, str | Callable[[sqlite3.Connection], None]]] = [
    (1, "initial_schema", _apply_initial_schema),
    (2, "knowledge_entity_links", _add_knowledge_entities),
    (3, "memory_contexts", _add_memory_contexts),
    (4, "sync_foundation", _add_sync_foundation),
    (5, "monitor_config", _add_monitor_config),
    (6, "monitor_log", _add_monitor_log),
    (7, "conflict_source", _add_conflict_source),
    (8, "conflict_severity", _add_conflict_severity),
    (9, "vector_id_map", _add_vector_id_map),
    (10, "agent_provenance", _add_agent_provenance),
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
