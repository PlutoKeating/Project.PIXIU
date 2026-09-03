"""Tests for storage/schema.py and storage/migrations.py."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.foundation.storage.schema import (
    SCHEMA_VERSION,
    DDL_STATEMENTS,
    create_connection,
    init_db,
    init_db_on_connection,
)
from backend.foundation.storage.migrations import (
    apply_pending,
    latest_version,
)

EXPECTED_TABLES = {
    "evidence",
    "knowledge_items",
    "knowledge_evidence",
    "preferences",
    "preference_history",
    "entities",
    "relations",
    "knowledge_entities",
    "memory_contexts",
    "conflict_records",
    "sync_oplog",
    "sync_identity",
    "sync_peers",
    "sync_state",
    "sync_peer_acks",
    "sync_meta",
    "monitor_config",
    "monitor_log",
    "vector_id_map",
}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return {r[0] for r in rows}


# ═══════════════════════════════════════════════════════
# Group 1: repeat initialization (idempotent)
# ═══════════════════════════════════════════════════════

def test_init_db_creates_all_tables(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    tables = _table_names(conn)
    conn.close()

    missing = EXPECTED_TABLES - tables
    # sqlite_sequence 是 AUTOINCREMENT（monitor_log.id）自动创建的 SQLite
    # 内部表，非应用表，不计入 extra。
    extra = tables - EXPECTED_TABLES - {"_schema_version", "sqlite_sequence"}
    assert not missing, f"missing tables: {missing}"
    assert not extra, f"unexpected tables: {extra}"


def test_init_db_is_idempotent(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    init_db(db_path)  # second call must not fail
    init_db(db_path)  # third call must not fail

    conn = sqlite3.connect(db_path)
    tables = _table_names(conn)
    conn.close()
    assert EXPECTED_TABLES.issubset(tables)


# ═══════════════════════════════════════════════════════
# Group 2: table existence and schema details
# ═══════════════════════════════════════════════════════

def test_evidence_has_expected_columns(tmp_path: Path):
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    init_db_on_connection(conn)
    cols = {
        r[1]
        for r in conn.execute("PRAGMA table_info('evidence')").fetchall()
    }
    assert cols == {"id", "source_type", "raw", "quality_score", "sensitivity", "scope", "created_at"}


def test_knowledge_items_has_expected_columns(tmp_path: Path):
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    init_db_on_connection(conn)
    cols = {
        r[1]
        for r in conn.execute("PRAGMA table_info('knowledge_items')").fetchall()
    }
    assert {"id", "kind", "title", "body", "status", "version", "scope", "created_at", "updated_at"}.issubset(cols)


def test_knowledge_evidence_fk_columns(tmp_path: Path):
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    init_db_on_connection(conn)
    fks = conn.execute("PRAGMA foreign_key_list('knowledge_evidence')").fetchall()
    targets = {r[2] for r in fks}
    assert "knowledge_items" in targets
    assert "evidence" in targets


def test_knowledge_entities_fk_columns(tmp_path: Path):
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    init_db_on_connection(conn)
    fks = conn.execute("PRAGMA foreign_key_list('knowledge_entities')").fetchall()
    targets = {row[2] for row in fks}
    assert targets == {"knowledge_items", "entities"}


def test_preferences_has_unique_key_scope(tmp_path: Path):
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    init_db_on_connection(conn)
    indexes = {
        r[1] for r in conn.execute("PRAGMA index_list('preferences')").fetchall()
    }
    assert "idx_pref_key_scope" in indexes


def test_memory_contexts_has_lifecycle_columns_and_fk(tmp_path: Path):
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    init_db_on_connection(conn)
    cols = {
        row[1] for row in conn.execute("PRAGMA table_info('memory_contexts')").fetchall()
    }
    assert {
        "id", "tier", "payload", "scope", "status", "created_at",
        "updated_at", "expires_at", "knowledge_id",
    } == cols
    fks = conn.execute("PRAGMA foreign_key_list('memory_contexts')").fetchall()
    assert {row[2] for row in fks} == {"knowledge_items"}
    conn.close()


def test_sync_foundation_tables_protect_identity_and_relations(tmp_path: Path):
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    init_db_on_connection(conn)
    identity_cols = {
        row[1] for row in conn.execute("PRAGMA table_info('sync_identity')").fetchall()
    }
    assert "encrypted_private_key" in identity_cols
    assert "private_key" not in identity_cols
    state_fks = conn.execute("PRAGMA foreign_key_list('sync_state')").fetchall()
    ack_fks = conn.execute("PRAGMA foreign_key_list('sync_peer_acks')").fetchall()
    assert {row[2] for row in state_fks} == {"sync_oplog"}
    assert {row[2] for row in ack_fks} == {"sync_peers", "sync_oplog"}
    conn.close()


# ═══════════════════════════════════════════════════════
# Group 3: foreign key enforcement
# ═══════════════════════════════════════════════════════

def test_fk_violation_rejected_knowledge_evidence(tmp_path: Path):
    conn = create_connection(str(tmp_path / "test.db"))
    init_db_on_connection(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO knowledge_evidence (knowledge_id, evidence_id) VALUES (?, ?)",
            ("nonexistent", "nope"),
        )
    conn.close()


def test_fk_violation_rejected_relations(tmp_path: Path):
    conn = create_connection(str(tmp_path / "test.db"))
    init_db_on_connection(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO relations (src, dst, type) VALUES (?, ?, ?)",
            ("no_src", "no_dst", "BELONG_TO"),
        )
    conn.close()


def test_fk_cascade_delete_works(tmp_path: Path):
    conn = create_connection(str(tmp_path / "test.db"))
    init_db_on_connection(conn)
    conn.execute(
        "INSERT INTO evidence (id, source_type, scope, created_at) VALUES (?, ?, ?, ?)",
        ("evd_a", "OCR", "user:alice", 1),
    )
    conn.execute(
        "INSERT INTO knowledge_items (id, kind, title, scope, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("knw_a", "FACT", "t", "user:alice", 1, 1),
    )
    conn.execute(
        "INSERT INTO knowledge_evidence (knowledge_id, evidence_id) VALUES (?, ?)",
        ("knw_a", "evd_a"),
    )
    # delete evidence → cascade deletes the association
    conn.execute("DELETE FROM evidence WHERE id = ?", ("evd_a",))
    rows = conn.execute(
        "SELECT * FROM knowledge_evidence WHERE evidence_id = ?", ("evd_a",)
    ).fetchall()
    assert len(rows) == 0
    conn.close()


# ═══════════════════════════════════════════════════════
# Group 4: WAL mode and pragmas
# ═══════════════════════════════════════════════════════

def test_wal_mode_active(tmp_path: Path):
    conn = create_connection(str(tmp_path / "test.db"))
    init_db_on_connection(conn)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode.upper() == "WAL"


def test_foreign_keys_enabled(tmp_path: Path):
    conn = create_connection(str(tmp_path / "test.db"))
    init_db_on_connection(conn)
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.close()
    assert fk == 1


def test_busy_timeout_set(tmp_path: Path):
    conn = create_connection(str(tmp_path / "test.db"))
    timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    conn.close()
    assert timeout == 5000


# ═══════════════════════════════════════════════════════
# Group 5: migration version recording
# ═══════════════════════════════════════════════════════

def test_apply_pending_creates_version_table(tmp_path: Path):
    conn = create_connection(str(tmp_path / "test.db"))
    count = apply_pending(conn)
    conn.commit()

    assert count >= 1
    tables = _table_names(conn)
    assert "_schema_version" in tables
    conn.close()


def test_apply_pending_is_idempotent(tmp_path: Path):
    conn = create_connection(str(tmp_path / "test.db"))
    first = apply_pending(conn)
    conn.commit()

    second = apply_pending(conn)
    conn.commit()

    assert first >= 1
    assert second == 0  # no new migrations to apply
    conn.close()


def test_latest_version_matches_schema(tmp_path: Path):
    conn = create_connection(str(tmp_path / "test.db"))
    apply_pending(conn)
    conn.commit()

    cursor = conn.execute("SELECT MAX(version) FROM _schema_version")
    db_version = cursor.fetchone()[0]
    conn.close()

    assert latest_version() == SCHEMA_VERSION
    assert db_version == SCHEMA_VERSION


def test_pending_migrations_upgrade_v1_database(tmp_path: Path):
    conn = create_connection(str(tmp_path / "test.db"))
    conn.execute(
        "CREATE TABLE _schema_version (version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL)"
    )
    conn.execute("INSERT INTO _schema_version VALUES (1, 1)")
    conn.execute("CREATE TABLE knowledge_items (id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE entities (id TEXT PRIMARY KEY)")
    conn.commit()

    assert apply_pending(conn) == 8
    conn.commit()
    assert "knowledge_entities" in _table_names(conn)
    assert "memory_contexts" in _table_names(conn)
    assert "sync_identity" in _table_names(conn)
    assert "monitor_config" in _table_names(conn)
    assert "monitor_log" in _table_names(conn)
    assert "vector_id_map" in _table_names(conn)
    assert conn.execute("SELECT MAX(version) FROM _schema_version").fetchone()[0] == 9
    conn.close()


def test_pending_migrations_add_conflict_source_to_v6_database(tmp_path: Path):
    # I-4：迁移 #7 的 ALTER 路径 —— v6 旧库（conflict_records 无 source 列）
    # 补列后：列存在、旧行回读 "write"、新行可写 source="sync"（roundtrip）。
    conn = create_connection(str(tmp_path / "test.db"))
    # v6 版冲突表 DDL（无 source 列）
    conn.execute(
        """CREATE TABLE conflict_records (
            id                TEXT PRIMARY KEY,
            target_knowledge  TEXT NOT NULL,
            field             TEXT NOT NULL DEFAULT '',
            old_value         TEXT NOT NULL DEFAULT 'null',
            new_value         TEXT NOT NULL DEFAULT 'null',
            resolution        TEXT NOT NULL DEFAULT 'NEW_WINS',
            created_at        INTEGER NOT NULL
        )"""
    )
    conn.execute(
        "INSERT INTO conflict_records (id, target_knowledge, created_at) VALUES (?, ?, ?)",
        ("cfl_AAAAAAAAAAAAAAAAAAAAAAAAAA", "knw_AAAAAAAAAAAAAAAAAAAAAAAAAA", 1),
    )
    conn.execute(
        "CREATE TABLE _schema_version (version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL)"
    )
    conn.execute("INSERT INTO _schema_version VALUES (6, 1)")
    conn.commit()

    assert apply_pending(conn) == 3  # 迁移 #7 + #8 + #9
    conn.commit()

    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(conflict_records)").fetchall()
    }
    assert "source" in columns
    assert "severity" in columns  # 迁移 #8 同路径补列
    # 旧行回读默认 "write"
    row = conn.execute(
        "SELECT source FROM conflict_records WHERE id = ?",
        ("cfl_AAAAAAAAAAAAAAAAAAAAAAAAAA",),
    ).fetchone()
    assert row[0] == "write"
    # 新行写入 source="sync" 并回读（roundtrip）
    conn.execute(
        """INSERT INTO conflict_records (id, target_knowledge, source, created_at)
           VALUES (?, ?, ?, ?)""",
        (
            "cfl_BBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "knw_BBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "sync",
            2,
        ),
    )
    conn.commit()
    row2 = conn.execute(
        "SELECT source FROM conflict_records WHERE id = ?",
        ("cfl_BBBBBBBBBBBBBBBBBBBBBBBBBBBB",),
    ).fetchone()
    assert row2[0] == "sync"
    conn.close()


def test_pending_migrations_add_conflict_severity_to_v7_database(tmp_path):
    # B3-3：迁移 #8 的 ALTER 路径 —— v7 旧库（conflict_records 有 source 无
    # severity 列）补列后：列存在、旧行列值 "high"（SQL 默认，最保守兜底）、
    # 新行可写 severity（roundtrip）。回读按 resolution 派生的语义在
    # test_conflict_severity.py::test_repo_legacy_row_severity_derived_from_resolution。
    conn = create_connection(str(tmp_path / "test.db"))
    # v7 版冲突表 DDL（有 source 列，无 severity 列）
    conn.execute(
        """CREATE TABLE conflict_records (
            id                TEXT PRIMARY KEY,
            target_knowledge  TEXT NOT NULL,
            field             TEXT NOT NULL DEFAULT '',
            old_value         TEXT NOT NULL DEFAULT 'null',
            new_value         TEXT NOT NULL DEFAULT 'null',
            resolution        TEXT NOT NULL DEFAULT 'NEW_WINS',
            created_at        INTEGER NOT NULL,
            source            TEXT NOT NULL DEFAULT 'write'
        )"""
    )
    conn.execute(
        "INSERT INTO conflict_records (id, target_knowledge, resolution, created_at) "
        "VALUES (?, ?, ?, ?)",
        ("cfl_AAAAAAAAAAAAAAAAAAAAAAAAAA", "knw_AAAAAAAAAAAAAAAAAAAAAAAAAA", "NEW_WINS", 1),
    )
    conn.execute(
        "CREATE TABLE _schema_version (version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL)"
    )
    conn.execute("INSERT INTO _schema_version VALUES (7, 1)")
    conn.commit()

    assert apply_pending(conn) == 2  # 迁移 #8 + #9
    conn.commit()

    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(conflict_records)").fetchall()
    }
    assert "severity" in columns
    # 旧行列值 = SQL 默认 high（保守兜底）
    row = conn.execute(
        "SELECT severity FROM conflict_records WHERE id = ?",
        ("cfl_AAAAAAAAAAAAAAAAAAAAAAAAAA",),
    ).fetchone()
    assert row[0] == "high"
    # 新行写入 severity 并回读（roundtrip）
    conn.execute(
        """INSERT INTO conflict_records (id, target_knowledge, severity, created_at)
           VALUES (?, ?, ?, ?)""",
        (
            "cfl_BBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "knw_BBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "low",
            2,
        ),
    )
    conn.commit()
    row2 = conn.execute(
        "SELECT severity FROM conflict_records WHERE id = ?",
        ("cfl_BBBBBBBBBBBBBBBBBBBBBBBBBBBB",),
    ).fetchone()
    assert row2[0] == "low"
    conn.close()


# ═══════════════════════════════════════════════════════
# Group 6: no knowledge_fts / knowledge_vec tables
# ═══════════════════════════════════════════════════════

def test_no_fts_or_vec_tables(tmp_path: Path):
    """knowledge_fts and knowledge_vec remain lazily created by repositories."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    tables = _table_names(conn)
    conn.close()
    assert "knowledge_fts" not in tables
    assert "knowledge_vec" not in tables
