"""ingest/ —— 多源数据接入。

对外暴露 IngestionService。通过 foundation/core Repository 契约注入仓储实现。
"""

from __future__ import annotations

import time
from typing import Any, Optional

from backend.foundation.core.idgen import gen_evidence_id
from backend.foundation.core.models import AgentProvenance, Evidence
from backend.foundation.core.repository import EvidenceRepository

from backend.engine.ingest.cleaner import Cleaner
from backend.engine.ingest.connectors import get_connector
from backend.engine.ingest.normalizer import Normalizer
from backend.engine.ingest.quality import Quality


class IngestionService:
    """Multi-source ingestion pipeline: Connector → Cleaner → Normalizer → Quality → Evidence."""

    def __init__(
        self,
        evidence_repo: EvidenceRepository,
        cleaner: Optional[Cleaner] = None,
        normalizer: Optional[Normalizer] = None,
        quality: Optional[Quality] = None,
    ) -> None:
        self._repo = evidence_repo
        self._cleaner = cleaner or Cleaner()
        self._normalizer = normalizer or Normalizer()
        self._quality = quality or Quality()

    async def ingest(
        self,
        source_type: str,
        raw: dict[str, Any],
        scope: str,
        *,
        sensitivity: int = 0,
        provenance: AgentProvenance | None = None,
    ) -> Evidence:
        if not isinstance(raw, dict):
            raise TypeError("raw must be a dict")
        if not scope:
            raise ValueError("scope must be a non-empty string")

        connector = get_connector(source_type)
        connected = connector.connect(raw)
        cleaned = self._cleaner.clean(connected)
        normalized = self._normalizer.normalize(cleaned)
        quality_score = self._quality.score(normalized, source_type)

        # Promote fingerprint out of the internal "_" namespace so it survives strip.
        persist_raw = {
            k: v for k, v in normalized.items() if not k.startswith("_")
        }
        content_hash = normalized.get("_content_hash")
        if isinstance(content_hash, str) and content_hash:
            persist_raw["content_hash"] = content_hash

        evidence = Evidence(
            id=gen_evidence_id(),
            source_type=source_type,
            raw=persist_raw,
            quality_score=quality_score,
            sensitivity=max(0, min(3, int(sensitivity))),
            provenance=provenance,
            scope=scope,
            created_at=int(time.time()),
        )
        await self._repo.save(evidence)
        return evidence


__all__ = ["IngestionService"]
