"""preference/ —— 偏好动态捕捉与版本化。

对外暴露 PreferenceService。
resolve 为 engine-only：scope+key 走 get_by_key，或调用方传入已有列表。
列出某 scope 下全部偏好需要 Foundation list_by_scope，本次不做。
"""

from __future__ import annotations

from typing import Any, Optional

from backend.foundation.core.models import Evidence, Preference, PreferenceSnapshot
from backend.foundation.core.repository import PreferenceRepository

from backend.engine.preference.adapter import Adapter
from backend.engine.preference.extractor import Extractor
from backend.engine.preference.rules import is_opposite_verbosity
from backend.engine.preference.versioning import to_preference


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
            # Compare with the stored row when the contract allows it.
            # Identical values still go through save(): version+1 / history is
            # PreferenceRepository.save semantics (Foundation). Skipping save
            # on equal value is a later product policy, not this Engine-only change.
            existing = await self._repo.get_by_key(pref.key, pref.scope)
            if existing is not None:
                _observe_update(existing.value, pref.value)

            saved_id = await self._repo.save(pref)
            stored = await self._repo.get(saved_id)
            saved.append(stored if stored is not None else pref)
        return saved

    async def get_history(self, pref_id: str) -> list[PreferenceSnapshot]:
        return await self._repo.get_history(pref_id)

    async def resolve(
        self,
        scope: str,
        key: str | None = None,
        preferences: list[Preference] | None = None,
    ) -> list[Preference]:
        """Resolve the effective preference for a scope (optional key).

        - ``preferences``: caller-supplied list, filtered by Adapter (scope / key /
          highest version).
        - ``key`` without a list: load via ``get_by_key`` (existing contract).
        - neither: not supported — listing a whole scope needs Foundation
          ``list_by_scope``, which is out of this Engine-only change.
        """
        if preferences is not None:
            return self._adapter.resolve(preferences, scope=scope, key=key)
        if key is None:
            raise ValueError(
                "PreferenceService.resolve requires key= or a preferences list; "
                "listing all preferences in a scope needs Foundation list_by_scope"
            )
        found = await self._repo.get_by_key(key, scope)
        if found is None:
            return []
        return self._adapter.resolve([found], scope=scope, key=key)


def _observe_update(old_value: dict[str, Any], new_value: dict[str, Any]) -> None:
    """Engine-side classification only; persistence is always repo.save."""
    if old_value == new_value:
        return
    if is_opposite_verbosity(old_value, new_value):
        # Reverse style (compact vs verbose): keep history via Foundation save.
        # Do not emit ConflictRecord — preference is not knowledge conflict.
        return


__all__ = ["PreferenceService"]
