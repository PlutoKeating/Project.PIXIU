"""Install-time passphrase provisioning and crash-recovery tests."""

from __future__ import annotations

import json
import sqlite3

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.foundation.sync import install_passphrase
from backend.foundation.sync.install_passphrase import (
    ensure_unique_install_passphrase,
)
from backend.foundation.sync.passphrase_migration import (
    PassphraseMigrationError,
    stored_identity_uses_passphrase,
)


OLD = "pixiu-local-sync-change-me-2026"
NEW = "generated-install-passphrase-012345"


def _config(path, passphrase: str = OLD) -> None:
    path.write_text(
        f"PIXIU_DB_PATH={path.parent / 'pixiu.db'}\n"
        f"PIXIU_SYNC_KEY_PASSPHRASE={passphrase}\n",
        encoding="utf-8",
    )
    path.chmod(0o640)


def _identity_database(path, passphrase: str = OLD) -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    encrypted = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(passphrase.encode()),
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


def _journal(config):
    return config.parent / ".sync-passphrase-migration.json"


def test_fresh_install_replaces_placeholder_without_creating_database(tmp_path):
    config = tmp_path / "pixiu.env"
    _config(config)

    assert ensure_unique_install_passphrase(
        config, tmp_path / "pixiu.db", token_factory=lambda: NEW
    )

    assert f"PIXIU_SYNC_KEY_PASSPHRASE={NEW}" in config.read_text()
    assert config.stat().st_mode & 0o777 == 0o640
    assert not (tmp_path / "pixiu.db").exists()
    assert not _journal(config).exists()


def test_existing_identity_is_rotated_and_preserved(tmp_path):
    config = tmp_path / "pixiu.env"
    database = tmp_path / "pixiu.db"
    _config(config)
    _identity_database(database)

    assert ensure_unique_install_passphrase(
        config, database, token_factory=lambda: NEW
    )

    assert stored_identity_uses_passphrase(database, NEW) is True
    assert stored_identity_uses_passphrase(database, OLD) is False
    connection = sqlite3.connect(database)
    device_id = connection.execute(
        "SELECT device_id FROM sync_identity WHERE singleton = 1"
    ).fetchone()[0]
    connection.close()
    assert device_id == "dev_keep_me"
    assert not _journal(config).exists()


def test_recovers_if_journal_state_update_fails_after_database_commit(
    tmp_path, monkeypatch
):
    config = tmp_path / "pixiu.env"
    database = tmp_path / "pixiu.db"
    _config(config)
    _identity_database(database)
    original_write = install_passphrase._write_journal
    calls = 0

    def fail_second_write(path, payload):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated full filesystem")
        original_write(path, payload)

    monkeypatch.setattr(
        install_passphrase, "_write_journal", fail_second_write
    )
    with pytest.raises(OSError, match="simulated"):
        ensure_unique_install_passphrase(
            config, database, token_factory=lambda: NEW
        )
    assert stored_identity_uses_passphrase(database, NEW) is True
    assert json.loads(_journal(config).read_text())["state"] == "prepared"

    monkeypatch.setattr(
        install_passphrase, "_write_journal", original_write
    )
    assert ensure_unique_install_passphrase(config, database)
    assert f"PIXIU_SYNC_KEY_PASSPHRASE={NEW}" in config.read_text()
    assert not _journal(config).exists()


def test_recovers_if_config_replacement_fails(tmp_path, monkeypatch):
    config = tmp_path / "pixiu.env"
    database = tmp_path / "pixiu.db"
    _config(config)
    _identity_database(database)
    original_replace = install_passphrase._replace_config_passphrase

    def fail_replace(*_args, **_kwargs):
        raise OSError("simulated config write failure")

    monkeypatch.setattr(
        install_passphrase, "_replace_config_passphrase", fail_replace
    )
    with pytest.raises(OSError, match="simulated"):
        ensure_unique_install_passphrase(
            config, database, token_factory=lambda: NEW
        )
    assert stored_identity_uses_passphrase(database, NEW) is True
    assert json.loads(_journal(config).read_text())["state"] == "database_rotated"

    monkeypatch.setattr(
        install_passphrase, "_replace_config_passphrase", original_replace
    )
    assert ensure_unique_install_passphrase(config, database)
    assert not _journal(config).exists()


def test_missing_old_passphrase_with_existing_identity_fails_before_journal(
    tmp_path,
):
    config = tmp_path / "pixiu.env"
    database = tmp_path / "pixiu.db"
    _config(config, "")
    _identity_database(database)

    with pytest.raises(PassphraseMigrationError, match="no configured old"):
        ensure_unique_install_passphrase(
            config, database, token_factory=lambda: NEW
        )
    assert not _journal(config).exists()
    assert stored_identity_uses_passphrase(database, OLD) is True


def test_custom_passphrase_is_left_unchanged(tmp_path):
    config = tmp_path / "pixiu.env"
    _config(config, "existing-strong-custom-passphrase")

    assert not ensure_unique_install_passphrase(
        config, tmp_path / "pixiu.db", token_factory=lambda: NEW
    )
    assert "existing-strong-custom-passphrase" in config.read_text()
