"""BM25 全文检索通道 — 基于 FTS5（trigram 分词）。

调用 KnowledgeRepository.search_fts，过滤 ACTIVE 状态（遗忘/被取代
知识不参与检索，与引擎语义对齐）。

⚠️ trigram 限制：长查询串会被 FTS5 按 AND 语义匹配所有 trigram，
整句查询几乎必然 0 命中。因此本通道对 CJK 查询提供滑动窗口回退：
直接 MATCH 无命中时，按 4 字窗口（步长 2）逐个检索并合并。
"""

from __future__ import annotations

import re

from backend.foundation.core.models import KnowledgeItem, KnowledgeStatus
from backend.foundation.core.repository import KnowledgeRepository

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]{3,}")
_WINDOW_SIZE = 4
_WINDOW_STEP = 2
_MAX_WINDOWS = 6


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
    return windows[: _MAX_WINDOWS]


class BM25Channel:
    """FTS5 全文检索通道。"""

    def __init__(self, knw_repo: KnowledgeRepository) -> None:
        self._knw_repo = knw_repo

    async def search(self, query: str, limit: int = 20) -> list[tuple[KnowledgeItem, float]]:
        """返回 [(KnowledgeItem, score)]，按命中权重降序。"""
        results = await self._knw_repo.search_fts(query, limit=limit)

        # 长句查询回退：滑动窗口逐个检索，首个命中窗口权重最高
        if not results:
            windows = _cjk_windows(query)
            if windows:
                results = []
                for window in windows:
                    hit = await self._knw_repo.search_fts(window, limit=limit)
                    if hit:
                        results.extend(hit)
                # 去重保序（保持第一个窗口的排序）
                seen: set[str] = set()
                deduped: list[KnowledgeItem] = []
                for item in results:
                    if item.id not in seen:
                        seen.add(item.id)
                        deduped.append(item)
                results = deduped[:limit]

        scored: list[tuple[KnowledgeItem, float]] = []
        for rank, item in enumerate(results):
            if item.status != KnowledgeStatus.ACTIVE:
                continue
            score = 1.0 / (rank + 1)
            scored.append((item, score))
        return scored
