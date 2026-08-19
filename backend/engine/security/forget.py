"""Natural-language forget — scoped match, score ranking, Knowledge soft-delete only."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from backend.foundation.core.models import KnowledgeItem, KnowledgeStatus
from backend.foundation.core.repository import EntityRepository, KnowledgeRepository

from backend.engine.security.models import ForgetResult

_FORGET_VERBS = ("忘记", "删除", "移除", "忘掉", "清除")
_STOPWORDS = frozenset(
    {
        "那张",
        "那个",
        "一下",
        "吧",
        "的",
        "了",
        "请",
        "帮我",
        "请帮我",
        "帮忙",
        "记录",
    }
)
_PREFIX_STOPWORDS = ("一下",)
_SCORE_WEIGHTS = {
    "title_token": 3.0,
    "body_token": 1.0,
    "title_exact": 10.0,
}
_MIN_MATCH_SCORE = 3.0
_MONTH_IN_TEXT = re.compile(r"([0-9一二三四五六七八九十]+)月份")
_CJK_PART = re.compile(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+")
_CJK_SUBTOKEN = re.compile(
    r"([0-9一二三四五六七八九十]+月(?:份)?)|([\u4e00-\u9fff]{2,})"
)
_CN_DIGIT = {
    "一": "1",
    "二": "2",
    "三": "3",
    "四": "4",
    "五": "5",
    "六": "6",
    "七": "7",
    "八": "8",
    "九": "9",
    "十": "10",
    "十一": "11",
    "十二": "12",
}


@dataclass(frozen=True)
class _ScoredTarget:
    item: KnowledgeItem
    score: float
    confidence: float


class ForgetEngine:
    async def forget(
        self,
        command: str,
        *,
        scope: str,
        confirm: bool,
        knw_repo: KnowledgeRepository,
        entity_repo: EntityRepository,
    ) -> ForgetResult:
        normalized_scope = scope.strip()
        if not normalized_scope:
            raise ValueError("scope must be a non-empty string")

        tokens = self._tokens(command)
        active = await knw_repo.list_active()
        scoped = [item for item in active if item.scope == normalized_scope]

        scored = [
            result
            for item in scoped
            if (result := self._score_item(item, tokens, command)) is not None
        ]
        scored.sort(key=lambda entry: (-entry.score, entry.item.title))

        target_payload = [
            {
                "type": "knowledge",
                "id": entry.item.id,
                "title": entry.item.title,
                "score": round(entry.score, 4),
                "confidence": round(entry.confidence, 4),
            }
            for entry in scored
        ]

        # Preview counts only — Engine does not physically delete evidence/relations.
        cascade_preview = await self._preview_cascade(scored, entity_repo)

        if not confirm:
            return ForgetResult(
                status="pending",
                targets=target_payload,
                cascade_preview=cascade_preview,
                irreversible=True,
            )

        forgotten_ids: list[str] = []
        for entry in scored:
            await knw_repo.update_status(entry.item.id, KnowledgeStatus.FORGOTTEN)
            forgotten_ids.append(entry.item.id)
            forgotten_ids.extend(entry.item.evidence_ids)

        return ForgetResult(
            status="forgotten",
            targets=target_payload,
            forgotten_ids=list(dict.fromkeys(forgotten_ids)),
            cascade_preview=cascade_preview,
            irreversible=True,
        )

    async def _preview_cascade(
        self,
        scored: list[_ScoredTarget],
        entity_repo: EntityRepository,
    ) -> dict[str, int]:
        evidence_ids: set[str] = set()
        for entry in scored:
            evidence_ids.update(entry.item.evidence_ids)

        relations = await entity_repo.list_relations()
        related_rel_count = 0
        for entry in scored:
            for name in entry.item.entities:
                ent = await entity_repo.find_entity_by_name(name)
                if ent is not None:
                    related_rel_count += sum(
                        1
                        for rel in relations
                        if rel.src == ent.id or rel.dst == ent.id
                    )
        return {
            "evidence_count": len(evidence_ids),
            "relation_count": related_rel_count,
        }

    def _tokens(self, command: str) -> list[str]:
        text = command.strip()
        for verb in _FORGET_VERBS:
            text = text.replace(verb, " ")
        parts = _CJK_PART.findall(text)
        tokens: list[str] = []
        seen: set[str] = set()
        for part in parts:
            for piece in self._split_part(part):
                piece = self._strip_prefix_stopwords(piece)
                if not piece or piece in _STOPWORDS:
                    continue
                normalized = self._normalize_month_token(piece)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                tokens.append(normalized)
        return tokens

    def _split_part(self, part: str) -> list[str]:
        if not re.fullmatch(r"[\u4e00-\u9fff]+", part):
            return [part]
        pieces: list[str] = []
        for segment in part.split("的"):
            segment = segment.strip()
            if not segment:
                continue
            pieces.extend(self._split_cjk_segment(segment))
        return pieces or [part]

    def _split_cjk_segment(self, segment: str) -> list[str]:
        pieces: list[str] = []
        idx = 0
        for match in _CJK_SUBTOKEN.finditer(segment):
            if match.start() > idx:
                leftover = segment[idx : match.start()]
                if leftover:
                    pieces.append(leftover)
            piece = match.group(1) or match.group(2)
            if piece:
                pieces.append(piece)
            idx = match.end()
        if idx < len(segment):
            pieces.append(segment[idx:])
        return pieces or [segment]

    @staticmethod
    def _strip_prefix_stopwords(piece: str) -> str:
        updated = piece
        changed = True
        while changed:
            changed = False
            for prefix in _PREFIX_STOPWORDS:
                if updated.startswith(prefix):
                    updated = updated[len(prefix) :]
                    changed = True
        return updated.strip()

    @staticmethod
    def _normalize_month_token(token: str) -> str:
        match = re.fullmatch(r"([0-9一二三四五六七八九十]+)月份?", token)
        if match:
            return f"{match.group(1)}月"
        return token

    @staticmethod
    def _normalize_haystack(text: str) -> str:
        return _MONTH_IN_TEXT.sub(r"\1月", text).lower()

    @staticmethod
    def _token_variants(token: str) -> list[str]:
        normalized = ForgetEngine._normalize_haystack(token)
        variants = {normalized}
        month_match = re.fullmatch(r"([0-9一二三四五六七八九十]+)月", token)
        if month_match:
            prefix = month_match.group(1)
            if prefix.isdigit():
                variants.add(f"{prefix}月")
            elif prefix in _CN_DIGIT:
                variants.add(f"{_CN_DIGIT[prefix]}月")
                variants.add(f"{prefix}月")
        return list(variants)

    def _score_item(
        self,
        item: KnowledgeItem,
        tokens: list[str],
        command: str,
    ) -> _ScoredTarget | None:
        if not tokens:
            return None

        title = self._normalize_haystack(self._normalize_month_token(item.title))
        body_text = self._normalize_haystack(self._body_text(item.body))
        normalized_command = self._normalize_haystack(self._normalize_month_token(command))

        score = 0.0
        for token in tokens:
            for needle in self._token_variants(token):
                if needle in title:
                    score += _SCORE_WEIGHTS["title_token"]
                    break
            for needle in self._token_variants(token):
                if needle in body_text:
                    score += _SCORE_WEIGHTS["body_token"]
                    break

        if title and title in normalized_command:
            score += _SCORE_WEIGHTS["title_exact"]

        if score < _MIN_MATCH_SCORE:
            return None

        max_score = len(tokens) * _SCORE_WEIGHTS["title_token"] + _SCORE_WEIGHTS["title_exact"]
        confidence = min(1.0, score / max(max_score, 1.0))
        return _ScoredTarget(item=item, score=score, confidence=confidence)

    @staticmethod
    def _body_text(body: dict[str, Any]) -> str:
        if not body:
            return ""
        return json.dumps(body, ensure_ascii=False, default=str)
