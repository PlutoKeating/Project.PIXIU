"""PIXIU Foundation — SQLite 数据库 Schema DDL

创建全部 12 张表及索引，WAL 模式开启。
"""

from __future__ import annotations

import os

SCHEMA_VERSION = 1

DDL_STATEMENTS: list[str] = [
    # ─── 证据 ──────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS evidence (
        id          TEXT PRIMARY KEY,
        source_type TEXT NOT NULL,
        raw         TEXT NOT NULL DEFAULT '{}',
        quality_score REAL NOT NULL DEFAULT 0.0,
        sensitivity  INTEGER NOT NULL DEFAULT 0,
        scope       TEXT NOT NULL DEFAULT '',
        created_at  INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_evidence_scope ON evidence(scope)",
    "CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence(source_type)",
    # ─── 知识条目 ──────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS knowledge_items (
        id           TEXT PRIMARY KEY,
        kind         TEXT NOT NULL,
        title        TEXT NOT NULL DEFAULT '',
        body         TEXT NOT NULL DEFAULT '{}',
        status       TEXT NOT NULL DEFAULT 'ACTIVE',
        version      INTEGER NOT NULL DEFAULT 1,
        scope        TEXT NOT NULL DEFAULT '',
        created_at   INTEGER NOT NULL,
        updated_at   INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_knw_status ON knowledge_items(status)",
    "CREATE INDEX IF NOT EXISTS idx_knw_scope ON knowledge_items(scope)",
    # ─── 知识-证据关联表 ────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS knowledge_evidence (
        knowledge_id TEXT NOT NULL,
        evidence_id  TEXT NOT NULL,
        PRIMARY KEY (knowledge_id, evidence_id),
        FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
        FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE
    )
    """,
    # ─── FTS5 全文索引 ─────────────────────────────────
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
        title,
        body_text,
        content='knowledge_items',
        content_rowid='rowid'
    )
    """,
    # ─── 向量索引 (INT8) ───────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS knowledge_vec (
        knowledge_id TEXT PRIMARY KEY,
        dim          INTEGER NOT NULL,
        vec          BLOB NOT NULL,
        FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE
    )
    """,
    # ─── 实体 ──────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS entities (
        id        TEXT PRIMARY KEY,
        name      TEXT NOT NULL,
        norm_name TEXT NOT NULL,
        type      TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_norm ON entities(norm_name)",
    # ─── 关系 ──────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS relations (
        src  TEXT NOT NULL,
        dst  TEXT NOT NULL,
        type TEXT NOT NULL,
        PRIMARY KEY (src, dst, type),
        FOREIGN KEY (src) REFERENCES entities(id) ON DELETE CASCADE,
        FOREIGN KEY (dst) REFERENCES entities(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_rel_src ON relations(src)",
    "CREATE INDEX IF NOT EXISTS idx_rel_dst ON relations(dst)",
    # ─── 偏好 ──────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS preferences (
        id         TEXT PRIMARY KEY,
        category   TEXT NOT NULL,
        key        TEXT NOT NULL,
        value      TEXT NOT NULL DEFAULT '{}',
        confidence REAL NOT NULL DEFAULT 0.0,
        version    INTEGER NOT NULL DEFAULT 1,
        scope      TEXT NOT NULL DEFAULT '',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pref_category ON preferences(category)",
    "CREATE INDEX IF NOT EXISTS idx_pref_scope ON preferences(scope)",
    # ─── 偏好历史版本 ──────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS preference_history (
        pref_id   TEXT NOT NULL,
        version   INTEGER NOT NULL,
        snapshot  TEXT NOT NULL DEFAULT '{}',
        ts        INTEGER NOT NULL,
        PRIMARY KEY (pref_id, version),
        FOREIGN KEY (pref_id) REFERENCES preferences(id) ON DELETE CASCADE
    )
    """,
    # ─── 冲突审计 ──────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS conflict_records (
        id                TEXT PRIMARY KEY,
        target_knowledge  TEXT NOT NULL,
        old_value         TEXT NOT NULL DEFAULT 'null',
        new_value         TEXT NOT NULL DEFAULT 'null',
        resolution        TEXT NOT NULL DEFAULT 'NEW_WINS',
        created_at        INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_cfl_knw ON conflict_records(target_knowledge)",
    # ─── CRDT 同步日志 ─────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS sync_oplog (
        op_id    TEXT PRIMARY KEY,
        entity   TEXT NOT NULL,
        payload  TEXT NOT NULL DEFAULT '{}',
        vclock   TEXT NOT NULL DEFAULT '{}',
        ts       INTEGER NOT NULL,
        synced   INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sync_ts ON sync_oplog(ts)",
    "CREATE INDEX IF NOT EXISTS idx_sync_synced ON sync_oplog(synced)",
]


def init_db(path: str) -> None:
    """创建/初始化 SQLite 数据库（WAL 模式）。

    幂等：已存在的表不会被重建。
    """
    import sqlite3

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    for stmt in DDL_STATEMENTS:
        conn.execute(stmt)

    conn.commit()
    conn.close()
