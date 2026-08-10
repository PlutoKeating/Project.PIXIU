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
    extra = tables - EXPECTED_TABLES - {"_schema_version"}
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

    assert apply_pending(conn) == 3
    conn.commit()
    assert "knowledge_entities" in _table_names(conn)
    assert "memory_contexts" in _table_names(conn)
    assert "sync_identity" in _table_names(conn)
    assert conn.execute("SELECT MAX(version) FROM _schema_version").fetchone()[0] == 4
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
