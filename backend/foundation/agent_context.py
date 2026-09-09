"""Budgeted, cited memory context for an OS Agent turn."""

from __future__ import annotations

import json
import time
from typing import Any

from .core.models import ConflictResolution, KnowledgeItem
from .core.repository import ConflictRepository, EvidenceRepository
from .retrieval import RetrievalService


class AgentContextService:
    """Assemble safe retrieval candidates into a prompt-ready context block."""

    def __init__(
        self,
        retrieval: RetrievalService,
        evidence_repo: EvidenceRepository,
        conflict_repo: ConflictRepository,
        preference_repo=None,
    ) -> None:
        self._retrieval = retrieval
        self._evidence_repo = evidence_repo
        self._conflict_repo = conflict_repo
        self._preference_repo = preference_repo

    async def build(
        self,
        query: str,
        scope: str,
        *,
        session_id: str,
        turn_id: str,
        top_k: int,
        max_chars: int,
        freshness_seconds: int,
        read_scopes: list[str] | None = None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        scopes = read_scopes or [scope]
        candidates = []
        for selected in scopes:
            candidates.extend(await self._retrieval.ranked(query, {"scope": selected, "top_k": top_k}))
        ranked = sorted({item.id: (item, score) for item, score in candidates}.values(),
                        key=lambda pair: pair[1], reverse=True)[:top_k]
        conflicts = await self._conflict_repo.list()
        conflict_by_knowledge: dict[str, str] = {}
        for record in conflicts:
            status = (
                "manual"
                if record.resolution == ConflictResolution.MANUAL
                else "resolved"
            )
            if status == "manual" or record.target_knowledge not in conflict_by_knowledge:
                conflict_by_knowledge[record.target_knowledge] = status

        now = int(time.time())
        context = ""
        preferences = []
        if self._preference_repo is not None:
            for selected in scopes:
                pref = await self._preference_repo.get_by_key("output_style.verbosity", selected)
                if pref is not None and pref.value.get("verbosity") in {"compact", "verbose"}:
                    preferences.append({"id": pref.id, "version": pref.version, "scope": pref.scope,
                                        "key": pref.key, "value": pref.value})
                    style = "简洁回答，先给结论" if pref.value["verbosity"] == "compact" else "详细回答，解释步骤和理由"
                    context = ("用户已保存的输出偏好：" + style + "。本轮明确要求优先。")[:max_chars]
                    break
        items: list[dict[str, Any]] = []
        truncated = False
        for item, score in ranked:
            evidence = await self._evidence_for(item)
            if not evidence or any(entry.sensitivity > 0 for entry in evidence):
                continue
            line = self._format_line(item)
            separator = "\n" if context else ""
            remaining = max_chars - len(context) - len(separator)
            if remaining <= 0:
                truncated = True
                break
            rendered = line[:remaining]
            if len(rendered) < len(line):
                truncated = True
            context += separator + rendered
            items.append(
                {
                    "knowledge_id": item.id,
                    "version": item.version,
                    "title": item.title,
                    "scope": item.scope,
                    "evidence_ids": [entry.id for entry in evidence],
                    "confidence": max(0.0, min(1.0, score)),
                    "updated_at": item.updated_at,
                    "freshness": (
                        "fresh"
                        if now - item.updated_at <= freshness_seconds
                        else "stale"
                    ),
                    "conflict_status": conflict_by_knowledge.get(item.id, "none"),
                }
            )
            if truncated:
                break

        return {
            "preferences": preferences,
            "read_scopes": scopes,
            "session_id": session_id,
            "turn_id": turn_id,
            "context": context,
            "items": items,
            "truncated": truncated,
            "latency_ms": int((time.monotonic() - started) * 1000),
        }

    async def _evidence_for(self, item: KnowledgeItem):
        if not item.evidence_ids:
            return []
        return await self._evidence_repo.get_many(item.evidence_ids)

    @staticmethod
    def _format_line(item: KnowledgeItem) -> str:
        body = json.dumps(
            item.body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        evidence = ",".join(item.evidence_ids) or "none"
        return f"- {item.title}: {body} [knowledge={item.id}; evidence={evidence}]"
