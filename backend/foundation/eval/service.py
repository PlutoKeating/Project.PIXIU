"""Phase 5 BenchmarkService：组装同步收敛基准 + 系统资源测量 → BenchmarkReport。

两套运行结果通过 runtime 字段区分：
- "stub"：测试 embedding 桩，用于回归与 CI（Windows 可执行）
- "kylin"：真实麒麟 SDK，用于赛题验收与报告（麒麟环境执行）
"""

from __future__ import annotations

import time
from collections.abc import Callable

from .benchmark import SyncBenchmark, SystemBenchmark
from .metrics import nearest_rank_percentile
from .models import (
    BenchmarkMetric,
    BenchmarkReport,
    MetricStatus,
    ReportStatus,
    RuntimeType,
    SyncRound,
)


class BenchmarkService:
    """同步收敛 + 系统资源基准服务。"""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.perf_counter,
        timestamp: Callable[[], float] = time.time,
    ) -> None:
        self._clock = clock
        self._timestamp = timestamp

    async def run_all(
        self,
        node_factory,
        *,
        db_path: str,
        rounds: int,
        ops_per_round: int,
        runtime: RuntimeType = "stub",
        now: int = 2_000_000_000,
    ) -> BenchmarkReport:
        """执行同步基准 + 资源测量，返回完整基准报告。"""
        sync_rounds, latencies = await SyncBenchmark(clock=self._clock).run(
            node_factory,
            rounds=rounds,
            ops_per_round=ops_per_round,
            now=now,
        )

        metrics: list[BenchmarkMetric] = []
        converged_rounds = sum(1 for r in sync_rounds if r.converged)
        total_rounds = len(sync_rounds)

        if total_rounds == 0:
            convergence = BenchmarkMetric(
                name="sync_convergence_rate",
                value=None,
                target=1.0,
                comparison=">=",
                unit="ratio",
                status=MetricStatus.NOT_EVALUATED,
                description="两节点同步模拟中收敛轮次占比。",
                sample_count=0,
            )
        else:
            rate = converged_rounds / total_rounds
            convergence = BenchmarkMetric(
                name="sync_convergence_rate",
                value=rate,
                target=1.0,
                comparison=">=",
                unit="ratio",
                status=MetricStatus.PASS if rate >= 1.0 else MetricStatus.FAIL,
                description="两节点同步模拟中收敛轮次占比。",
                sample_count=total_rounds,
            )
        metrics.append(convergence)

        if latencies:
            metrics.extend(
                [
                    BenchmarkMetric(
                        name="sync_latency_p50_ms",
                        value=nearest_rank_percentile(latencies, 0.50),
                        target=0.0,
                        comparison="<=",
                        unit="ms",
                        status=MetricStatus.PASS,
                        description="两节点同步耗时 P50（信息性）。",
                        sample_count=len(latencies),
                    ),
                    BenchmarkMetric(
                        name="sync_latency_p95_ms",
                        value=nearest_rank_percentile(latencies, 0.95),
                        target=0.0,
                        comparison="<=",
                        unit="ms",
                        status=MetricStatus.PASS,
                        description="两节点同步耗时 P95（信息性）。",
                        sample_count=len(latencies),
                    ),
                ]
            )

        metrics.extend(SystemBenchmark(clock=self._clock).measure(db_path))

        overall = (
            ReportStatus.FAIL
            if any(m.status is MetricStatus.FAIL for m in metrics)
            else ReportStatus.PASS
        )
        return BenchmarkReport(
            runtime=runtime,
            generated_at=int(self._timestamp()),
            overall_status=overall,
            metrics=metrics,
            sync_rounds=sync_rounds,
        )


__all__ = ["BenchmarkService"]
