"""ingest/ —— 多源数据接入。

对外暴露 IngestionService。V0.1 通过 engine.mocks 注入 Mock Repository。
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from engine.ingest.cleaner import Cleaner
from engine.ingest.connectors import get_connector
from engine.ingest.normalizer import Normalizer
from engine.ingest.quality import Quality
from engine.mocks.models import Evidence
from engine.mocks.repository import EvidenceRepository


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

        # Strip internal helper fields before persistence
        persist_raw = {
            k: v for k, v in normalized.items() if not k.startswith("_")
        }

        evidence = Evidence(
            id=f"evd_{uuid.uuid4().hex[:16]}",
            source_type=source_type,  # type: ignore[arg-type]
            raw=persist_raw,
            quality_score=quality_score,
            sensitivity=max(0, min(3, int(sensitivity))),
            scope=scope,
            created_at=int(time.time()),
        )
        await self._repo.save(evidence)
        return evidence


__all__ = ["IngestionService"]
