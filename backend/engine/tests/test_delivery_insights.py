"""洞察流生成规则（批次④ B4-1）：最近 24h / quality 降序 / 敏感过滤 / MANUAL 抑制。

对齐 docs/compose/specs/2026-08-29-batch4-delivery-layer-design.md [S2.1]：
  - 候选：最近 24h 入库的 ACTIVE knowledge（按 quality_score 降序）；
  - 过滤：sensitivity>0 不出现；
  - 抑制：任一 source=sync 的 MANUAL 冲突待处理时不递送（本服务对全部 MANUAL
    冲突待处理抑制，避免干扰人工裁决）；
  - summary 服务端生成（title + body.text 前 60 字），不含敏感原文。
"""

from __future__ import annotations

import time

import pytest

from backend.engine.delivery.insights import DeliveryInsightsService, _summarize
from backend.foundation.core.models import ConflictResolution

_NOW = int(time.time())


class _Item:
    """模拟 KnowledgeItem（附带质量/敏感度字段；真实模型无此字段时走证据解析路径）。"""

    def __init__(
        self,
        kid: str,
        title: str,
        quality: float,
        created_at: int,
        sensitivity: int = 0,
        scope: str = "user:local",
        evidence_ids: list[str] | None = None,
    ) -> None:
        self.id = kid
        self.title = title
        self.body = {"text": "正文" + title}
        self.quality_score = quality
        self.sensitivity = sensitivity
        self.created_at = created_at
        self.scope = scope
        self.evidence_ids = evidence_ids or []


class _Conflict:
    def __init__(self, resolution) -> None:
        self.resolution = resolution


class _FakeKnowledgeRepo:
    """模拟 KnowledgeRepository.list_recent（窗口/scope 过滤在内存模拟）。"""

    def __init__(self, items) -> None:
        self.items = items
        self.calls: list[tuple] = []

    async def list_recent(self, scope, since_ts=None, limit=50):
        self.calls.append((scope, since_ts, limit))
        out = [i for i in self.items if i.scope == scope]
        if since_ts is not None:
            out = [i for i in out if i.created_at >= since_ts]
        if limit is not None:
            out = out[:limit]
        return list(out)


class _FakeConflictRepo:
    def __init__(self, records=None) -> None:
        self.records = list(records or [])

    async def list(self):
        return list(self.records)


class _FakeEvidenceRepo:
    def __init__(self, by_id) -> None:
        self.by_id = by_id
        self.get_many_calls: list[list[str]] = []

    async def get_many(self, ids: list[str]):
        self.get_many_calls.append(list(ids))
        return [self.by_id[i] for i in ids if i in self.by_id]


def _service(items, conflicts=(), evidence_repo=None) -> DeliveryInsightsService:
    return DeliveryInsightsService(
        _FakeKnowledgeRepo(items),
        _FakeConflictRepo(conflicts),
        evidence_repo=evidence_repo,
    )


def _item(kid: str, title: str, quality: float, created_at: int, **kw) -> _Item:
    return _Item(kid, title, quality, created_at, **kw)


def _evd(eid: str, quality: float, sensitivity: int = 0):
    """模拟 Evidence（真实模型含 id/quality_score/sensitivity，见 core/models.py）。"""
    return type(
        "E", (), {"id": eid, "quality_score": quality, "sensitivity": sensitivity}
    )()


@pytest.mark.asyncio
async def test_insights_sorted_by_quality_recent():
    svc = _service([_item("k1", "A", 0.3, _NOW), _item("k2", "B", 0.9, _NOW)])
    out = await svc.insights("user:local", limit=3)
    assert [i["knowledge_id"] for i in out] == ["k2", "k1"]
    assert out[0]["kind"] == "recent"
    assert out[0]["score"] == 0.9
    assert out[0]["title"] == "B"


@pytest.mark.asyncio
async def test_insights_excludes_sensitive():
    svc = _service(
        [
            _item("k1", "A", 0.9, _NOW, sensitivity=2),
            _item("k2", "B", 0.5, _NOW),
        ]
    )
    out = await svc.insights("user:local")
    assert [i["knowledge_id"] for i in out] == ["k2"]


@pytest.mark.asyncio
async def test_insights_suppressed_when_manual_conflict_pending():
    svc = _service(
        [_item("k1", "A", 0.9, _NOW)],
        conflicts=[_Conflict(ConflictResolution.MANUAL)],
    )
    assert await svc.insights("user:local") == []


