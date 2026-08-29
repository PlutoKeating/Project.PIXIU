"""定时简报生成规则（批次④ B4-2）：按日聚合 monitor_log → 中文简报。

对齐 docs/compose/specs/2026-08-29-batch4-delivery-layer-design.md [S2.2]：
  - 按本地时区日边界取当日 monitor_log 事件（跨日不串）；
  - 仅 status == "ingested" 计为「新增记忆」，按 source 分组计数
    （monitor_log source 枚举 directory|clipboard|behavior|screenshot|system，
    无独立「文本」枚举——文本经 ingest_bridge 走 directory，见批次②）；
  - sensitive_quarantined 不计入新增，>0 时单列「敏感内容已隔离」；
  - ignored / state_changed 不计入；
  - summary 服务端生成中文文案，不含任何事件 summary 原文（敏感隔离原则）；
  - 空日 → "当日无新记忆"。
偏好/冲突计数按任务说明简化（MonitorLogStore 不携带偏好/冲突数据；
Produces 接口为 DeliveryDigestService(monitor_log)），不在本服务实现。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from backend.engine.delivery.digest import DeliveryDigestService
from backend.foundation.api.monitor_log import MonitorLogStore


def _ts(y: int, m: int, d: int, hh: int = 12, mm: int = 0, ss: int = 0) -> int:
    """本地时区时间戳（种子正午取点，避开多数 DST 切换时刻的歧义）。

    与 store 的日边界计算（naive datetime.timestamp() 按本地时区解释）同源，
    故断言与运行机时区无关。
    """
    return int(datetime(y, m, d, hh, mm, ss).timestamp())


def _write(store, *, source, status, summary, ts):
    store.write_event(source=source, status=status, summary=summary, ts=ts)


def _service(db_path: str) -> DeliveryDigestService:
    return DeliveryDigestService(monitor_log=MonitorLogStore(db_path))


@pytest.mark.asyncio
async def test_digest_groups_ingested_by_source(tmp_path):
    store = MonitorLogStore(str(tmp_path / "p.db"))
    _write(store, source="directory", status="ingested", summary="记住文件 a.txt", ts=_ts(2026, 8, 29))
    _write(store, source="directory", status="ingested", summary="记住文件 b.txt", ts=_ts(2026, 8, 29))
    _write(store, source="clipboard", status="ingested", summary="记住剪贴板 x", ts=_ts(2026, 8, 29))
    out = await _service(str(tmp_path / "p.db")).digest("2026-08-29")
    assert out == {
        "date": "2026-08-29",
        "summary": "当日新增 3 条记忆（目录 2、剪贴板 1）",
    }


@pytest.mark.asyncio
async def test_digest_lists_only_nonzero_source_groups(tmp_path):
    store = MonitorLogStore(str(tmp_path / "p.db"))
    _write(store, source="directory", status="ingested", summary="d", ts=_ts(2026, 8, 29))
    _write(store, source="clipboard", status="ingested", summary="c1", ts=_ts(2026, 8, 29))
    _write(store, source="clipboard", status="ingested", summary="c2", ts=_ts(2026, 8, 29))
    _write(store, source="behavior", status="ingested", summary="b", ts=_ts(2026, 8, 29))
    _write(store, source="screenshot", status="ingested", summary="s", ts=_ts(2026, 8, 29))
    out = await _service(str(tmp_path / "p.db")).digest("2026-08-29")
    assert out["summary"] == "当日新增 5 条记忆（目录 1、剪贴板 2、行为 1、截屏 1）"


@pytest.mark.asyncio
async def test_digest_unknown_source_not_inflate_total(tmp_path):
    """未登记 source（新增枚举未同步 _SOURCE_LABELS）不膨胀总数、也不进明细。

    total 与渲染组同源自 _SOURCE_LABELS：未知 source 的 ingested 事件不计入
    总数，保证「总数 == 各组之和」不变量不因新 producer 静默破坏。
    """
    store = MonitorLogStore(str(tmp_path / "p.db"))
    _write(store, source="directory", status="ingested", summary="已知源", ts=_ts(2026, 8, 29))
    _write(store, source="future_source", status="ingested", summary="未来新增源", ts=_ts(2026, 8, 29))
    out = await _service(str(tmp_path / "p.db")).digest("2026-08-29")
    assert out["summary"] == "当日新增 1 条记忆（目录 1）"


@pytest.mark.asyncio
async def test_digest_day_filter_no_leak_across_days(tmp_path):
    """日边界：当日 [00:00, 次日 00:00)，前后一日 23:59:59 / 00:00:00 不串。"""
    store = MonitorLogStore(str(tmp_path / "p.db"))
    _write(store, source="directory", status="ingested", summary="前一日末秒", ts=_ts(2026, 8, 28, 23, 59, 59))
    _write(store, source="directory", status="ingested", summary="当日零点", ts=_ts(2026, 8, 29, 0, 0, 0))
    _write(store, source="directory", status="ingested", summary="当日晚间", ts=_ts(2026, 8, 29, 23, 59, 59))
    _write(store, source="directory", status="ingested", summary="次日零点", ts=_ts(2026, 8, 30, 0, 0, 0))
    out = await _service(str(tmp_path / "p.db")).digest("2026-08-29")
    assert out["summary"] == "当日新增 2 条记忆（目录 2）"


@pytest.mark.asyncio
async def test_digest_counts_only_ingested_and_reports_quarantined(tmp_path):
    """ingested 计新增；sensitive_quarantined 单列；ignored/state_changed 不计。"""
    store = MonitorLogStore(str(tmp_path / "p.db"))
    _write(store, source="directory", status="ingested", summary="正常文件", ts=_ts(2026, 8, 29))
    _write(store, source="directory", status="ingested", summary="正常文件2", ts=_ts(2026, 8, 29))
    _write(store, source="clipboard", status="ingested", summary="正常剪贴板", ts=_ts(2026, 8, 29))
    _write(store, source="directory", status="sensitive_quarantined", summary="敏感文件", ts=_ts(2026, 8, 29))
    _write(store, source="directory", status="ignored", summary="忽略的超大文件", ts=_ts(2026, 8, 29))
    _write(store, source="system", status="state_changed", summary="监控已开启", ts=_ts(2026, 8, 29))
    out = await _service(str(tmp_path / "p.db")).digest("2026-08-29")
    assert out["summary"] == "当日新增 3 条记忆（目录 2、剪贴板 1），另有 1 条敏感内容已隔离"


@pytest.mark.asyncio
async def test_digest_empty_day_returns_no_memories(tmp_path):
    out = await _service(str(tmp_path / "p.db")).digest("2026-08-29")
    assert out == {"date": "2026-08-29", "summary": "当日无新记忆"}


@pytest.mark.asyncio
async def test_digest_quarantined_only_day(tmp_path):
    store = MonitorLogStore(str(tmp_path / "p.db"))
    _write(store, source="clipboard", status="sensitive_quarantined", summary="敏感剪贴板", ts=_ts(2026, 8, 29))
    out = await _service(str(tmp_path / "p.db")).digest("2026-08-29")
    assert out["summary"] == "当日无新记忆，另有 1 条敏感内容已隔离"


@pytest.mark.asyncio
async def test_digest_summary_contains_no_raw_event_text(tmp_path):
    """敏感隔离原则：summary 为模板计数，不含任何事件 summary 原文。"""
    store = MonitorLogStore(str(tmp_path / "p.db"))
    raw = "含医保卡号的敏感文件 12345 内容"
    _write(store, source="directory", status="ingested", summary=raw, ts=_ts(2026, 8, 29))
    _write(store, source="clipboard", status="sensitive_quarantined", summary=raw, ts=_ts(2026, 8, 29))
    out = await _service(str(tmp_path / "p.db")).digest("2026-08-29")
    assert raw not in out["summary"]
    assert "12345" not in out["summary"]


@pytest.mark.asyncio
async def test_digest_invalid_date_raises_value_error(tmp_path):
    svc = _service(str(tmp_path / "p.db"))
    with pytest.raises(ValueError):
        await svc.digest("2026-13-01")
    with pytest.raises(ValueError):
        await svc.digest("not-a-date")


@pytest.mark.parametrize(
    "bad",
    [
        "2026-13-01",      # 月越界
        "2026-02-30",      # 无效日历日
        "2026-1-1",        # 非严格两位（strptime 宽松接受，round-trip 收紧）
        "20260829",        # 非分隔格式
        "2026/08/29",      # 错误分隔符
        "not-a-date",      # 非日期
        "",                # 空串
    ],
)
def test_list_events_by_day_invalid_date_raises(tmp_path, bad):
    store = MonitorLogStore(str(tmp_path / "p.db"))
    with pytest.raises(ValueError):
        store.list_events_by_day(bad)


def test_list_events_by_day_returns_day_rows_asc(tmp_path):
    store = MonitorLogStore(str(tmp_path / "p.db"))
    _write(store, source="directory", status="ingested", summary="早", ts=_ts(2026, 8, 29, 8))
    _write(store, source="directory", status="ingested", summary="晚", ts=_ts(2026, 8, 29, 20))
    rows = store.list_events_by_day("2026-08-29")
    assert [r["summary"] for r in rows] == ["早", "晚"]
    assert rows[0]["source"] == "directory"
    assert rows[0]["status"] == "ingested"
    assert isinstance(rows[0]["ts"], int)
    # 邻日不含
    assert store.list_events_by_day("2026-08-28") == []
    assert store.list_events_by_day("2026-08-30") == []
