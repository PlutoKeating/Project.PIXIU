"""Project CRDT winners into the durable memory repositories."""

from __future__ import annotations

from backend.foundation.core.models import (
    Evidence,
    KnowledgeItem,
    KnowledgeStatus,
    Preference,
)

from .models import SyncRecord, validate_shared_scope

_PENDING_EVIDENCE_PREFIX = "sync_pending_evidence:"


def _pending_evidence_key(evidence_id: str, knowledge_id: str) -> str:
    return f"{_PENDING_EVIDENCE_PREFIX}{evidence_id}:{knowledge_id}"


class FoundationMaterializer:
    """Apply supported shared-memory entity types after CRDT convergence."""

    def __init__(
        self,
        *,
        evidence_repo,
        knowledge_repo,
        preference_repo,
        conflict_service=None,
        knowledge_service=None,
        sync_store=None,
    ) -> None:
        self._evidence_repo = evidence_repo
        self._knowledge_repo = knowledge_repo
        self._preference_repo = preference_repo
        self._conflict_service = conflict_service
        self._knowledge_service = knowledge_service
        self._sync_store = sync_store

    async def _clear_pending_for_knowledge(self, knowledge_id: str) -> None:
        if self._sync_store is None:
            return
        keys = await self._sync_store.list_meta_keys(_PENDING_EVIDENCE_PREFIX)
        for key in keys:
            if key.endswith(f":{knowledge_id}"):
                await self._sync_store.delete_meta(key)

    async def _resolve_pending_evidence(self, evidence_id: str) -> None:
        if self._sync_store is None:
            return
        prefix = f"{_PENDING_EVIDENCE_PREFIX}{evidence_id}:"
        for key in await self._sync_store.list_meta_keys(prefix):
            knowledge_id = key.removeprefix(prefix)
            item = await self._knowledge_repo.get(knowledge_id)
            if item is not None and item.status == KnowledgeStatus.ACTIVE:
                await self._knowledge_repo.link_evidence(knowledge_id, evidence_id)
            await self._sync_store.delete_meta(key)

    async def __call__(self, record: SyncRecord) -> None:
        kind, separator, entity_id = record.entity.partition(":")
        if not separator or not entity_id:
            return
        if record.tombstone:
            if kind == "knowledge":
                await self._clear_pending_for_knowledge(entity_id)
                if self._knowledge_service is None:
                    await self._knowledge_repo.update_status(
                        entity_id, KnowledgeStatus.FORGOTTEN
                    )
                else:
                    await self._knowledge_service.forget(entity_id)
            return
        if kind == "evidence":
            evidence = Evidence.model_validate(record.payload)
            validate_shared_scope(evidence.scope)
            if evidence.id != entity_id:
                raise ValueError("evidence sync entity ID does not match payload")
            await self._evidence_repo.save(evidence)
            await self._resolve_pending_evidence(evidence.id)
            return
        if kind == "knowledge":
            item = KnowledgeItem.model_validate(record.payload)
            validate_shared_scope(item.scope)
            if item.id != entity_id:
                raise ValueError("knowledge sync entity ID does not match payload")
            available_evidence = [
                evidence_id
                for evidence_id in item.evidence_ids
                if await self._evidence_repo.get(evidence_id) is not None
            ]
            missing_evidence = set(item.evidence_ids) - set(available_evidence)
            if self._sync_store is not None:
                for evidence_id in item.evidence_ids:
                    key = _pending_evidence_key(evidence_id, item.id)
                    if evidence_id in missing_evidence:
                        await self._sync_store.set_meta(key, "1")
                    else:
                        await self._sync_store.delete_meta(key)
            item = item.model_copy(update={"evidence_ids": available_evidence})
            if self._conflict_service is None:
                if self._knowledge_service is None:
                    await self._knowledge_repo.save(item)
                else:
                    await self._knowledge_service.materialize(item)
            else:
                # A first-seen remote entity is a CRDT fast-forward, but it may
                # still contradict another local knowledge ID semantically.
                # Route it through the same engine policy as local writes.
                await self._conflict_service.arbitrate(item, source="sync")
            for evidence_id in missing_evidence:
                if await self._evidence_repo.get(evidence_id) is not None:
                    await self._resolve_pending_evidence(evidence_id)
            return
        if kind == "preference":
            preference = Preference.model_validate(record.payload)
            validate_shared_scope(preference.scope)
            if preference.id != entity_id:
                raise ValueError("preference sync entity ID does not match payload")
            await self._preference_repo.save(preference)