@pytest.mark.asyncio
async def test_insights_suppressed_when_manual_conflict_pending_as_str():
    # ConflictRecord.resolution 是 str-Enum，等于 "MANUAL" 字符串
    svc = _service(
        [_item("k1", "A", 0.9, _NOW)],
        conflicts=[_Conflict("MANUAL")],
    )
    assert await svc.insights("user:local") == []


@pytest.mark.asyncio
async def test_insights_not_suppressed_when_auto_resolved():
    svc = _service(
        [_item("k1", "A", 0.9, _NOW)],
        conflicts=[
            _Conflict(ConflictResolution.NEW_WINS),
            _Conflict(ConflictResolution.MERGE),
        ],
    )
    out = await svc.insights("user:local")
    assert [i["knowledge_id"] for i in out] == ["k1"]


@pytest.mark.asyncio
async def test_insights_empty_when_no_items():
    assert await _service([]).insights("user:local") == []


@pytest.mark.asyncio
async def test_insights_filters_by_scope():
    svc = _service(
        [
            _item("k1", "A", 0.9, _NOW, scope="user:alice"),
            _item("k2", "B", 0.8, _NOW, scope="user:local"),
        ]
    )
    out = await svc.insights("user:local")
    assert [i["knowledge_id"] for i in out] == ["k2"]


@pytest.mark.asyncio
async def test_insights_24h_window_excludes_stale():
    svc = _service(
        [
            _item("k1", "A", 0.9, _NOW - 25 * 3600),  # 超出 24h 窗口
            _item("k2", "B", 0.8, _NOW - 1 * 3600),  # 窗口内
        ]
    )
    out = await svc.insights("user:local")
    assert [i["knowledge_id"] for i in out] == ["k2"]


@pytest.mark.asyncio
async def test_insights_respects_limit():
    items = [_item(f"k{i}", str(i), i / 10, _NOW) for i in range(1, 6)]
    out = await _service(items).insights("user:local", limit=2)
    assert [i["knowledge_id"] for i in out] == ["k5", "k4"]


@pytest.mark.asyncio
async def test_insights_summary_uses_title_and_body_text_prefix():
    item = _item("k1", "标题", 0.9, _NOW)
    item.body = {"text": "x" * 100}
    out = await _service([item]).insights("user:local")
    assert out[0]["summary"] == "标题：" + "x" * 60


def test_summarize_title_only_when_no_body_text():
    item = _item("k1", "标题", 0.9, _NOW)
    item.body = {}
    assert _summarize(item) == "标题"


@pytest.mark.asyncio
async def test_insights_resolves_quality_from_linked_evidence():
    """真实数据路径：KnowledgeItem 不携带 quality/sensitivity，从关联 Evidence 解析。"""
    evidence = {
        "e1": _evd("e1", 0.2, 0),
        "e2": _evd("e2", 0.95, 3),
        "e3": _evd("e3", 0.6, 0),
    }
    items = [
        _item("k1", "A", 0.0, _NOW, evidence_ids=["e1"]),
        _item("k2", "B", 0.0, _NOW, evidence_ids=["e2"]),
        _item("k3", "C", 0.0, _NOW, evidence_ids=["e3"]),
    ]
    for it in items:  # 去掉 item 级兜底字段，模拟真实 KnowledgeItem
        delattr(it, "quality_score")
        delattr(it, "sensitivity")
    svc = DeliveryInsightsService(
        _FakeKnowledgeRepo(items),
        _FakeConflictRepo(),
        evidence_repo=_FakeEvidenceRepo(evidence),
    )
    out = await svc.insights("user:local", limit=3)
    # e2 敏感（sensitivity=3）→ 排除；e3(0.6) > e1(0.2)
    assert [i["knowledge_id"] for i in out] == ["k3", "k1"]
    assert out[0]["score"] == 0.6


# ─── B4-1 审查 M3：_summarize 防御分支 ─────────────────────────


@pytest.mark.parametrize(
    "body,expected",
    [
        ({"text": "abc"}, "标题：abc"),
        ({"text": 123}, "标题：123"),  # text 为数字 → str() 归一
        ({"text": 1.5}, "标题：1.5"),
        ({"text": 0}, "标题"),  # 数字 0 为 falsy → 视为无正文
        ({"text": None}, "标题"),
        ({"text": ""}, "标题"),
        ({"text": "  padded  "}, "标题：padded"),  # 前 60 字后 strip
        ({"text": "x" * 100}, "标题：" + "x" * 60),  # 截断前 60 字
        ("plain string", "标题"),  # body 为 str → 非 dict 回退 {}
        (None, "标题"),  # body 为 None → 非 dict 回退 {}
        ([], "标题"),  # body 为 list → 非 dict 回退 {}
    ],
)
def test_summarize_defensive(body, expected):
    item = _item("k1", "标题", 0.9, _NOW)
    item.body = body
    assert _summarize(item) == expected


