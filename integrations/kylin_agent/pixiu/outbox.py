"""Bounded durable delivery records, independent of backend private storage.

Callers partition by destination/profile and retain the original idempotency key.
Leases prevent concurrent senders; backend idempotency handles crash-after-send.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import sqlite3
import stat
import threading
import time


class Outbox:
    def __init__(self, directory: Path, partition: str, *, capacity=1024,
                 byte_limit=16 * 1024 * 1024, clock=time.time):
        if not partition or capacity < 1 or byte_limit < 1:
            raise ValueError("INVALID_OUTBOX_CONFIGURATION")
        directory = Path(directory)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("UNSAFE_OUTBOX_DIRECTORY")
        path = directory / "delivery.sqlite3"
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError("UNSAFE_OUTBOX_FILE")
        finally:
            os.close(fd)
        self.partition, self.capacity, self.byte_limit = partition, capacity, byte_limit
        self.clock = clock
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, timeout=2, check_same_thread=False)
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("""CREATE TABLE IF NOT EXISTS deliveries (
            partition TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL,
            size INTEGER NOT NULL, lease TEXT NOT NULL DEFAULT '',
            available REAL NOT NULL DEFAULT 0, PRIMARY KEY(partition, key))""")
        self._db.commit()

    @contextmanager
    def _transaction(self):
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self._db.commit()
            except BaseException:
                self._db.rollback()
                raise

    def enqueue(self, key: str, payload: dict) -> None:
        if not key or len(key) > 256 or not isinstance(payload, dict):
            raise ValueError("INVALID_OUTBOX_RECORD")
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
        size = len(encoded.encode("utf-8"))
        if size > 2 * 1024 * 1024:
            raise ValueError("OUTBOX_RECORD_TOO_LARGE")
        with self._transaction():
            previous = self._db.execute(
                "SELECT payload FROM deliveries WHERE partition=? AND key=?",
                (self.partition, key)).fetchone()
            if previous:
                if previous[0] != encoded:
                    raise ValueError("OUTBOX_IDEMPOTENCY_CONFLICT")
                return
            count, used = self._db.execute("SELECT COUNT(*), COALESCE(SUM(size),0) FROM deliveries").fetchone()
            if count >= self.capacity or used + size > self.byte_limit:
                raise ValueError("OUTBOX_FULL")
            self._db.execute("INSERT INTO deliveries(partition,key,payload,size) VALUES(?,?,?,?)",
                             (self.partition, key, encoded, size))

    def claim(self, *, lease_seconds=30) -> tuple[str, dict, str] | None:
        if lease_seconds <= 0:
            raise ValueError("INVALID_OUTBOX_LEASE")
        with self._transaction():
            row = self._db.execute(
                "SELECT key,payload FROM deliveries WHERE partition=? AND available<=? ORDER BY rowid LIMIT 1",
                (self.partition, self.clock())).fetchone()
            if not row:
                return None
            lease = secrets.token_hex(16)
            self._db.execute("UPDATE deliveries SET lease=?,available=? WHERE partition=? AND key=?",
                             (lease, self.clock() + lease_seconds, self.partition, row[0]))
            return row[0], json.loads(row[1]), lease

    def acknowledge(self, key: str, lease: str) -> bool:
        with self._transaction():
            return self._db.execute(
                "DELETE FROM deliveries WHERE partition=? AND key=? AND lease=? AND available>?",
                (self.partition, key, lease, self.clock())).rowcount == 1

    def retry(self, key: str, lease: str, *, delay=30) -> bool:
        if delay < 0:
            raise ValueError("INVALID_OUTBOX_DELAY")
        with self._transaction():
            return self._db.execute(
                "UPDATE deliveries SET lease='',available=? WHERE partition=? AND key=? AND lease=? AND available>?",
                (self.clock() + delay, self.partition, key, lease, self.clock())).rowcount == 1

    def pending(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM deliveries WHERE partition=?",
                                    (self.partition,)).fetchone()[0]

    def close(self):
        with self._lock:
            self._db.close()
