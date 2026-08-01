"""Cross-scene preference adapter (V0.1: scope + key resolution)."""

from __future__ import annotations

from engine.mocks.models import Preference


class Adapter:
    """Resolve which preference applies for a given scope/scene."""

    def resolve(
        self,
        preferences: list[Preference],
        *,
        scope: str,
        key: str | None = None,
    ) -> list[Preference]:
        matched = [p for p in preferences if p.scope == scope]
        if key is not None:
            matched = [p for p in matched if p.key == key]
        # Highest version wins per key
        best: dict[str, Preference] = {}
        for pref in matched:
            cur = best.get(pref.key)
            if cur is None or pref.version >= cur.version:
                best[pref.key] = pref
        return list(best.values())