# ─── B4-1 审查 I1：窗口下沉 + 批量证据 ────────────────────────


@pytest.mark.asyncio
async def test_insights_window_and_scope_pushed_to_repo():
    """窗口/scope 过滤下沉到 list_recent 单条 SQL（不再全量 list_active 后内存过滤）。"""
    svc = _service([_item("k1", "A", 0.9, _NOW)])
    await svc.insights("user:local")
    scope, since, limit = svc._knowledge.calls[0]
    assert scope == "user:local"
    assert abs(since - (int(time.time()) - 24 * 3600)) <= 1
    assert limit is None  # 质量重排需窗口内全量候选，不截断


@pytest.mark.asyncio
async def test_insights_batches_evidence_fetch():
    """证据解析走一次 get_many（IN 批量），替代逐 evidence_id 调 get() 的 N+1。"""
    evidence = {
        "e1": _evd("e1", 0.2, 0),
        "e2": _evd("e2", 0.95, 0),
    }
    items = [
        _item("k1", "A", 0.0, _NOW, evidence_ids=["e1", "e2"]),
        _item("k2", "B", 0.0, _NOW, evidence_ids=["e2"]),
    ]
    for it in items:
        delattr(it, "quality_score")
        delattr(it, "sensitivity")
    ev_repo = _FakeEvidenceRepo(evidence)
    svc = DeliveryInsightsService(
        _FakeKnowledgeRepo(items),
        _FakeConflictRepo(),
        evidence_repo=ev_repo,
    )
    out = await svc.insights("user:local", limit=3)
    assert len(ev_repo.get_many_calls) == 1  # 只一次批量取
    assert sorted(ev_repo.get_many_calls[0]) == ["e1", "e2"]  # 全部 id 一次取回
    assert out[0]["knowledge_id"] == "k1"
    assert out[0]["score"] == 0.95  # 多条证据取 quality 最大值


@pytest.mark.asyncio
async def test_insights_missing_evidence_tolerated():
    """关联证据已删除/缺失 → 按 0 质量分兜底，不抛异常。"""
    items = [_item("k1", "A", 0.0, _NOW, evidence_ids=["missing"])]
    for it in items:
        delattr(it, "quality_score")
        delattr(it, "sensitivity")
    svc = DeliveryInsightsService(
        _FakeKnowledgeRepo(items),
        _FakeConflictRepo(),
        evidence_repo=_FakeEvidenceRepo({}),
    )
    out = await svc.insights("user:local")
    assert out[0]["knowledge_id"] == "k1"
    assert out[0]["score"] == 0.0


@pytest.mark.asyncio
async def test_insights_quality_takes_max_over_multiple_evidence():
    items = [_item("k1", "A", 0.0, _NOW, evidence_ids=["e1", "e2"])]
    for it in items:
        delattr(it, "quality_score")
        delattr(it, "sensitivity")
    svc = DeliveryInsightsService(
        _FakeKnowledgeRepo(items),
        _FakeConflictRepo(),
        evidence_repo=_FakeEvidenceRepo(
            {
                "e1": _evd("e1", 0.2, 0),
                "e2": _evd("e2", 0.9, 0),
            }
        ),
    )
    out = await svc.insights("user:local")
    assert out[0]["score"] == 0.9


@pytest.mark.asyncio
async def test_insights_sensitivity_max_filters_out():
    """多条证据中任一 sensitivity>0 → 候选整体过滤（取最差值）。"""
    items = [_item("k1", "A", 0.0, _NOW, evidence_ids=["e1", "e2"])]
    for it in items:
        delattr(it, "quality_score")
        delattr(it, "sensitivity")
    svc = DeliveryInsightsService(
        _FakeKnowledgeRepo(items),
        _FakeConflictRepo(),
        evidence_repo=_FakeEvidenceRepo(
            {
                "e1": _evd("e1", 0.2, 0),
                "e2": _evd("e2", 0.9, 2),
            }
        ),
    )
    assert await svc.insights("user:local") == []
