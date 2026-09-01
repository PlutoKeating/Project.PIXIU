"""Tests for safe sync identity passphrase rotation."""

from __future__ import annotations

import sqlite3

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.foundation.sync.passphrase_migration import (
    PassphraseMigrationError,
    rotate_identity_passphrase,
)


OLD_PASSPHRASE = "pixiu-local-sync-change-me-2026"
NEW_PASSPHRASE = "new-random-passphrase-for-tests"


def _create_identity_database(path) -> bytes:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    encrypted = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(OLD_PASSPHRASE.encode()),
    )
    connection = sqlite3.connect(path)
    connection.execute(
        """CREATE TABLE sync_identity (
            singleton INTEGER PRIMARY KEY,
            device_id TEXT NOT NULL,
            name TEXT NOT NULL,
            domain TEXT NOT NULL,
            encrypted_private_key BLOB NOT NULL,
            public_key BLOB NOT NULL,
            created_at INTEGER NOT NULL
        )"""
    )
    connection.execute(
        "INSERT INTO sync_identity VALUES (1, ?, ?, ?, ?, ?, ?)",
        ("dev_keep_me", "device", "shared:home", encrypted, public_key, 1),
    )
    connection.commit()
    connection.close()
    return public_key


def test_rotation_preserves_device_identity_and_reencrypts_private_key(tmp_path):
    database = tmp_path / "pixiu.db"
    public_key = _create_identity_database(database)

    assert rotate_identity_passphrase(
        database, OLD_PASSPHRASE, NEW_PASSPHRASE
    )

    connection = sqlite3.connect(database)
    row = connection.execute(
        "SELECT device_id, encrypted_private_key, public_key "
        "FROM sync_identity WHERE singleton = 1"
    ).fetchone()
    connection.close()
    assert row[0] == "dev_keep_me"
    assert bytes(row[2]) == public_key
    private_key = serialization.load_pem_private_key(
        row[1], password=NEW_PASSPHRASE.encode()
    )
    assert isinstance(private_key, Ed25519PrivateKey)
    with pytest.raises((TypeError, ValueError)):
        serialization.load_pem_private_key(
            row[1], password=OLD_PASSPHRASE.encode()
        )


def test_wrong_old_passphrase_rolls_back_without_modifying_identity(tmp_path):
    database = tmp_path / "pixiu.db"
    _create_identity_database(database)
    connection = sqlite3.connect(database)
    before = connection.execute(
        "SELECT encrypted_private_key FROM sync_identity WHERE singleton = 1"
    ).fetchone()[0]
    connection.close()

    with pytest.raises(PassphraseMigrationError, match="unable to decrypt"):
        rotate_identity_passphrase(
            database, "incorrect-old-passphrase", NEW_PASSPHRASE
        )

    connection = sqlite3.connect(database)
    after = connection.execute(
        "SELECT encrypted_private_key FROM sync_identity WHERE singleton = 1"
    ).fetchone()[0]
    connection.close()
    assert after == before


def test_existing_identity_without_old_passphrase_is_rejected(tmp_path):
    database = tmp_path / "pixiu.db"
    _create_identity_database(database)

    with pytest.raises(PassphraseMigrationError, match="requires its old"):
        rotate_identity_passphrase(database, "", NEW_PASSPHRASE)


def test_missing_database_or_identity_is_a_noop(tmp_path):
    missing = tmp_path / "missing.db"
    assert not rotate_identity_passphrase(
        missing, OLD_PASSPHRASE, NEW_PASSPHRASE
    )
    assert not missing.exists()

    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    assert not rotate_identity_passphrase(
        empty, OLD_PASSPHRASE, NEW_PASSPHRASE
    )
