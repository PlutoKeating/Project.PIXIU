"""检索路由 — 意图分类 + 实体抽取 + 通道选择。

在线零 LLM：全部基于规则与词汇匹配。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ─── 意图 ────────────────────────────────────────────────

_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "WORKFLOW_LOOKUP": ("步骤", "流程", "怎么", "如何", "操作", "做法", "顺序"),
    "TEMPLATE_LOOKUP": ("模板", "格式", "范本", "样例"),
}

_ALL_CHANNELS = ("bm25", "ann", "graph")


@dataclass
class QueryIntent:
    """检索意图与通道选择结果。"""

    intent: str = "FACT_RETRIEVAL"
    entities: list[str] = field(default_factory=list)
    channels: tuple[str, ...] = _ALL_CHANNELS


def classify_intent(text: str) -> str:
    """按关键词规则分类意图。

    - WORKFLOW_LOOKUP：含流程/步骤类词
    - TEMPLATE_LOOKUP：含模板/格式类词
    - 其余默认 FACT_RETRIEVAL
    """
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return intent
    return "FACT_RETRIEVAL"


def select_channels(intent: str) -> tuple[str, ...]:
    """通道选择：事实检索三通道全开；流程/模板检索以 BM25 为主。"""
    if intent == "FACT_RETRIEVAL":
        return _ALL_CHANNELS
    return ("bm25", "graph")


def extract_entities(text: str, entity_names: list[str]) -> list[str]:
    """从查询文本中抽取已知实体（子串匹配）。

    实体数量少（端侧），全量做子串匹配可接受。
    """
    hits: list[str] = []
    for name in entity_names:
        if name and name in text:
            hits.append(name)
    return hits


def route(text: str, entity_names: list[str] | None = None) -> QueryIntent:
    """路由入口：意图 → 实体 → 通道。"""
    intent = classify_intent(text)
    entities = extract_entities(text, entity_names or [])
    return QueryIntent(intent=intent, entities=entities, channels=select_channels(intent))
