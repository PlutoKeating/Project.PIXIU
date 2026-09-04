from __future__ import annotations

import importlib.util
import os
import sqlite3
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "build/release/scripts/migrate-system-data.py"
SPEC = importlib.util.spec_from_file_location("pixiu_migration", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_migration_preserves_schema_counts_identity_and_source(tmp_path: Path) -> None:
    source = tmp_path / "legacy"
    source.mkdir()
    database = source / "pixiu.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        "PRAGMA user_version=12;"
        "CREATE TABLE knowledge_items(id TEXT PRIMARY KEY, body TEXT);"
        "CREATE TABLE sync_identity(device_id TEXT, public_key TEXT);"
        "INSERT INTO knowledge_items VALUES('knw_test', 'remember me');"
        "INSERT INTO sync_identity VALUES('dev_test', 'public');"
    )
    connection.commit()
    connection.close()
    (source / "data").mkdir()
    (source / "data/vector-engine.db").write_bytes(b"vector")
    legacy_config = tmp_path / "legacy.env"
    legacy_config.write_text(
        "PIXIU_DB_PATH=/var/lib/pixiu/pixiu.db\n"
        "PIXIU_VECTOR_DB_PATH=/var/lib/pixiu/data/vector-engine.db\n"
        "PIXIU_SYNC_KEY_PASSPHRASE=secret-value\n",
        encoding="utf-8",
    )
    data = tmp_path / "home/.local/share/pixiu"
    config = tmp_path / "home/.config/pixiu"
    state = tmp_path / "home/.local/state/pixiu"

    record = MODULE.migrate(
        source_root=source, source_config=legacy_config, data_dir=data,
        config_dir=config, state_dir=state, uid=os.getuid(), gid=os.getgid(),
    )

    assert record["verified"] is True
    assert record["source_retained"] is True
    assert database.exists()
    assert MODULE._snapshot(data / "pixiu.db") == MODULE._snapshot(database)
    assert (data / "data/vector-engine.db").read_bytes() == b"vector"
    migrated_config = (config / "pixiu.env").read_text(encoding="utf-8")
    assert "PIXIU_DB_PATH" not in migrated_config
    assert "PIXIU_VECTOR_DB_PATH" not in migrated_config
    assert "PIXIU_SYNC_KEY_PASSPHRASE=secret-value" in migrated_config
    assert (state / "migration-v1.json").stat().st_mode & 0o777 == 0o600


def test_migration_refuses_nonempty_target(tmp_path: Path) -> None:
    source = tmp_path / "legacy"
    source.mkdir()
    connection = sqlite3.connect(source / "pixiu.db")
    connection.execute("CREATE TABLE sample(value TEXT)")
    connection.close()
    data = tmp_path / "data"
    data.mkdir()
    (data / "pixiu.db").write_bytes(b"occupied")
    try:
        MODULE.migrate(
            source_root=source, source_config=tmp_path / "missing.env", data_dir=data,
            config_dir=tmp_path / "config", state_dir=tmp_path / "state",
            uid=os.getuid(), gid=os.getgid(),
        )
    except RuntimeError as error:
        assert "not empty" in str(error)
    else:
        raise AssertionError("nonempty migration target must be rejected")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as first:
        test_migration_preserves_schema_counts_identity_and_source(Path(first))
    with tempfile.TemporaryDirectory() as second:
        test_migration_refuses_nonempty_target(Path(second))
    print("system data migration tests: OK")
