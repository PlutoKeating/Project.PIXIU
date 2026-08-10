"""Phase 5 基准：CRDT 同步收敛率/耗时 + 系统资源（DB 大小/内存/CPU）。

- SyncBenchmark：两节点模拟，每轮传输 N 条 op 并断言收敛。
- SystemBenchmark：SQLite 文件大小、tracemalloc 峰值内存、process_time CPU 耗时。
  均为尽力而为的近似（不引入 psutil），文档标注为 Python 侧测量。
"""

from __future__ import annotations

import os
import time
import tracemalloc
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from .models import BenchmarkMetric, MetricStatus, SyncRound

NodeFactory = Callable[[], Awaitable[Any]]  # 返回 (service, store, db) 的可等待工厂


class SyncBenchmark:
    """两节点 CRDT 收敛率与同步耗时基准。"""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.perf_counter,
        domain: str = "shared:home",
        entity_prefix: str = "bench:entity",
    ) -> None:
        self._clock = clock
        self._domain = domain
        self._entity_prefix = entity_prefix

    async def run(
        self,
        node_factory: NodeFactory,
        *,
        rounds: int,
        ops_per_round: int,
        now: int = 2_000_000_000,
    ) -> tuple[list[SyncRound], list[float]]:
        """执行 rounds 轮同步，返回 (轮次明细, 每轮耗时 ms)。

        node_factory 每次调用返回新建的 (service, store, db) 元组，轮次间相互独立。
        """
        rounds_out: list[SyncRound] = []
        latencies: list[float] = []

        for round_index in range(1, rounds + 1):
            a = b = None
            try:
                a, _, a_db = await node_factory()
                b, _, b_db = await node_factory()
                a_svc, b_svc = a, b
                # 建立互信：双向配对后 B 才会接受 A 的 op
                from backend.foundation.sync import PairingMethod

                token_b = await b_svc.create_pairing_token(PairingMethod.QR, now=now)
                await a_svc.pair(PairingMethod.QR, token_b, now=now)
                token_a = await a_svc.create_pairing_token(PairingMethod.QR, now=now)
                await b_svc.pair(PairingMethod.QR, token_a, now=now)

                started = self._clock()
                # A 本地产生 ops_per_round 条共享域修改
                for i in range(ops_per_round):
                    await a_svc.record_local(
                        f"{self._entity_prefix}:{round_index}:{i}",
                        {"v": i},
                        self._domain,
                        now=now,
                    )
                # 传输到 B 并断言收敛
                ops = await a_svc._store.list_ops()
                accepted = await b_svc.receive_ops(ops)
                elapsed_ms = (self._clock() - started) * 1000.0

                converged = accepted == ops_per_round
                if converged:
                    for i in range(ops_per_round):
                        entity = f"{self._entity_prefix}:{round_index}:{i}"
                        sa = await a_svc._store.get_state(entity)
                        sb = await b_svc._store.get_state(entity)
                        if sa is None or sb is None or sa.payload != sb.payload:
                            converged = False
                            break
                rounds_out.append(
                    SyncRound(
                        round=round_index,
                        ops=ops_per_round,
                        converged=converged,
                        elapsed_ms=elapsed_ms,
                    )
                )
                latencies.append(elapsed_ms)
            except Exception as exc:  # 单轮失败不中断整体基准
                rounds_out.append(
                    SyncRound(
                        round=round_index,
                        ops=ops_per_round,
                        converged=False,
                        elapsed_ms=0.0,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
            finally:
                if a is not None and a_db is not None:
                    await a_db.close()
                if b is not None and b_db is not None:
                    await b_db.close()

        return rounds_out, latencies


class SystemBenchmark:
    """系统资源基准：DB 大小 / 峰值内存 / CPU 耗时。"""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._clock = clock

    def measure(self, db_path: str | Path, *, duration_ms: int = 200) -> list[BenchmarkMetric]:
        """测量数据库文件大小与一段工作负载期间的 Python 峰值内存/CPU。"""
        path = Path(db_path)

        db_bytes = 0.0
        if path.exists():
            db_bytes = float(path.stat().st_size)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(path) + suffix)
            if sidecar.exists():
                db_bytes += float(sidecar.stat().st_size)

        # tracemalloc 峰值（Python 侧分配近似）
        tracemalloc.start()
        cpu_start = time.process_time()
        # 触发分配的工作负载：序列化模拟查询结果
        payload = {"results": [{"knowledge_id": f"knw_{i}", "score": i * 0.1} for i in range(10_000)]}
        _ = str(payload) * 3
        cpu_elapsed = (time.process_time() - cpu_start) * 1000.0
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_mb = peak / (1024 * 1024)

        return [
            BenchmarkMetric(
                name="db_size_bytes",
                value=db_bytes,
                target=0.0,
                comparison="<=",
                unit="bytes",
                status=MetricStatus.PASS,
                description="SQLite 主库与 WAL/SHM 文件总字节数（信息性）。",
                sample_count=1,
            ),
            BenchmarkMetric(
                name="peak_memory_mb",
                value=peak_mb,
                target=0.0,
                comparison="<=",
                unit="bytes",
                status=MetricStatus.PASS,
                description="tracemalloc 峰值（Python 侧近似，非 RSS）。",
                sample_count=1,
            ),
            BenchmarkMetric(
                name="cpu_time_ms",
                value=cpu_elapsed,
                target=0.0,
                comparison="<=",
                unit="ms",
                status=MetricStatus.PASS,
                description="workload 的 process_time 增量（信息性）。",
                sample_count=1,
            ),
        ]
