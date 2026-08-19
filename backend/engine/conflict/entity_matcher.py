"""EntityMatcher — decide whether two knowledge items share a comparable entity.

ConflictService historically selected candidates by title+scope, which misses
same-entity corrections with different titles and over-matches different
entities that happen to share a title.

This class isolates "same entity" matching so arbitrate() stays small.
EntityRepository is optional: KnowledgeItem.entities stores names, not ids,
and the foundation contract has no list-by-knowledge-id API. When the repo
is injected we resolve names to Entity.id / norm_name; otherwise we match on
normalized names already stored on the item (post-ingest aliases).
"""

from __future__ import annotations

import unicodedata
from typing import Any, Optional

from backend.foundation.core.models import KnowledgeItem
from backend.foundation.core.repository import EntityRepository

# Instance identity keys (generic; not acceptance-sample field names).
# "category" is a classifier, not an instance, so it is excluded here.
_IDENTITY_KEYS = frozenset(
    {
        "vendor",
        "entity",
        "entity_name",
        "org",
        "organization",
        "subject",
        "actor",
        "who",
        "target_entity",
    }
)
_CATEGORY_KEYS = frozenset({"category", "categories", "kind_label"})


def normalize_entity_key(name: str) -> str:
    """Strip / NFKC / casefold so Latin aliases compare; CJK is unchanged."""
    return unicodedata.normalize("NFKC", name).strip().casefold()


def identity_keys() -> frozenset[str]:
    return _IDENTITY_KEYS


def category_keys() -> frozenset[str]:
    return _CATEGORY_KEYS


def collect_string_fields(obj: Any, keys: frozenset[str]) -> set[str]:
    """Collect normalized string values for the given field names, nested."""
    found: set[str] = set()
    _collect_string_fields(obj, keys, found)
    return found


def _collect_string_fields(obj: Any, keys: frozenset[str], found: set[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).casefold() in keys and isinstance(value, str):
                normalized = normalize_entity_key(value)
                if normalized:
                    found.add(normalized)
            else:
                _collect_string_fields(value, keys, found)
    elif isinstance(obj, list):
        for item in obj:
            _collect_string_fields(item, keys, found)


def names_from_relations(item: KnowledgeItem) -> set[str]:
    names: set[str] = set()
    for rel in item.relations:
        if not isinstance(rel, dict):
            continue
        for key in ("from", "to", "src", "dst"):
            raw = rel.get(key)
            if isinstance(raw, str) and raw.strip():
                names.add(normalize_entity_key(raw))
    return names


class EntityMatcher:
    """Match knowledge items by instance-entity overlap; title is fallback only."""

    def __init__(self, entity_repo: Optional[EntityRepository] = None) -> None:
        self._entity_repo = entity_repo

    async def matches(self, left: KnowledgeItem, right: KnowledgeItem) -> bool:
        """True when the pair should enter field-level conflict detection."""
        left_keys = await self.instance_keys(left)
        right_keys = await self.instance_keys(right)
        if left_keys and right_keys:
            return not left_keys.isdisjoint(right_keys)
        if left_keys or right_keys:
            return False
        # Auxiliary signal only: both sides lack instance entities.
        return left.title == right.title

    async def instance_keys(self, item: KnowledgeItem) -> set[str]:
        """Instance-level entity keys (ids / norm names / identity field values).

        Category labels that only appear as classifiers are subtracted so two
        different vendors in the same category do not look like one entity.
        """
        explicit = {
            normalize_entity_key(name) for name in item.entities if str(name).strip()
        }
        from_relations = names_from_relations(item)
        identity = collect_string_fields(item.body, _IDENTITY_KEYS)
        categories = collect_string_fields(item.body, _CATEGORY_KEYS)

        keys = set(identity)
        keys |= explicit - categories
        keys |= from_relations - categories
        keys.discard("")

        if self._entity_repo is None:
            return keys
        return await self._resolve(keys)

    async def _resolve(self, keys: set[str]) -> set[str]:
        repo = self._entity_repo
        if repo is None:
            return keys
        resolved = set(keys)
        for key in list(keys):
            entity = await repo.find_entity_by_name(key)
            if entity is None:
                continue
            resolved.add(entity.id)
            if entity.norm_name:
                resolved.add(normalize_entity_key(entity.norm_name))
            if entity.name:
                resolved.add(normalize_entity_key(entity.name))
        return resolved
