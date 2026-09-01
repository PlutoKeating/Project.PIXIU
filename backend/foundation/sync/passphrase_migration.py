"""Rotate the passphrase that encrypts the persisted Ed25519 device identity.

This module is intentionally usable from Debian ``postinst``.  It updates only
the encrypted private-key blob; the device ID, public key, peers, CRDT state,
and acknowledgements remain unchanged.
"""

from __future__ import annotations

import argparse
import hmac
import os
import sqlite3
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class PassphraseMigrationError(RuntimeError):
    """The stored identity could not be safely re-encrypted."""


def stored_identity_uses_passphrase(
    database: str | Path, passphrase: str
) -> bool | None:
    """Return whether the stored identity decrypts with ``passphrase``.

    ``None`` means no identity exists.  A mismatched key pair is treated as a
    hard error rather than as a wrong passphrase.
    """

    path = Path(database)
    if not path.is_file():
        return None
    connection = sqlite3.connect(path)
    try:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'sync_identity'"
        ).fetchone()
        if table is None:
            return None
        row = connection.execute(
            "SELECT encrypted_private_key, public_key "
            "FROM sync_identity WHERE singleton = 1"
        ).fetchone()
        if row is None:
            return None
        try:
            private_key = serialization.load_pem_private_key(
                row[0], password=passphrase.encode("utf-8")
            )
        except (TypeError, ValueError):
            return False
        if not isinstance(private_key, Ed25519PrivateKey):
            raise PassphraseMigrationError("stored sync key is not Ed25519")
        public_key = private_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        if not hmac.compare_digest(public_key, bytes(row[1])):
            raise PassphraseMigrationError(
                "stored sync private and public keys do not match"
            )
        return True
    finally:
        connection.close()


def rotate_identity_passphrase(
    database: str | Path,
    old_passphrase: str,
    new_passphrase: str,
) -> bool:
    """Re-encrypt an existing sync identity and preserve its public identity.

    Returns ``True`` when an identity was migrated and ``False`` when the
    database has no ``sync_identity`` table or row.  Any validation or
    decryption failure leaves the database unchanged.
    """

    if len(new_passphrase) < 16:
        raise PassphraseMigrationError(
            "the new sync passphrase must contain 16 characters"
        )

    path = Path(database)
    if not path.is_file():
        return False

    connection = sqlite3.connect(path)
    try:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'sync_identity'"
        ).fetchone()
        if table is None:
            return False

        row = connection.execute(
            "SELECT encrypted_private_key, public_key "
            "FROM sync_identity WHERE singleton = 1"
        ).fetchone()
        if row is None:
            return False
        if len(old_passphrase) < 16:
            raise PassphraseMigrationError(
                "an existing sync identity requires its old passphrase"
            )

        try:
            private_key = serialization.load_pem_private_key(
                row[0], password=old_passphrase.encode("utf-8")
            )
        except (TypeError, ValueError) as exc:
            raise PassphraseMigrationError(
                "unable to decrypt stored sync identity with the old passphrase"
            ) from exc
        if not isinstance(private_key, Ed25519PrivateKey):
            raise PassphraseMigrationError("stored sync key is not Ed25519")

        public_key = private_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        if not hmac.compare_digest(public_key, bytes(row[1])):
            raise PassphraseMigrationError(
                "stored sync private and public keys do not match"
            )

        encrypted = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(new_passphrase.encode("utf-8")),
        )
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            "UPDATE sync_identity SET encrypted_private_key = ? "
            "WHERE singleton = 1",
            (encrypted,),
        )
        if cursor.rowcount != 1:
            raise PassphraseMigrationError("stored sync identity disappeared")
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rotate PIXIU's persisted sync identity passphrase."
    )
    parser.add_argument("--database", required=True)
    args = parser.parse_args()

    old_passphrase = os.getenv("PIXIU_SYNC_OLD_PASSPHRASE", "")
    new_passphrase = os.getenv("PIXIU_SYNC_NEW_PASSPHRASE", "")
    rotate_identity_passphrase(args.database, old_passphrase, new_passphrase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
