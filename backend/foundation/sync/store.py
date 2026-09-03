"""同步身份、peer、oplog、CRDT 状态与 ACK 的 SQLite 存储。"""

from __future__ import annotations

import json

import aiosqlite

from backend.foundation.core.models import SyncOp

from .models import DeviceIdentity, Peer, PeerStatus, SyncRecord


def _identity(row: aiosqlite.Row) -> DeviceIdentity:
    return DeviceIdentity(
        id=row["device_id"],
        name=row["name"],
        domain=row["domain"],
        encrypted_private_key=row["encrypted_private_key"],
        public_key=row["public_key"],
        created_at=row["created_at"],
    )


def _peer(row: aiosqlite.Row, pending_ops: int = 0) -> Peer:
    return Peer(
        id=row["id"],
        name=row["name"],
        domain=row["domain"],
        public_key=row["public_key"],
        status=row["status"],
        paired_at=row["paired_at"],
        last_seen_ts=row["last_seen_ts"],
        last_sync_ts=row["last_sync_ts"],
        total_ops_synced=row["total_ops_synced"],
        pending_ops=pending_ops,
    )


def _op(row: aiosqlite.Row) -> SyncOp:
    return SyncOp(
        op_id=row["op_id"],
        entity=row["entity"],
        payload=json.loads(row["payload"]),
        vclock=json.loads(row["vclock"]),
        ts=row["ts"],
    )


def _record(row: aiosqlite.Row) -> SyncRecord:
    return SyncRecord(
        entity=row["entity"],
        payload=json.loads(row["payload"]),
        vclock=json.loads(row["vclock"]),
        ts=row["ts"],
        op_id=row["op_id"],
        tombstone=bool(row["tombstone"]),
    )


