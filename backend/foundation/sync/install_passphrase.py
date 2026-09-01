"""Crash-recoverable install-time provisioning of the sync key passphrase."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import tempfile
from pathlib import Path
from typing import Callable

from .passphrase_migration import (
    PassphraseMigrationError,
    rotate_identity_passphrase,
    stored_identity_uses_passphrase,
)


PUBLIC_PLACEHOLDERS = frozenset(
    {"change-me-before-production", "pixiu-local-sync-change-me-2026"}
)
PASSPHRASE_KEY = "PIXIU_SYNC_KEY_PASSPHRASE"
DATABASE_KEY = "PIXIU_DB_PATH"


def _value(lines: list[str], key: str) -> str:
    prefix = f"{key}="
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix) :]
    return ""


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write(
    path: Path,
    content: str,
    *,
    mode: int,
    owner: tuple[int, int] | None = None,
) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        if owner is not None:
            os.fchown(descriptor, *owner)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def _write_journal(path: Path, payload: dict[str, str]) -> None:
    _atomic_write(
        path,
        json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n",
        mode=0o600,
    )


def _replace_config_passphrase(config: Path, passphrase: str) -> None:
    stat = config.stat()
    lines = config.read_text(encoding="utf-8").splitlines()
    replacement = f"{PASSPHRASE_KEY}={passphrase}"
    output: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith(f"{PASSPHRASE_KEY}="):
            if not replaced:
                output.append(replacement)
                replaced = True
            continue
        output.append(line)
    if not replaced:
        output.append(replacement)
    _atomic_write(
        config,
        "\n".join(output) + "\n",
        mode=0o640,
        owner=(stat.st_uid, stat.st_gid),
    )


def _resume_migration(config: Path, journal: Path) -> None:
    payload = json.loads(journal.read_text(encoding="utf-8"))
    required = {"state", "database", "old_passphrase", "new_passphrase"}
    if set(payload) != required:
        raise PassphraseMigrationError("invalid passphrase migration journal")

    database = Path(payload["database"])
    old_passphrase = payload["old_passphrase"]
    new_passphrase = payload["new_passphrase"]
    state = payload["state"]
    if state == "prepared":
        try:
            rotate_identity_passphrase(
                database, old_passphrase, new_passphrase
            )
        except PassphraseMigrationError:
            # A crash can occur after SQLite commits but before the journal's
            # state update.  In that case the new passphrase is authoritative.
            if stored_identity_uses_passphrase(database, new_passphrase) is not True:
                raise
        payload["state"] = "database_rotated"
        _write_journal(journal, payload)
    elif state != "database_rotated":
        raise PassphraseMigrationError("invalid passphrase migration state")

    _replace_config_passphrase(config, new_passphrase)
    journal.unlink()
    _fsync_directory(journal.parent)


def ensure_unique_install_passphrase(
    config_path: str | Path,
    default_database: str | Path,
    *,
    token_factory: Callable[[], str] | None = None,
) -> bool:
    """Provision or recover a unique passphrase for a packaged installation.

    A root-only journal makes the database re-encryption and conffile update
    recoverable across power loss.  Returns ``True`` when provisioning or
    recovery was performed.
    """

    config = Path(config_path)
    if not config.is_file():
        raise PassphraseMigrationError("PIXIU environment file is missing")
    journal = config.parent / ".sync-passphrase-migration.json"
    if journal.exists():
        _resume_migration(config, journal)
        return True

    lines = config.read_text(encoding="utf-8").splitlines()
    current = _value(lines, PASSPHRASE_KEY)
    normalized = current.strip().casefold()
    if normalized and normalized not in PUBLIC_PLACEHOLDERS:
        return False

    database_text = _value(lines, DATABASE_KEY)
    database = Path(database_text or default_database)
    identity_state = stored_identity_uses_passphrase(database, current)
    if not current and identity_state is not None:
        raise PassphraseMigrationError(
            "existing sync identity has no configured old passphrase"
        )

    factory = token_factory or (lambda: secrets.token_urlsafe(32))
    new_passphrase = factory()
    if (
        len(new_passphrase) < 16
        or new_passphrase.strip().casefold() in PUBLIC_PLACEHOLDERS
    ):
        raise PassphraseMigrationError("generated sync passphrase is invalid")

    _write_journal(
        journal,
        {
            "state": "prepared",
            "database": str(database),
            "old_passphrase": current,
            "new_passphrase": new_passphrase,
        },
    )
    _resume_migration(config, journal)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Provision PIXIU's packaged sync identity passphrase."
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--default-database", required=True)
    args = parser.parse_args()
    changed = ensure_unique_install_passphrase(
        args.config, args.default_database
    )
    if changed:
        print("pixiu: generated a unique sync identity passphrase")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
