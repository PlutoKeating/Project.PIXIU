#!/usr/bin/env python3
"""One-time, rollback-safe migration from the legacy system account store."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import shutil
import sqlite3
import stat
import tempfile
from pathlib import Path

MIGRATION_VERSION = 1
PATH_KEYS = {"PIXIU_DB_PATH", "PIXIU_DATA_DIR", "PIXIU_VECTOR_DB_PATH"}


def _snapshot(path: Path) -> dict[str, object]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise RuntimeError("database integrity check failed")
        schema = int(connection.execute("PRAGMA user_version").fetchone()[0])
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts = {name: int(connection.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]) for name in tables}
        identity_rows = []
        if "sync_identity" in counts:
            identity_rows = connection.execute(
                "SELECT device_id, public_key FROM sync_identity ORDER BY device_id"
            ).fetchall()
        normalized_identity = [
            [
                value.hex() if isinstance(value, bytes) else str(value)
                for value in row
            ]
            for row in identity_rows
        ]
        identity_digest = hashlib.sha256(
            json.dumps(normalized_identity, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        return {"schema_version": schema, "table_counts": counts, "identity_digest": identity_digest}
    finally:
        connection.close()


def _copy_database(source: Path, destination: Path) -> None:
    source_db = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    target_db = sqlite3.connect(destination)
    try:
        source_db.backup(target_db)
    finally:
        target_db.close()
        source_db.close()


def _copy_config(source: Path, destination: Path) -> None:
    lines = []
    if source.is_file():
        for line in source.read_text(encoding="utf-8").splitlines():
            key = line.split("=", 1)[0].strip() if "=" in line else ""
            if key not in PATH_KEYS:
                lines.append(line)
    destination.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def migrate(
    *, source_root: Path, source_config: Path, data_dir: Path,
    config_dir: Path, state_dir: Path, uid: int, gid: int,
) -> dict[str, object]:
    source_db = source_root / "pixiu.db"
    destination_db = data_dir / "pixiu.db"
    marker = state_dir / "migration-v1.json"
    journal = state_dir / ".migration-v1.in-progress"
    destination_config = config_dir / "pixiu.env"
    target_data = data_dir / "data"
    if not source_db.is_file():
        raise RuntimeError("legacy database is missing")
    data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if marker.exists():
        raise RuntimeError("legacy data was already migrated")
    if journal.exists():
        destination_db.unlink(missing_ok=True)
        destination_config.unlink(missing_ok=True)
        if target_data.exists():
            shutil.rmtree(target_data)
    elif destination_db.exists() or destination_config.exists() or (
        target_data.exists() and any(target_data.iterdir())
    ):
        raise RuntimeError("migration target is not empty")

    source_snapshot = _snapshot(source_db)
    journal.write_text(
        json.dumps({"migration_version": MIGRATION_VERSION, "source": source_snapshot}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chown(journal, uid, gid)
    os.chmod(journal, 0o600)
    fd, temporary_name = tempfile.mkstemp(prefix=".pixiu-migration-", dir=data_dir)
    os.close(fd)
    temporary_db = Path(temporary_name)
    temporary_config = config_dir / ".pixiu.env.migrating"
    temporary_data = data_dir / ".data.migrating"
    try:
        _copy_database(source_db, temporary_db)
        if _snapshot(temporary_db) != source_snapshot:
            raise RuntimeError("migrated database verification failed")
        os.chmod(temporary_db, 0o600)
        os.chown(temporary_db, uid, gid)
        if source_config.is_file():
            _copy_config(source_config, temporary_config)
            os.chmod(temporary_config, 0o600)
            os.chown(temporary_config, uid, gid)

        legacy_data = source_root / "data"
        temporary_data.mkdir(mode=0o700)
        if legacy_data.is_dir():
            for child in legacy_data.iterdir():
                if child.is_symlink():
                    raise RuntimeError("legacy data contains a symlink")
                target = temporary_data / child.name
                if child.is_dir():
                    shutil.copytree(child, target, symlinks=False)
                elif child.is_file():
                    shutil.copy2(child, target)
        for root, directories, files in os.walk(temporary_data):
            os.chown(root, uid, gid)
            os.chmod(root, 0o700)
            for name in files:
                item = Path(root) / name
                os.chown(item, uid, gid)
                os.chmod(item, 0o600)

        if target_data.exists():
            target_data.rmdir()
        os.replace(temporary_data, target_data)
        os.replace(temporary_db, destination_db)
        if temporary_config.exists():
            os.replace(temporary_config, destination_config)

        record = {
            "migration_version": MIGRATION_VERSION,
            "source_retained": True,
            "verified": True,
            **source_snapshot,
        }
        marker.write_text(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        os.chown(marker, uid, gid)
        os.chmod(marker, 0o600)
        journal.unlink()
        return record
    finally:
        temporary_db.unlink(missing_ok=True)
        temporary_config.unlink(missing_ok=True)
        if temporary_data.exists():
            shutil.rmtree(temporary_data)


def _validated_user_path(value: str, home: Path, uid: int) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise RuntimeError("migration target must be absolute")
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(home.resolve(strict=True))
    except ValueError as error:
        raise RuntimeError("migration target must remain inside the selected user's home") from error
    parent = resolved
    while not parent.exists():
        parent = parent.parent
    details = parent.stat()
    if stat.S_ISLNK(details.st_mode) or details.st_uid != uid:
        raise RuntimeError("migration target parent ownership is invalid")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uid", required=True, type=int)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--config-dir", required=True)
    parser.add_argument("--state-dir", required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit("pixiu migration helper must run through system authorization")
    account = pwd.getpwuid(args.uid)
    if args.uid < 1000 or not account.pw_dir or account.pw_dir == "/":
        raise SystemExit("invalid desktop user")
    home = Path(account.pw_dir)
    paths = [_validated_user_path(value, home, args.uid) for value in (args.data_dir, args.config_dir, args.state_dir)]
    migrate(
        source_root=Path("/var/lib/pixiu"), source_config=Path("/etc/pixiu/pixiu.env"),
        data_dir=paths[0], config_dir=paths[1], state_dir=paths[2], uid=args.uid, gid=account.pw_gid,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
