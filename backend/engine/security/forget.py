"""Natural-language forget engine — match → cascade mark FORGOTTEN."""

from __future__ import annotations

import re

from backend.foundation.core.models import KnowledgeItem, KnowledgeStatus
from backend.foundation.core.repository import EntityRepository, KnowledgeRepository

from engine.security.models import ForgetResult


class ForgetEngine:
    async def forget(
        self,
        command: str,
        *,
        confirm: bool,
        knw_repo: KnowledgeRepository,
        entity_repo: EntityRepository,
    ) -> ForgetResult:
        tokens = self._tokens(command)
        active = await knw_repo.list_active()
        targets = [item for item in active if self._matches(item, tokens, command)]

        target_payload = [
            {"type": "knowledge", "id": t.id, "title": t.title} for t in targets
        ]
        evidence_ids: set[str] = set()
        for t in targets:
            evidence_ids.update(t.evidence_ids)

        relations = await entity_repo.list_relations()
        related_rel_count = 0
        for t in targets:
            for name in t.entities:
                ent = await entity_repo.find_entity_by_name(name)
                if ent is not None:
                    related_rel_count += sum(
                        1
                        for r in relations
                        if r.src == ent.id or r.dst == ent.id
                    )

        cascade = {
            "evidence_count": len(evidence_ids),
            "relation_count": related_rel_count,
        }

        if not confirm:
            return ForgetResult(
                status="pending",
                targets=target_payload,
                cascade=cascade,
                irreversible=True,
            )

        forgotten_ids: list[str] = []
        for item in targets:
            await knw_repo.update_status(item.id, KnowledgeStatus.FORGOTTEN)
            forgotten_ids.append(item.id)
            forgotten_ids.extend(item.evidence_ids)

        return ForgetResult(
            status="forgotten",
            targets=target_payload,
            forgotten_ids=list(dict.fromkeys(forgotten_ids)),
            cascade=cascade,
            irreversible=True,
        )

    def _tokens(self, command: str) -> list[str]:
        # Keep CJK chunks and alnum words; strip forget verbs
        text = command.strip()
        for verb in ("忘记", "删除", "移除", "忘掉"):
            text = text.replace(verb, " ")
        parts = re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", text)
        stop = {"那张", "那个", "一下", "吧", "的", "了"}
        return [p for p in parts if p not in stop and len(p) >= 1]

    def _matches(self, item: KnowledgeItem, tokens: list[str], command: str) -> bool:
        hay = f"{item.title} {item.body}".lower()
        if not tokens:
            return False
        # All significant tokens should appear in title/body
        hits = sum(1 for t in tokens if t.lower() in hay)
        # Require at least half of tokens, and at least one hit
        return hits >= max(1, (len(tokens) + 1) // 2)
