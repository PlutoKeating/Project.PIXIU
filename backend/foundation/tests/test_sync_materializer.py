"""CRDT materialization into the local query repositories."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite
import pytest

from backend.engine.conflict import ConflictService
from backend.foundation.core.models import (
    ConflictResolution,
    Evidence,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeStatus,
    SourceType,
)
from backend.foundation.storage.repository import (
    SqliteConflictRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
    SqlitePreferenceRepo,
)
from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.sync import (
    InvalidSyncOperation,
    PairingMethod,
    SqliteSyncStore,
    SyncService,
)
from backend.foundation.sync.materializer import FoundationMaterializer

PASSPHRASE = "phase3-materializer-passphrase"
NOW = 2_000_000_000


async def _node(
    root: Path,
    filename: str,
    name: str,
    *,
    materialize: bool,
    semantic_conflicts: bool = False,
):
    path = str(root / filename)
    connection = sqlite3.connect(path)
    init_db_on_connection(connection)
    connection.close()
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    store = SqliteSyncStore(db)
    materializer = None
    if materialize:
        conflict_service = (
            ConflictService(
                knw_repo=SqliteKnowledgeRepo(db),
                conflict_repo=SqliteConflictRepo(db),
            )
            if semantic_conflicts
            else None
        )
        materializer = FoundationMaterializer(
            evidence_repo=SqliteEvidenceRepo(db),
            knowledge_repo=SqliteKnowledgeRepo(db),
            preference_repo=SqlitePreferenceRepo(db),
            conflict_service=conflict_service,
        )
    service = SyncService(
        store,
        device_name=name,
        domain="shared:home",
        key_passphrase=PASSPHRASE,
        materializer=materializer,
    )
    return service, store, db


@pytest.mark.asyncio
async def test_remote_shared_memory_is_materialized_and_tombstoned(tmp_path: Path):
    a, _, db_a = await _node(tmp_path, "a.db", "device-a", materialize=True)
    b, _, db_b = await _node(tmp_path, "b.db", "device-b", materialize=False)
    try:
        await a.pair(
            PairingMethod.QR,
            await b.create_pairing_token(PairingMethod.QR, now=NOW),
            now=NOW,
        )
        await b.pair(
            PairingMethod.QR,
            await a.create_pairing_token(PairingMethod.QR, now=NOW),
            now=NOW,
        )
        evidence = Evidence(
            id="evd_AAAAAAAAAAAAAAAAAAAAAAAAAA",
            source_type=SourceType.OCR,
            raw={"title": "shared expense"},
            quality_score=0.9,
            sensitivity=0,
            scope="shared:home",
            created_at=NOW,
        )
        knowledge = KnowledgeItem(
            id="knw_AAAAAAAAAAAAAAAAAAAAAAAAAA",
            kind=KnowledgeKind.FACT,
            title="shared expense",
            body={"amount": 434.5},
            status=KnowledgeStatus.ACTIVE,
            version=1,
            evidence_ids=[evidence.id],
            scope="shared:home",
            created_at=NOW,
            updated_at=NOW,
        )
        evidence_op = await b.record_local(
            f"evidence:{evidence.id}",
            evidence.model_dump(mode="json"),
            evidence.scope,
            now=NOW,
        )
        knowledge_op = await b.record_local(
            f"knowledge:{knowledge.id}",
            knowledge.model_dump(mode="json"),
            knowledge.scope,
            now=NOW,
        )
        assert await a.receive_ops([evidence_op, knowledge_op]) == 2

        stored_evidence = await SqliteEvidenceRepo(db_a).get(evidence.id)
        stored_knowledge = await SqliteKnowledgeRepo(db_a).get(knowledge.id)
        assert stored_evidence == evidence
        assert stored_knowledge.body == {"amount": 434.5}
        assert stored_knowledge.evidence_ids == [evidence.id]

        tombstone = await b.record_local(
            f"knowledge:{knowledge.id}",
            {},
            knowledge.scope,
            deleted=True,
            now=NOW + 1,
        )
        assert await a.receive_ops([tombstone]) == 1
        assert (
            await SqliteKnowledgeRepo(db_a).get(knowledge.id)
        ).status == KnowledgeStatus.FORGOTTEN
    finally:
        await db_a.close()
        await db_b.close()


@pytest.mark.asyncio
async def test_remote_new_knowledge_runs_semantic_conflict_arbitration(
    tmp_path: Path,
):
    receiver, _, db_receiver = await _node(
        tmp_path,
        "receiver.db",
        "device-receiver",
        materialize=True,
        semantic_conflicts=True,
    )
    sender, _, db_sender = await _node(
        tmp_path, "sender.db", "device-sender", materialize=False
    )
    receiver_knowledge = SqliteKnowledgeRepo(db_receiver)
    try:
        await receiver.pair(
            PairingMethod.QR,
            await sender.create_pairing_token(PairingMethod.QR, now=NOW),
            now=NOW,
        )
        await sender.pair(
            PairingMethod.QR,
            await receiver.create_pairing_token(PairingMethod.QR, now=NOW),
            now=NOW,
        )
        existing = KnowledgeItem(
            id="knw_CCCCCCCCCCCCCCCCCCCCCCCCCC",
            kind=KnowledgeKind.FACT,
            title="energy statement",
            body={"vendor": "AlphaPower", "amount": 210},
            scope="shared:home",
            created_at=NOW,
            updated_at=NOW,
        )
        incoming = KnowledgeItem(
            id="knw_DDDDDDDDDDDDDDDDDDDDDDDDDD",
            kind=KnowledgeKind.FACT,
            title="corrected energy statement",
            body={"vendor": "AlphaPower", "amount": 230},
            scope="shared:home",
            created_at=NOW + 1,
            updated_at=NOW + 1,
        )
        await receiver_knowledge.save(existing)
        operation = await sender.record_local(
            f"knowledge:{incoming.id}",
            incoming.model_dump(mode="json"),
            incoming.scope,
            now=NOW + 1,
        )

        assert await receiver.receive_ops([operation]) == 1

        stored_existing = await receiver_knowledge.get(existing.id)
        stored_incoming = await receiver_knowledge.get(incoming.id)
        records = await SqliteConflictRepo(db_receiver).list()
        assert stored_existing is not None
        assert stored_existing.status == KnowledgeStatus.SUPERSEDED
        assert stored_incoming is not None and stored_incoming.version == 2
        assert len(records) == 1
        assert records[0].resolution == ConflictResolution.NEW_WINS
        assert records[0].source == "sync"
    finally:
        await db_receiver.close()
        await db_sender.close()


@pytest.mark.asyncio
async def test_opposite_delivery_order_converges_semantic_knowledge_views(
    tmp_path: Path,
):
    a, _, db_a = await _node(
        tmp_path, "semantic-a.db", "device-a", materialize=True, semantic_conflicts=True
    )
    b, _, db_b = await _node(
        tmp_path, "semantic-b.db", "device-b", materialize=True, semantic_conflicts=True
    )
    repo_a = SqliteKnowledgeRepo(db_a)
    repo_b = SqliteKnowledgeRepo(db_b)
    try:
        await a.pair(
            PairingMethod.QR,
            await b.create_pairing_token(PairingMethod.QR, now=NOW),
            now=NOW,
        )
        await b.pair(
            PairingMethod.QR,
            await a.create_pairing_token(PairingMethod.QR, now=NOW),
            now=NOW,
        )
        older = KnowledgeItem(
            id="knw_EEEEEEEEEEEEEEEEEEEEEEEEEE",
            kind=KnowledgeKind.FACT,
            title="energy statement",
            body={"vendor": "AlphaPower", "amount": 210},
            scope="shared:home",
            created_at=NOW,
            updated_at=NOW,
        )
        newer = KnowledgeItem(
            id="knw_FFFFFFFFFFFFFFFFFFFFFFFFFF",
            kind=KnowledgeKind.FACT,
            title="corrected energy statement",
            body={"vendor": "AlphaPower", "amount": 230},
            scope="shared:home",
            created_at=NOW + 1,
            updated_at=NOW + 1,
        )
        await repo_a.save(older)
        await repo_b.save(newer)
        op_a = await a.record_local(
            f"knowledge:{older.id}", older.model_dump(mode="json"), older.scope, now=NOW
        )
        op_b = await b.record_local(
            f"knowledge:{newer.id}",
            newer.model_dump(mode="json"),
            newer.scope,
            now=NOW + 1,
        )

        assert await a.receive_ops([op_b]) == 1
        assert await b.receive_ops([op_a]) == 1

        for repo in (repo_a, repo_b):
            stored_older = await repo.get(older.id)
            stored_newer = await repo.get(newer.id)
            assert stored_older is not None
            assert stored_older.status == KnowledgeStatus.SUPERSEDED
            assert stored_newer is not None
            assert stored_newer.status == KnowledgeStatus.ACTIVE
            assert stored_newer.version == 2
            assert stored_newer.body == newer.body
        for db in (db_a, db_b):
            records = await SqliteConflictRepo(db).list()
            assert len(records) == 1
            assert records[0].source == "sync"
            assert records[0].target_knowledge == older.id
    finally:
        await db_a.close()
        await db_b.close()


@pytest.mark.asyncio
async def test_nested_private_scope_is_rejected_before_oplog(tmp_path: Path):
    service, store, db = await _node(
        tmp_path, "scope.db", "device", materialize=False
    )
    try:
        with pytest.raises(InvalidSyncOperation, match="scope"):
            await service.record_local(
                "knowledge:private",
                {"scope": "user:alice", "value": "secret"},
                "shared:home",
            )
        assert await store.list_ops() == []
    finally:
        await db.close()