class SqliteSyncStore:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def get_identity(self) -> DeviceIdentity | None:
        row = await (await self._db.execute(
            "SELECT * FROM sync_identity WHERE singleton = 1"
        )).fetchone()
        return _identity(row) if row else None

    async def save_identity(self, identity: DeviceIdentity) -> None:
        await self._db.execute(
            """INSERT INTO sync_identity
               (singleton, device_id, name, domain, encrypted_private_key,
                public_key, created_at)
               VALUES (1, ?, ?, ?, ?, ?, ?)""",
            (
                identity.id,
                identity.name,
                identity.domain,
                identity.encrypted_private_key,
                identity.public_key,
                identity.created_at,
            ),
        )
        await self._db.commit()

    async def save_peer(self, peer: Peer) -> None:
        await self._db.execute(
            """INSERT INTO sync_peers
               (id, name, domain, public_key, status, paired_at, last_seen_ts,
                last_sync_ts, total_ops_synced)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 name=excluded.name, domain=excluded.domain,
                 public_key=excluded.public_key, status=excluded.status,
                 last_seen_ts=excluded.last_seen_ts""",
            (
                peer.id,
                peer.name,
                peer.domain,
                peer.public_key,
                peer.status.value,
                peer.paired_at,
                peer.last_seen_ts,
                peer.last_sync_ts,
                peer.total_ops_synced,
            ),
        )
        await self._db.commit()

    async def get_peer(self, peer_id: str) -> Peer | None:
        row = await (await self._db.execute(
            "SELECT * FROM sync_peers WHERE id = ?", (peer_id,)
        )).fetchone()
        if row is None:
            return None
        return _peer(row, await self.pending_for_peer(peer_id))

    async def list_peers(self, *, include_revoked: bool = False) -> list[Peer]:
        query = "SELECT * FROM sync_peers"
        args: tuple = ()
        if not include_revoked:
            query += " WHERE status != ?"
            args = (PeerStatus.REVOKED.value,)
        query += " ORDER BY paired_at, id"
        rows = await (await self._db.execute(query, args)).fetchall()
        return [
            _peer(row, await self.pending_for_peer(row["id"]))
            for row in rows
        ]

    async def revoke_peer(self, peer_id: str) -> bool:
        cursor = await self._db.execute(
            "UPDATE sync_peers SET status = ? WHERE id = ? AND status != ?",
            (PeerStatus.REVOKED.value, peer_id, PeerStatus.REVOKED.value),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def set_peer_status(
        self, peer_id: str, status: PeerStatus, now: int
    ) -> bool:
        cursor = await self._db.execute(
            """UPDATE sync_peers SET status = ?, last_seen_ts = ?
               WHERE id = ? AND status != ?""",
            (status.value, now, peer_id, PeerStatus.REVOKED.value),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def append_op(self, op: SyncOp) -> bool:
        cursor = await self._db.execute(
            """INSERT OR IGNORE INTO sync_oplog
               (op_id, entity, payload, vclock, ts, synced)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (
                op.op_id,
                op.entity,
                json.dumps(op.payload, ensure_ascii=False),
                json.dumps(op.vclock, sort_keys=True),
                op.ts,
            ),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def get_op(self, op_id: str) -> SyncOp | None:
        row = await (await self._db.execute(
            "SELECT * FROM sync_oplog WHERE op_id = ?", (op_id,)
        )).fetchone()
        return _op(row) if row else None

    async def list_ops(self) -> list[SyncOp]:
        rows = await (await self._db.execute(
            "SELECT * FROM sync_oplog ORDER BY ts, op_id"
        )).fetchall()
        return [_op(row) for row in rows]

    async def op_ids(self) -> set[str]:
        rows = await (await self._db.execute(
            "SELECT op_id FROM sync_oplog"
        )).fetchall()
        return {row["op_id"] for row in rows}

    async def _acked_ids(self, peer_id: str) -> set[str]:
        rows = await (await self._db.execute(
            "SELECT op_id FROM sync_peer_acks WHERE peer_id = ?", (peer_id,)
        )).fetchall()
        return {row["op_id"] for row in rows}

    async def pending_for_peer(self, peer_id: str) -> int:
        row = await (await self._db.execute(
            "SELECT domain, status FROM sync_peers WHERE id = ?", (peer_id,)
        )).fetchone()
        if row is None or row["status"] == PeerStatus.REVOKED.value:
            return 0
        acked = await self._acked_ids(peer_id)
        return sum(
            1
            for op in await self.list_ops()
            if op.op_id not in acked and op.payload.get("scope") == row["domain"]
        )

    async def pending_ops_for_peer(self, peer_id: str) -> list[SyncOp]:
        row = await (await self._db.execute(
            "SELECT domain, status FROM sync_peers WHERE id = ?", (peer_id,)
        )).fetchone()
        if row is None or row["status"] == PeerStatus.REVOKED.value:
            return []
        acked = await self._acked_ids(peer_id)
        return [
            op
            for op in await self.list_ops()
            if op.op_id not in acked and op.payload.get("scope") == row["domain"]
        ]

    async def acknowledge(self, peer_id: str, op_ids: list[str], now: int) -> int:
        if not op_ids:
            return 0
        before = self._db.total_changes
        await self._db.executemany(
            """INSERT OR IGNORE INTO sync_peer_acks
               (peer_id, op_id, acked_at) VALUES (?, ?, ?)""",
            [(peer_id, op_id, now) for op_id in op_ids],
        )
        inserted = self._db.total_changes - before
        if inserted:
            await self._db.execute(
                """UPDATE sync_peers SET last_sync_ts = ?, last_seen_ts = ?,
                   status = ?, total_ops_synced = total_ops_synced + ?
                   WHERE id = ? AND status != ?""",
                (
                    now,
                    now,
                    PeerStatus.ONLINE.value,
                    inserted,
                    peer_id,
                    PeerStatus.REVOKED.value,
                ),
            )
        await self._db.commit()
        return inserted

    async def get_state(self, entity: str) -> SyncRecord | None:
        row = await (await self._db.execute(
            "SELECT * FROM sync_state WHERE entity = ?", (entity,)
        )).fetchone()
        return _record(row) if row else None

    async def save_state(self, record: SyncRecord) -> None:
        await self._db.execute(
            """INSERT INTO sync_state
               (entity, payload, vclock, ts, op_id, tombstone)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(entity) DO UPDATE SET payload=excluded.payload,
                 vclock=excluded.vclock, ts=excluded.ts, op_id=excluded.op_id,
                 tombstone=excluded.tombstone""",
            (
                record.entity,
                json.dumps(record.payload, ensure_ascii=False),
                json.dumps(record.vclock, sort_keys=True),
                record.ts,
                record.op_id,
                int(record.tombstone),
            ),
        )
        await self._db.commit()

    async def tombstones_before(self, cutoff: int) -> list[SyncRecord]:
        rows = await (await self._db.execute(
            """SELECT * FROM sync_state
               WHERE tombstone = 1 AND ts <= ? ORDER BY ts, entity""",
            (cutoff,),
        )).fetchall()
        return [_record(row) for row in rows]

    async def all_active_peers_acked(self, op_id: str) -> bool:
        row = await (await self._db.execute(
            """SELECT COUNT(*) AS missing FROM sync_peers p
               WHERE p.status != ? AND NOT EXISTS (
                 SELECT 1 FROM sync_peer_acks a
                 WHERE a.peer_id = p.id AND a.op_id = ?
               )""",
            (PeerStatus.REVOKED.value, op_id),
        )).fetchone()
        return bool(row and row["missing"] == 0)

    async def delete_tombstone(self, record: SyncRecord) -> None:
        await self._db.execute(
            """DELETE FROM sync_state
               WHERE entity = ? AND op_id = ? AND tombstone = 1""",
            (record.entity, record.op_id),
        )
        await self._db.execute(
            "DELETE FROM sync_oplog WHERE op_id = ?", (record.op_id,)
        )
        await self._db.commit()

    async def set_meta(self, key: str, value: str) -> None:
        await self._db.execute(
            """INSERT INTO sync_meta (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (key, value),
        )
        await self._db.commit()

    async def get_meta(self, key: str) -> str | None:
        row = await (await self._db.execute(
            "SELECT value FROM sync_meta WHERE key = ?", (key,)
        )).fetchone()
        return row["value"] if row else None

    async def list_meta_keys(self, prefix: str) -> list[str]:
        escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        rows = await (
            await self._db.execute(
                "SELECT key FROM sync_meta WHERE key LIKE ? ESCAPE '\\' ORDER BY key",
                (f"{escaped}%",),
            )
        ).fetchall()
        return [row["key"] for row in rows]

    async def delete_meta(self, key: str) -> None:
        await self._db.execute("DELETE FROM sync_meta WHERE key = ?", (key,))
        await self._db.commit()

    async def total_acknowledgements(self) -> int:
        row = await (await self._db.execute(
            "SELECT COUNT(*) AS count FROM sync_peer_acks"
        )).fetchone()
        return int(row["count"] if row else 0)
