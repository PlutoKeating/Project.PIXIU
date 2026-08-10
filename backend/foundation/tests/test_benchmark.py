"""Tests for eval/benchmark.py, eval/service.py, eval/report.py — Phase 5."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from backend.foundation.eval import (
    BenchmarkService,
    BenchmarkMetric,
    BenchmarkReport,
    MetricStatus,
    ReportStatus,
    SyncBenchmark,
    SystemBenchmark,
    render_benchmark_markdown,
    write_benchmark_report,
)
from backend.foundation.storage.schema import init_db_on_connection
from backend.foundation.sync import SqliteSyncStore, SyncService

PASSPHRASE = "phase5-benchmark-passphrase"
NOW = 2_000_000_000


async def _node(root: Path, name: str):
    """新建独立节点（service, store, db）。"""
    db_path = str(root / f"{name}.db")
    sync_db = sqlite3.connect(db_path)
    init_db_on_connection(sync_db)
    sync_db.close()
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    store = SqliteSyncStore(db)
    service = SyncService(
        store,
        device_name=name,
        domain="shared:home",
        key_passphrase=PASSPHRASE,
    )
    return service, store, db


def _node_factory(root: Path):
    counter = {"n": 0}

    async def make():
        counter["n"] += 1
        return await _node(root, f"node{counter['n']}")

    return make


# ═══════════════════════════════════════════════════════
# SyncBenchmark
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_sync_benchmark_converges(tmp_path: Path):
    factory = _node_factory(tmp_path)
    rounds, latencies = await SyncBenchmark().run(
        factory, rounds=3, ops_per_round=10, now=NOW
    )

    assert len(rounds) == 3
    assert all(r.converged for r in rounds)
    assert all(r.elapsed_ms >= 0 for r in rounds)
    assert len(latencies) == 3
    assert all(latency >= 0 for latency in latencies)


@pytest.mark.asyncio
async def test_sync_benchmark_records_failure_round(tmp_path: Path):
    """制造失败轮次：节点无法配对时收敛失败且不中断。"""
    factory = _node_factory(tmp_path)
    real_factory = factory
    call_counter = {"n": 0}

    async def failing_round_factory():
        call_counter["n"] += 1
        svc, store, db = await real_factory()
        if call_counter["n"] % 2 == 0:  # 第 2、4…次调用 = B 节点 → 破坏验签
            class NoStore:
                async def get_peer(self, peer_id):
                    return None  # 触发 "operation origin is not trusted"

            svc._store = NoStore()
        return svc, store, db

    rounds, latencies = await SyncBenchmark().run(
        failing_round_factory, rounds=2, ops_per_round=5, now=NOW
    )
    assert any(not r.converged for r in rounds)
    assert any(r.error for r in rounds)


class _FakeDb:
    async def close(self):
        pass


# ═══════════════════════════════════════════════════════
# SystemBenchmark
# ═══════════════════════════════════════════════════════

def test_system_benchmark_measures_resources(tmp_path: Path):
    # 先建一个真实数据库文件
    db_path = str(tmp_path / "sys.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, payload TEXT)")
    conn.execute("INSERT INTO t VALUES (1, 'x' * 1000)")
    conn.commit()
    conn.close()

    metrics = SystemBenchmark().measure(db_path)
    by_name = {m.name: m for m in metrics}
    assert by_name["db_size_bytes"].value is not None
    assert by_name["db_size_bytes"].value > 0
    assert by_name["peak_memory_mb"].value is not None
    assert by_name["peak_memory_mb"].value > 0
    assert by_name["cpu_time_ms"].value is not None
    assert by_name["cpu_time_ms"].value >= 0


def test_system_benchmark_missing_db_reports_zero(tmp_path: Path):
    metrics = SystemBenchmark().measure(str(tmp_path / "nonexistent.db"))
    by_name = {m.name: m for m in metrics}
    assert by_name["db_size_bytes"].value == 0.0


# ═══════════════════════════════════════════════════════
# BenchmarkService.run_all + BenchmarkReport
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_benchmark_service_run_all(tmp_path: Path):
    factory = _node_factory(tmp_path)
    # 先建一个 db 文件供系统测量
    db_path = str(tmp_path / "measure.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    report = await BenchmarkService(timestamp=lambda: 123456).run_all(
        factory,
        db_path=db_path,
        rounds=3,
        ops_per_round=10,
        runtime="stub",
        now=NOW,
    )

    assert report.runtime == "stub"
    assert report.generated_at == 123456
    assert report.overall_status is ReportStatus.PASS
    assert len(report.sync_rounds) == 3

    by_name = {m.name: m for m in report.metrics}
    convergence = by_name["sync_convergence_rate"]
    assert convergence.value == 1.0
    assert convergence.status is MetricStatus.PASS
    assert "sync_latency_p50_ms" in by_name
    assert "sync_latency_p95_ms" in by_name
    assert "db_size_bytes" in by_name
    assert "peak_memory_mb" in by_name
    assert "cpu_time_ms" in by_name


@pytest.mark.asyncio
async def test_benchmark_service_runtime_kylin_label(tmp_path: Path):
    factory = _node_factory(tmp_path)
    report = await BenchmarkService().run_all(
        factory,
        db_path=str(tmp_path / "m.db"),
        rounds=1,
        ops_per_round=5,
        runtime="kylin",
        now=NOW,
    )
    assert report.runtime == "kylin"


# ═══════════════════════════════════════════════════════
# report.py — render + write
# ═══════════════════════════════════════════════════════

def test_benchmark_report_render_and_write(tmp_path: Path):
    report = BenchmarkReport(
        runtime="stub",
        generated_at=123,
        overall_status=ReportStatus.PASS,
        metrics=[
            BenchmarkMetric(
                name="sync_convergence_rate",
                value=1.0,
                target=1.0,
                comparison=">=",
                unit="ratio",
                status=MetricStatus.PASS,
                description="convergence",
                sample_count=2,
            ),
            BenchmarkMetric(
                name="db_size_bytes",
                value=4096.0,
                target=0.0,
                comparison="<=",
                unit="bytes",
                status=MetricStatus.PASS,
                description="db size",
                sample_count=1,
            ),
        ],
    )

    markdown = render_benchmark_markdown(report)
    assert "Benchmark Report" in markdown
    assert "sync_convergence_rate" in markdown
    assert "stub" in markdown

    json_path, md_path = write_benchmark_report(
        report, tmp_path, stem="phase5-bench", overwrite=False
    )
    assert json_path.exists()
    assert md_path.exists()
    import json as _json

    loaded = _json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["runtime"] == "stub"
    assert len(loaded["metrics"]) == 2

    # 不覆盖：再次写入应拒绝
    import pytest as _pytest

    with _pytest.raises(FileExistsError):
        write_benchmark_report(report, tmp_path, stem="phase5-bench", overwrite=False)
