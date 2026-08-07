"""preference/ —— 偏好动态捕捉与版本化。

对外暴露 PreferenceService。
"""

from __future__ import annotations

from typing import Optional

from engine.mocks.models import Evidence, Preference, PreferenceSnapshot
from engine.mocks.repository import PreferenceRepository
from engine.preference.adapter import Adapter
from engine.preference.extractor import Extractor
from engine.preference.versioning import to_preference


class PreferenceService:
    def __init__(
        self,
        pref_repo: PreferenceRepository,
        extractor: Optional[Extractor] = None,
        adapter: Optional[Adapter] = None,
    ) -> None:
        self._repo = pref_repo
        self._extractor = extractor or Extractor()
        self._adapter = adapter or Adapter()

    async def extract(self, evidence: Evidence) -> list[Preference]:
        candidates = self._extractor.extract(evidence)
        saved: list[Preference] = []
        for cand in candidates:
            pref = to_preference(
                category=str(cand["category"]),
                key=str(cand["key"]),
                value=dict(cand["value"]),
                confidence=float(cand["confidence"]),
                scope=evidence.scope,
            )
            await self._repo.save(pref)
            # Re-read to get bumped version if repo versioned it
            stored = await self._repo.get(pref.id)
            saved.append(stored if stored is not None else pref)
        return saved

    async def get_history(self, pref_id: str) -> list[PreferenceSnapshot]:
        return await self._repo.get_history(pref_id)


__all__ = ["PreferenceService"]
