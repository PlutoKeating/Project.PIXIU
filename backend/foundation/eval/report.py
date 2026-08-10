"""Phase 5 基准报告渲染与写出（JSON + Markdown）。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .eval import EvalConfigurationError, _atomic_write
from .models import BenchmarkMetric, BenchmarkReport


def render_benchmark_markdown(report: BenchmarkReport) -> str:
    """渲染基准报告 Markdown。"""

    def _cell(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")

    def _fmt(metric: BenchmarkMetric) -> str:
        if metric.value is None:
            value = "n/a"
        elif metric.unit == "ratio":
            value = f"{metric.value * 100:.2f}%"
        elif metric.unit == "bytes":
            value = f"{metric.value:,.0f} B"
        else:
            value = f"{metric.value:.3f} ms" if metric.unit == "ms" else f"{metric.value:.0f}"
        return value

    lines = [
        "# PIXIU Benchmark Report",
        "",
        f"- Runtime: `{report.runtime}`",
        f"- Generated at (UTC Unix): `{report.generated_at}`",
        f"- Overall status: **{report.overall_status.value}**",
        "",
        "## Metrics",
        "",
        "| Metric | Value | Target | Samples | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for metric in report.metrics:
        lines.append(
            f"| `{_cell(metric.name)}` | {_fmt(metric)} | "
            f"{metric.comparison} {metric.target} | {metric.sample_count} | "
            f"{metric.status.value} |"
        )

    if report.sync_rounds:
        lines.extend(
            [
                "",
                "## Sync rounds",
                "",
                "| Round | Ops | Converged | Elapsed (ms) | Error |",
                "|---:|---:|:---:|---:|---|",
            ]
        )
        for round_ in report.sync_rounds:
            lines.append(
                f"| {round_.round} | {round_.ops} | "
                f"{'yes' if round_.converged else 'no'} | "
                f"{round_.elapsed_ms:.1f} | {_cell(round_.error or '')} |"
            )
    lines.append("")
    return "\n".join(lines)


def write_benchmark_report(
    report: BenchmarkReport,
    output_dir: str | Path,
    *,
    stem: str = "benchmark-report",
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """原子写出 JSON 与 Markdown 基准报告。"""
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", stem):
        raise EvalConfigurationError("report stem contains unsupported characters")
    target = Path(output_dir)
    json_path = target / f"{stem}.json"
    markdown_path = target / f"{stem}.md"
    if not overwrite:
        existing = [path for path in (json_path, markdown_path) if path.exists()]
        if existing:
            raise FileExistsError(f"refusing to overwrite report: {existing[0]}")

    json_text = json.dumps(
        report.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    _atomic_write(json_path, json_text)
    _atomic_write(markdown_path, render_benchmark_markdown(report))
    return json_path, markdown_path
