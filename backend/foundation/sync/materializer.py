"""Project CRDT winners into the durable memory repositories."""

from __future__ import annotations

from backend.foundation.core.models import (
    Evidence,
    KnowledgeItem,
    KnowledgeStatus,
    Preference,
)

from .models import SyncRecord, validate_shared_scope


class FoundationMaterializer:
    """Apply supported shared-memory entity types after CRDT convergence."""

    def __init__(
        self,
        *,
        evidence_repo,
        knowledge_repo,
        preference_repo,
    ) -> None:
        self._evidence_repo = evidence_repo
        self._knowledge_repo = knowledge_repo
        self._preference_repo = preference_repo

    async def __call__(self, record: SyncRecord) -> None:
        kind, separator, entity_id = record.entity.partition(":")
        if not separator or not entity_id:
            return
        if record.tombstone:
            if kind == "knowledge":
                await self._knowledge_repo.update_status(
                    entity_id, KnowledgeStatus.FORGOTTEN
                )
            return
        if kind == "evidence":
            evidence = Evidence.model_validate(record.payload)
            validate_shared_scope(evidence.scope)
            if evidence.id != entity_id:
                raise ValueError("evidence sync entity ID does not match payload")
            await self._evidence_repo.save(evidence)
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
            await self._knowledge_repo.save(
                item.model_copy(update={"evidence_ids": available_evidence})
            )
            return
        if kind == "preference":
            preference = Preference.model_validate(record.payload)
            validate_shared_scope(preference.scope)
            if preference.id != entity_id:
                raise ValueError("preference sync entity ID does not match payload")
            await self._preference_repo.save(preference)
