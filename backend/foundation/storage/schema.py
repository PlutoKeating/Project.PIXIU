"""PIXIU Foundation — SQLite 数据库 Schema DDL

创建全部 19 张基础表及索引，启用 WAL + foreign_keys + busy_timeout。
知识向量表（knowledge_vec）留待 retrieval 阶段；knowledge_fts 由
SqliteKnowledgeRepo 惰性创建（见 ensure_knowledge_fts）。
"""

from __future__ import annotations

import os
import sqlite3

SCHEMA_VERSION = 9

# monitor_config 配置 KV 表（监视服务配置，单行 key="main"）。
# 独立常量供 monitor/config_store.py 复用，避免 DDL 双份漂移。
MONITOR_CONFIG_DDL = """
CREATE TABLE IF NOT EXISTS monitor_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT '{}',
    updated_at INTEGER NOT NULL
)
"""

# monitor_log 活动日志表（监视捕获/状态变更事件；BE-3 写 + 分页查询）。
# 独立常量供 api/monitor_log.py 复用，避免 DDL 双份漂移。
MONITOR_LOG_DDL = """
CREATE TABLE IF NOT EXISTS monitor_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           INTEGER NOT NULL,
    source       TEXT NOT NULL,
    status       TEXT NOT NULL,
    summary      TEXT NOT NULL,
    evidence_id  TEXT,
    knowledge_id TEXT
)
"""
MONITOR_LOG_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS idx_monitor_log_ts ON monitor_log(ts)"
)

# FTS5 全文索引（trigram 分词器，支持中文子串检索）。
# 独立表（不绑定 content=），rowid 手动对应 knowledge_items.rowid，
# 由 SqliteKnowledgeRepo 在首次使用时创建。
FTS_DDL_STATEMENTS: list[str] = [
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
        title,
        body_text,
        tokenize='trigram'
    )
    """,
]

# 向量表（INT8 BLOB）。仅存储，不做 ANN 检索（检索在 retrieval/ 阶段实现）。
# 由 SqliteKnowledgeRepo.save_vector 惰性创建。
VEC_DDL_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS knowledge_vec (
        knowledge_id TEXT PRIMARY KEY,
        dim          INTEGER NOT NULL,
        vec          BLOB NOT NULL,
        FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE
    )
    """,
]

