"""BM25 全文检索通道 — 基于 FTS5（trigram 分词）。

调用 KnowledgeRepository.search_fts，过滤 ACTIVE 状态（遗忘/被取代
知识不参与检索，与引擎语义对齐）。

⚠️ trigram 限制：长查询串会被 FTS5 按 AND 语义匹配所有 trigram，
整句查询几乎必然 0 命中且代价高昂。因此本通道对长查询提供显著词
回退：优先取字母数字串（单号/编号类强区分信号），再按 CJK 4 字
滑动窗口（步长 2）逐个检索并合并。
"""

from __future__ import annotations

import re

from backend.foundation.core.models import KnowledgeItem, KnowledgeStatus
from backend.foundation.core.repository import KnowledgeRepository

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]{3,}")
_ALNUM_RUN = re.compile(r"[A-Za-z0-9_]{3,}")
_WINDOW_SIZE = 4
_WINDOW_STEP = 2
_MAX_WINDOWS = 6
# 超过该长度的查询跳过整句直查（trigram AND 语义下必然 0 命中且昂贵）。
_DIRECT_MATCH_MAX_LEN = 12


def _cjk_windows(text: str) -> list[str]:
    """从查询文本提取 CJK 4 字滑动窗口（覆盖长句查询）。"""
    windows: list[str] = []
    for run in _CJK_RUN.findall(text):
        if len(run) <= _WINDOW_SIZE:
            windows.append(run)
            continue
        for i in range(0, len(run) - _WINDOW_SIZE + 1, _WINDOW_STEP):
            windows.append(run[i : i + _WINDOW_SIZE])
            if len(windows) >= _MAX_WINDOWS:
                return windows
    return windows[:_MAX_WINDOWS]


def _salient_tokens(text: str) -> list[str]:
    """显著词序列：字母数字串（编号/单号）优先，其后为 CJK 滑动窗口。"""
    tokens: list[str] = []
    seen: set[str] = set()
    for run in _ALNUM_RUN.findall(text):
        key = run.casefold()
        if key not in seen:
            seen.add(key)
            tokens.append(run)
    for window in _cjk_windows(text):
        if window not in seen:
            seen.add(window)
            tokens.append(window)
    return tokens


class BM25Channel:
    """FTS5 全文检索通道。"""

    def __init__(self, knw_repo: KnowledgeRepository) -> None:
        self._knw_repo = knw_repo

    async def search(self, query: str, limit: int = 20) -> list[tuple[KnowledgeItem, float]]:
        """返回 [(KnowledgeItem, score)]，按命中权重降序。"""
        results = []
        if len(query or "") <= _DIRECT_MATCH_MAX_LEN:
            results = list(await self._knw_repo.search_fts(query, limit=limit))

        # 长句查询回退：显著词逐个检索（编号类词最先、区分度最高）
        if not results:
            collected: list[KnowledgeItem] = []
            seen: set[str] = set()
            for token in _salient_tokens(query):
                hit = await self._knw_repo.search_fts(token, limit=limit)
                for item in hit:
                    if item.id not in seen:
                        seen.add(item.id)
                        collected.append(item)
                if len(collected) >= limit:
                    break
            results = collected[:limit]

        scored: list[tuple[KnowledgeItem, float]] = []
        for rank, item in enumerate(results):
            if item.status != KnowledgeStatus.ACTIVE:
                continue
            score = 1.0 / (rank + 1)
            scored.append((item, score))
        return scored
