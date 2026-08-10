"""Phase 7 压测证据生成器。

本地（stub embedding）执行 1000 次查询压测，产出可引用证据：
  - evidence/pressure_report.json      聚合统计（P50/P95/P99、吞吐、错误率）
  - evidence/pressure_latencies.csv    逐次查询延迟明细
  - evidence/pressure_test_report.md   人类可读测试报告

用法（项目根）：
  python -m backend.foundation.scripts.phase7_pressure
"""

from __future__ import annotations

import asyncio
import csv
import json
import sqlite3
import statistics
import tempfile
import time
from pathlib import Path

import aiosqlite

from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.tests.fakes import StubTextEmbedder
from backend.foundation.eval import compute_metrics, load_predictions
from backend.foundation.retrieval import RetrievalService
from backend.foundation.storage.repository import (
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
)
from backend.foundation.storage.schema import init_db_on_connection

EVIDENCE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "backend" / "foundation" / "evidence"
QUERY_SET = [
    "水电燃气方面花了多少钱",
    "家庭支出清单",
    "国家电网电费多少钱",
    "最近的家庭支出记录",
    "话费账单明细",
    "2026年4月水电燃气支出",
    "物业费是多少",
    "燃气费账单",
    "家庭月度开销汇总",
    "电费和水费记录",
]


async def _make_db(path: Path) -> aiosqlite.Connection:
    sc = sqlite3.connect(str(path))
    init_db_on_connection(sc)
    sc.close()
    db = await aiosqlite.connect(str(path))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db = await _make_db(root / "pressure.db")
        embedder = StubTextEmbedder()
        knw_repo = SqliteKnowledgeRepo(db)
        ent_repo = SqliteEntityRepo(db)
        evd_repo = SqliteEvidenceRepo(db)

        # 50 条家庭支出知识（与 reference-v1 规模一致）
        vendors = ["国家电网", "新奥燃气", "市自来水公司", "中国移动", "物业公司"]
        categories = ["电费", "燃气费", "水费", "话费", "物业费"]
        for i in range(50):
            from backend.foundation.core.models import KnowledgeItem, KnowledgeKind

            item = KnowledgeItem(
                id=f"knw_{i:026d}",
                kind=KnowledgeKind.FACT,
                title=f"2026年{4 + i % 6}月家庭支出清单{i}",
                body={
                    "description": f"{vendors[i % 5]} {categories[i % 5]}缴费记录",
                    "items": [{"category": categories[i % 5], "vendor": vendors[i % 5], "amount": 100.0 + i}],
                },
                scope="shared:home",
                created_at=1700000000 + i,
                updated_at=1700000000 + i,
            )
            await knw_repo.save(item)
            import struct

            from backend.foundation.retrieval.ann import quantize_int8

            text = " ".join(str(x) for x in [item.title, item.kind, item.body])
            q = quantize_int8(embedder.embed(text))
            await knw_repo.save_vector(item.id, embedder.dim, struct.pack(f"{len(q)}b", *q))

        service = RetrievalService(knw_repo, ent_repo, evd_repo, embedder)

        # 1000 次查询压测
        latencies: list[float] = []
        errors = 0
        results: list[dict] = []
        for i in range(1000):
            text = QUERY_SET[i % len(QUERY_SET)]
            started = time.perf_counter()
            try:
                atom = await service.query(text, {"top_k": 5, "scope": "shared:home"})
                results.append(
                    {
                        "query": text,
                        "latency_ms": round(atom.latency_ms, 2),
                        "hit": bool(atom.source_knowledge),
                    }
                )
            except Exception:
                errors += 1
                results.append({"query": text, "latency_ms": None, "hit": False})
            latencies.append((time.perf_counter() - started) * 1000)

        await db.close()

    latencies.sort()
    n = len(latencies)

    def pct(p: float) -> float:
        return latencies[max(0, min(n - 1, int(p * n) - 1))]

    report = {
        "benchmark": "phase7-1000-query-pressure",
        "runtime": "stub",
        "samples": n,
        "errors": errors,
        "error_rate": round(errors / n, 4),
        "latency_ms": {
            "p50": round(pct(0.50), 2),
            "p95": round(pct(0.95), 2),
            "p99": round(pct(0.99), 2),
            "max": round(latencies[-1], 2),
            "mean": round(statistics.mean(latencies), 2),
        },
        "throughput_qps": round(n / (sum(latencies) / 1000), 1),
        "acceptance": {
            "p95_le_500ms": pct(0.95) <= 500.0,
            "hit_rate": round(sum(1 for r in results if r["hit"]) / len(results), 4),
        },
        "generated_at": int(time.time()),
    }

    (EVIDENCE_DIR / "pressure_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (EVIDENCE_DIR / "pressure_latencies.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["index", "query", "latency_ms", "hit"])
        for idx, row in enumerate(results):
            writer.writerow([idx, row["query"], row["latency_ms"] if row["latency_ms"] is not None else "error", row["hit"]])

    markdown = (
        "# PIXIU Phase 7 压测报告\n\n"
        f"- Benchmark: `{report['benchmark']}`\n"
        f"- Runtime: `{report['runtime']}`（stub embedding，回归/CI；麒麟真实 SDK 需验收机）\n"
        f"- Samples: {report['samples']}，Errors: {report['errors']}（错误率 {report['error_rate'] * 100:.2f}%）\n"
        f"- 吞吐: {report['throughput_qps']} QPS\n\n"
        "## 延迟\n\n"
        f"| P50 | P95 | P99 | Max | Mean |\n|---|---:|---:|---:|---:|\n"
        f"| {report['latency_ms']['p50']} ms | {report['latency_ms']['p95']} ms | "
        f"{report['latency_ms']['p99']} ms | {report['latency_ms']['max']} ms | "
        f"{report['latency_ms']['mean']} ms |\n\n"
        "## 验收门槛\n\n"
        f"- P95 ≤ 500ms：**{'PASS' if report['acceptance']['p95_le_500ms'] else 'FAIL'}** "
        f"（实测 {report['latency_ms']['p95']} ms）\n"
        f"- 查询命中率：{report['acceptance']['hit_rate'] * 100:.2f}%\n\n"
        "> 证据文件：pressure_report.json / pressure_latencies.csv\n"
    )
    (EVIDENCE_DIR / "pressure_test_report.md").write_text(markdown, encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nEvidence written to {EVIDENCE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
