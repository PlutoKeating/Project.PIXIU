"""轻量重排 — 词面重叠 + 符号化时间信号（在线零 LLM 约束下不引入神经网络 reranker）。

时间增强属于“神经-符号混合检索”的符号通道：从查询中解析显式年/月表述，
与知识条目的结构化业务日期比对后加权。中文 trigram 分词无法桥接
“3月的家庭支出清单”与标题“2026年3月…”的邻接断裂，该通道补足这一缺口。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from backend.foundation.core.models import KnowledgeItem

from .fuse import _item_timestamps

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")

# 匹配 “2026年3月” / “3月份”；年份可缺省。
_YEAR_MONTH_RE = re.compile(r"(?:(\d{4})\s*年)?\s*(\d{1,2})\s*月")

# 权重与词面重叠（0~1）同量级：命中月为强信号，仅命中年为弱信号。
MONTH_MATCH_WEIGHT = 1.0
YEAR_MATCH_WEIGHT = 0.3


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text or ""))


def _query_temporal(query: str) -> list[tuple[int | None, int]]:
    """提取查询中的 (year|None, month) 表述；非法月份忽略。"""
    hints: list[tuple[int | None, int]] = []
    for match in _YEAR_MONTH_RE.finditer(query or ""):
        year = int(match.group(1)) if match.group(1) else None
        month = int(match.group(2))
        if 1 <= month <= 12:
            hints.append((year, month))
    return hints


def temporal_score(query: str, item: KnowledgeItem) -> float:
    """查询时间表述与知识业务日期的匹配得分（0 / 0.3 / 1.0）。"""
    hints = _query_temporal(query)
    if not hints:
        return 0.0
    best = 0.0
    for timestamp in _item_timestamps(item):
        moment = datetime.fromtimestamp(timestamp, timezone.utc)
        for year, month in hints:
            if moment.month == month and (year is None or moment.year == year):
                best = max(best, MONTH_MATCH_WEIGHT)
            elif year is not None and moment.year == year:
                best = max(best, YEAR_MATCH_WEIGHT)
    return best


def overlap_score(query: str, item: KnowledgeItem) -> float:
    """查询词与 标题+正文 的词面重叠率。"""
    q_tokens = _tokens(query)
    item_text = f"{item.title} {_flatten_text(item.body)}"
    item_tokens = _tokens(item_text)
    if not q_tokens or not item_tokens:
        return 0.0
    return len(q_tokens & item_tokens) / len(q_tokens)


def _flatten_text(obj: Any) -> str:
    """把 body 的所有字符串值拼接，供词面匹配使用。"""
    parts: list[str] = []
    if isinstance(obj, str):
        parts.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            parts.append(_flatten_text(value))
    elif isinstance(obj, list):
        for value in obj:
            parts.append(_flatten_text(value))
    return " ".join(parts)


def rerank(
    candidates: list[tuple[KnowledgeItem, float]],
    query: str,
) -> list[tuple[KnowledgeItem, float]]:
    """在融合分数基础上叠加词面重叠与时间信号微调，返回重排后列表。"""
    adjusted = [
        (item, score + overlap_score(query, item) + temporal_score(query, item))
        for item, score in candidates
    ]
    adjusted.sort(key=lambda t: t[1], reverse=True)
    return adjusted
