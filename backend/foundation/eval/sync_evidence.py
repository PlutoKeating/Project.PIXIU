"""Generate deterministic three-node protocol evidence without claiming real devices."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import aiosqlite

from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.sync import (
    PairingMethod,
    ScopeNotShareable,
    SqliteSyncStore,
    SyncService,
)
from backend.foundation.sync.anti_entropy import AntiEntropy
from backend.foundation.sync.gc import TombstoneGC


DOMAIN = "shared:home"
NOW = 2_000_000_000
SCHEMA_VERSION = 1


async def _node(
    root: Path, name: str, passphrase: str
) -> tuple[SyncService, SqliteSyncStore, Any]:
    path = root / f"{name}.db"
    bootstrap = sqlite3.connect(path)
    init_db_on_connection(bootstrap)
    bootstrap.close()
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    store = SqliteSyncStore(db)
    service = SyncService(
        store,
        device_name=name,
        domain=DOMAIN,
        key_passphrase=passphrase,
    )
    return service, store, db


async def _pair(a: SyncService, b: SyncService) -> None:
    token_b = await b.create_pairing_token(PairingMethod.QR, now=NOW)
    await a.pair(PairingMethod.QR, token_b, now=NOW)
    token_a = await a.create_pairing_token(PairingMethod.QR, now=NOW)
    await b.pair(PairingMethod.QR, token_a, now=NOW)


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def _state_digest(service: SyncService, entities: list[str]) -> str:
    states = []
    for entity in sorted(entities):
        state = await service._store.get_state(entity)
        states.append(None if state is None else state.model_dump(mode="json"))
    return _digest(states)


async def _logical_view_digest(service: SyncService, entities: list[str]) -> str:
    """Hash the visible view; a collected tombstone and a tombstone are both deleted."""
    visible = []
    for entity in sorted(entities):
        state = await service._store.get_state(entity)
        if state is None or state.tombstone:
            visible.append({"entity": entity, "deleted": True})
        else:
            visible.append(
                {"entity": entity, "deleted": False, "payload": state.payload}
            )
    return _digest(visible)


async def run_three_node_protocol_evidence(
    root: Path,
    *,
    release_commit: str,
    generated_at: int,
) -> dict[str, Any]:
    """Run W6 protocol scenarios with three isolated stores in one process."""
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        passphrase = secrets.token_urlsafe(32)
        nodes = [
            await _node(work, "node-a", passphrase),
            await _node(work, "node-b", passphrase),
            await _node(work, "node-c", passphrase),
        ]
        a, b, c = [node[0] for node in nodes]
        try:
            await _pair(a, b)
            await _pair(b, c)
            await _pair(a, c)
            identities = [await service.initialize() for service in (a, b, c)]
            peer_counts = [len(await store.list_peers()) for _, store, _ in nodes]
            scenarios: list[dict[str, Any]] = [
                {
                    "id": "full-mesh-pairing",
                    "passed": peer_counts == [2, 2, 2],
                    "node_count": 3,
                }
            ]

            concurrent_entity = "evidence:concurrent"
            concurrent_ops = [
                await service.record_local(
                    concurrent_entity, {"writer": index}, DOMAIN, now=NOW + 1
                )
                for index, service in enumerate((a, b, c), start=1)
            ]
            for service in (a, b, c):
                await service.receive_ops(concurrent_ops)
            concurrent_digests = [
                await _state_digest(service, [concurrent_entity])
                for service in (a, b, c)
            ]
            scenarios.append(
                {
                    "id": "concurrent-update-convergence",
                    "passed": len(set(concurrent_digests)) == 1,
                    "state_digest": concurrent_digests[0],
                }
            )

            offline_entity = "evidence:offline"
            offline_op = await a.record_local(
                offline_entity, {"value": "queued"}, DOMAIN, now=NOW + 2
            )
            summary_c = await AntiEntropy(c._store, None).summary()
            anti_entropy_a = AntiEntropy(a._store, None)
            delta = await anti_entropy_a.delta_for(
                set(summary_c["op_ids"])
            )
            accepted_c = await c.receive_ops(delta)
            summary_b = await AntiEntropy(b._store, None).summary()
            delta_b = await anti_entropy_a.delta_for(set(summary_b["op_ids"]))
            accepted_b = await b.receive_ops(delta_b)
            offline_digests = [
                await _state_digest(service, [offline_entity])
                for service in (a, b, c)
            ]
            scenarios.append(
                {
                    "id": "offline-anti-entropy",
                    "passed": (
                        offline_op.op_id in {operation.op_id for operation in delta}
                        and offline_op.op_id
                        in {operation.op_id for operation in delta_b}
                        and accepted_c >= 1
                        and accepted_b >= 1
                        and len(set(offline_digests)) == 1
                    ),
                    "delta_count": len(delta) + len(delta_b),
                    "state_digest": offline_digests[0],
                }
            )

            forgotten_entity = "evidence:forgotten"
            created = await a.record_local(
                forgotten_entity, {"value": "old"}, DOMAIN, now=NOW + 3
            )
            await b.receive_ops([created])
            await c.receive_ops([created])
            tombstone = await b.record_local(
                forgotten_entity, {}, DOMAIN, deleted=True, now=NOW + 4
            )
            await a.receive_ops([tombstone])
            stale_summary = await AntiEntropy(c._store, None).summary()
            tombstone_delta = await AntiEntropy(a._store, None).delta_for(
                set(stale_summary["op_ids"])
            )
            await c.receive_ops(tombstone_delta)
            replay_counts = [
                await service.receive_ops([created]) for service in (a, b, c)
            ]
            deleted_states = [
                await service._store.get_state(forgotten_entity)
                for service in (a, b, c)
            ]
            deleted_before_gc = all(
                state is not None and state.tombstone for state in deleted_states
            )
            await a.acknowledge(identities[1].id, [tombstone.op_id], now=NOW + 5)
            gc = TombstoneGC(a._store, retention_seconds=0)
            premature_gc = await gc.collect(now=NOW + 5)
            await a.acknowledge(identities[2].id, [tombstone.op_id], now=NOW + 5)
            final_gc = await gc.collect(now=NOW + 5)
            replay_after_gc = await a.receive_ops([created])
            scenarios.append(
                {
                    "id": "offline-forget-no-resurrection",
                    "passed": (
                        [operation.op_id for operation in tombstone_delta]
                        == [tombstone.op_id]
                        and replay_counts == [0, 0, 0]
                        and deleted_before_gc
                        and premature_gc == []
                        and final_gc == [forgotten_entity]
                        and replay_after_gc == 0
                        and await a._store.get_state(forgotten_entity) is None
                    ),
                    "tombstone_digest": _digest(tombstone.model_dump(mode="json")),
                    "active_peer_ack_count": 2,
                }
            )

            private_rejected = False
            try:
                await a.record_local(
                    "evidence:private",
                    {"value": "must-not-sync"},
                    "user:alice",
                    now=NOW + 6,
                )
            except ScopeNotShareable:
                private_rejected = True
            private_present = any(
                operation.entity == "evidence:private"
                for operation in await a._store.list_ops()
            )
            scenarios.append(
                {
                    "id": "private-scope-never-enters-oplog",
                    "passed": private_rejected and not private_present,
                }
            )

            final_entities = [concurrent_entity, offline_entity, forgotten_entity]
            node_summaries = []
            for identity, service in zip(identities, (a, b, c), strict=True):
                summary = await AntiEntropy(service._store, None).summary()
                node_summaries.append(
                    {
                        "logical_node": identity.name,
                        "device_id_digest": _digest(identity.id),
                        "oplog_digest": summary["digest"],
                        "op_count": len(summary["op_ids"]),
                        "logical_view_digest": await _logical_view_digest(
                            service, final_entities
                        ),
                    }
                )
            passed = all(scenario["passed"] for scenario in scenarios)
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "passed" if passed else "failed",
                "release_commit": release_commit,
                "product_version": (root / "VERSION").read_text(encoding="utf-8").strip(),
                "generated_at": generated_at,
                "evidence_class": "single-process-three-database-protocol-simulation",
                "final_device_evidence": False,
                "limitations": [
                    "does-not-prove-three-physical-devices",
                    "does-not-measure-lan-or-mtls-performance",
                    "must-not-satisfy-final-N-01-through-N-08-alone",
                ],
                "topology": {
                    "logical_nodes": 3,
                    "processes": 1,
                    "isolated_databases": 3,
                    "trust_edges": 3,
                    "domain": DOMAIN,
                },
                "scenarios": scenarios,
                "nodes": node_summaries,
            }
        finally:
            for _, _, db in nodes:
                await db.close()


def _git_commit(root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()


def _timestamp() -> int:
    value = os.environ.get("SOURCE_DATE_EPOCH")
    return int(value) if value is not None else int(time.time())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    if output.exists() and not args.overwrite:
        print("sync evidence error: output already exists", file=sys.stderr)
        return 2
    try:
        report = asyncio.run(
            run_three_node_protocol_evidence(
                root,
                release_commit=_git_commit(root),
                generated_at=_timestamp(),
            )
        )
    except Exception as exc:
        print(
            f"sync evidence error: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("w" if args.overwrite else "x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
    except FileExistsError:
        print("sync evidence error: output already exists", file=sys.stderr)
        return 2
    print(json.dumps({"status": report["status"], "output": str(output)}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