DDL_STATEMENTS: list[str] = [
    # ─── evidence (原始证据) ─────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS evidence (
        id            TEXT PRIMARY KEY,
        source_type   TEXT NOT NULL,
        raw           TEXT NOT NULL DEFAULT '{}',
        quality_score REAL NOT NULL DEFAULT 0.0,
        sensitivity   INTEGER NOT NULL DEFAULT 0,
        scope         TEXT NOT NULL DEFAULT '',
        created_at    INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_evidence_scope ON evidence(scope)",
    "CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence(source_type)",

    # ─── knowledge_items (结构化知识) ────────────────────
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

    # ─── Vector Engine int64 ↔ canonical knowledge ID ───
    """
    CREATE TABLE IF NOT EXISTS vector_id_map (
        knowledge_id TEXT PRIMARY KEY,
        vector_id    INTEGER NOT NULL UNIQUE
    )
    """,

    # ─── knowledge_evidence (知识-证据关联) ───────────────
    """
    CREATE TABLE IF NOT EXISTS knowledge_evidence (
        knowledge_id TEXT NOT NULL,
        evidence_id  TEXT NOT NULL,
        PRIMARY KEY (knowledge_id, evidence_id),
        FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
        FOREIGN KEY (evidence_id)  REFERENCES evidence(id)       ON DELETE CASCADE
    )
    """,

    # ─── preferences (偏好记忆) ──────────────────────────
    """
    CREATE TABLE IF NOT EXISTS preferences (
        id          TEXT PRIMARY KEY,
        category    TEXT NOT NULL,
        key         TEXT NOT NULL,
        value       TEXT NOT NULL DEFAULT '{}',
        confidence  REAL NOT NULL DEFAULT 0.0,
        version     INTEGER NOT NULL DEFAULT 1,
        scope       TEXT NOT NULL DEFAULT '',
        created_at  INTEGER NOT NULL,
        updated_at  INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pref_category ON preferences(category)",
    "CREATE INDEX IF NOT EXISTS idx_pref_scope ON preferences(scope)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_pref_key_scope ON preferences(key, scope)",

    # ─── preference_history (偏好版本快照) ───────────────
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

    # ─── entities (命名实体) ─────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS entities (
        id        TEXT PRIMARY KEY,
        name      TEXT NOT NULL,
        norm_name TEXT NOT NULL,
        type      TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_norm ON entities(norm_name)",

    # ─── relations (实体关系) ────────────────────────────
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

    # ─── knowledge_entities (知识-实体关联) ───────────────
    """
    CREATE TABLE IF NOT EXISTS knowledge_entities (
        knowledge_id TEXT NOT NULL,
        entity_id    TEXT NOT NULL,
        PRIMARY KEY (knowledge_id, entity_id),
        FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
        FOREIGN KEY (entity_id)    REFERENCES entities(id)        ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_knw_entity_entity ON knowledge_entities(entity_id)",

    # ─── memory_contexts (短/中期记忆上下文) ─────────────
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_ctx_scope_tier ON memory_contexts(scope, tier)",
    "CREATE INDEX IF NOT EXISTS idx_ctx_expiry ON memory_contexts(status, expires_at)",

    # ─── conflict_records (冲突审计) ─────────────────────
    """
    CREATE TABLE IF NOT EXISTS conflict_records (
        id                TEXT PRIMARY KEY,
        target_knowledge  TEXT NOT NULL,
        field             TEXT NOT NULL DEFAULT '',
        old_value         TEXT NOT NULL DEFAULT 'null',
        new_value         TEXT NOT NULL DEFAULT 'null',
        resolution        TEXT NOT NULL DEFAULT 'NEW_WINS',
        created_at        INTEGER NOT NULL,
        source            TEXT NOT NULL DEFAULT 'write',
        severity          TEXT NOT NULL DEFAULT 'high'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_cfl_knw ON conflict_records(target_knowledge)",

    # ─── sync_oplog (CRDT 同步日志) ──────────────────────
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

    # ─── sync_identity (本机 Ed25519 身份，私钥加密存储) ─
    """
    CREATE TABLE IF NOT EXISTS sync_identity (
        singleton            INTEGER PRIMARY KEY CHECK (singleton = 1),
        device_id            TEXT NOT NULL UNIQUE,
        name                 TEXT NOT NULL,
        domain               TEXT NOT NULL,
        encrypted_private_key BLOB NOT NULL,
        public_key           BLOB NOT NULL,
        created_at           INTEGER NOT NULL
    )
    """,

    # ─── sync_peers (已配对设备) ─────────────────────────
    """
    CREATE TABLE IF NOT EXISTS sync_peers (
        id               TEXT PRIMARY KEY,
        name             TEXT NOT NULL,
        domain           TEXT NOT NULL,
        public_key       BLOB NOT NULL,
        status           TEXT NOT NULL DEFAULT 'OFFLINE'
                         CHECK (status IN ('ONLINE', 'OFFLINE', 'REVOKED')),
        paired_at        INTEGER NOT NULL,
        last_seen_ts     INTEGER,
        last_sync_ts     INTEGER,
        total_ops_synced INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sync_peer_domain ON sync_peers(domain, status)",

    # ─── sync_state (LWW-Element-Set 物化状态) ───────────
    """
    CREATE TABLE IF NOT EXISTS sync_state (
        entity    TEXT PRIMARY KEY,
        payload   TEXT NOT NULL DEFAULT '{}',
        vclock    TEXT NOT NULL DEFAULT '{}',
        ts        INTEGER NOT NULL,
        op_id     TEXT NOT NULL,
        tombstone INTEGER NOT NULL DEFAULT 0 CHECK (tombstone IN (0, 1)),
        FOREIGN KEY (op_id) REFERENCES sync_oplog(op_id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sync_state_tombstone ON sync_state(tombstone, ts)",

    # ─── sync_peer_acks (按 peer 的 op 确认) ──────────────
    """
    CREATE TABLE IF NOT EXISTS sync_peer_acks (
        peer_id  TEXT NOT NULL,
        op_id    TEXT NOT NULL,
        acked_at INTEGER NOT NULL,
        PRIMARY KEY (peer_id, op_id),
        FOREIGN KEY (peer_id) REFERENCES sync_peers(id) ON DELETE CASCADE,
        FOREIGN KEY (op_id) REFERENCES sync_oplog(op_id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sync_ack_op ON sync_peer_acks(op_id)",

    # ─── sync_meta (反熵/调度游标) ───────────────────────
    """
    CREATE TABLE IF NOT EXISTS sync_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,

    # ─── monitor_config (监视服务配置 KV) ─────────────────
    MONITOR_CONFIG_DDL,

    # ─── monitor_log (监视活动日志) ────────────────────────
    MONITOR_LOG_DDL,
    MONITOR_LOG_INDEX_DDL,
]


def create_connection(path: str) -> sqlite3.Connection:
    """创建 SQLite 连接并应用 PIXIU 标准 pragmas。

    - journal_mode=WAL  并发读写不互锁
    - foreign_keys=ON   外键约束生效
    - busy_timeout=5000 写入锁等待最多 5 秒
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(path: str) -> None:
    """创建/初始化数据库（幂等）。

    已存在的表不会被重建。
    """
    conn = create_connection(path)
    try:
        for stmt in DDL_STATEMENTS:
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()


def init_db_on_connection(conn: sqlite3.Connection) -> None:
    """在已有连接上初始化 schema（测试/迁移场景）。"""
    for stmt in DDL_STATEMENTS:
        conn.execute(stmt)
    conn.commit()


def ensure_knowledge_fts(conn: sqlite3.Connection) -> None:
    """在已有连接上创建 knowledge_fts（幂等，供仓储惰性调用）。"""
    for stmt in FTS_DDL_STATEMENTS:
        conn.execute(stmt)
    conn.commit()


def ensure_knowledge_vec(conn: sqlite3.Connection) -> None:
    """在已有连接上创建 knowledge_vec（幂等，供仓储惰性调用）。"""
    for stmt in VEC_DDL_STATEMENTS:
        conn.execute(stmt)
    conn.commit()
