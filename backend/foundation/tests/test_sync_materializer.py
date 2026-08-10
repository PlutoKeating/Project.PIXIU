"""CRDT materialization into the local query repositories."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite
import pytest

from backend.foundation.core.models import (
    Evidence,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeStatus,
    SourceType,
)
from backend.foundation.storage.repository import (
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


async def _node(root: Path, filename: str, name: str, *, materialize: bool):
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
        materializer = FoundationMaterializer(
            evidence_repo=SqliteEvidenceRepo(db),
            knowledge_repo=SqliteKnowledgeRepo(db),
            preference_repo=SqlitePreferenceRepo(db),
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
