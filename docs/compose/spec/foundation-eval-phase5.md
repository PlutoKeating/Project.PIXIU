---
feature: foundation-eval-phase5
status: delivered
updated: 2026-08-10
branch: feat/foundation
commits: 300ec0d..d6adeb9
---

# Phase 5 — 量化评测框架扩展

> 2026-09-06 代码复核：历史 stub/portable 数值保留原画像；最终性能由 capture_final_eval.py 和 final-performance-evidence.py 绑定安装组件、真实双 SDK、数据集及候选包，不能直接采用本阶段结果。
> 下文实施步骤、旧接口草图和测试数字保留作阶段历史，不作为当前操作手册；当前契约见 docs/API.md，发布见 docs/DELIVERY_PLAN.md。

## Report

**What was built** — Phase 5 评测扩展完成两大部分：
1. **指标扩展**（metrics.py/models.py/eval.py）：Recall@1/3/5 分档召回、P50/P95/P99 延迟分布、scope 隔离正确率（100% 硬门槛，prediction 携带 `knowledge_scopes` 映射，声明 scope 却缺映射视为违规）。`overall_status` 改为只以 6 项核心验收指标为准，辅助指标无样本不阻塞。
2. **基准框架**（benchmark.py/report.py/service.py 新增）：`SyncBenchmark`（两节点 CRDT 收敛率 + 同步耗时 P50/P95，轮次隔离、故障轮次记录）、`SystemBenchmark`（DB 大小/tracemalloc 峰值/process_time，零新依赖）、`BenchmarkService.run_all` 组装 `BenchmarkReport`，`runtime=stub|kylin` 区分测试桩与真实麒麟 SDK 两套结果。

**Verification** — 全量 354 项测试通过（新增 13 项：6 eval 扩展 + 7 benchmark）。stub 基准自检：收敛率 1.0、同步 P95 55ms、DB 225KB、峰值内存 5MB、CPU 47ms。验收门槛全部映射到指标实现。

**Journey log**
- `overall_status` 三版演进：全指标 NOT_EVALUATED→INCOMPLETE 会破坏无 scope 数据集 → 改为仅核心 6 指标有样本判定 → 最终只检查核心 6 指标全 PASS，辅助指标无样本不阻塞。
- PowerShell `Add-Content` 以 GBK 写入破坏 UTF-8 测试文件——此后一律用 Python 脚本以 UTF-8 追加。
- SyncBenchmark 首版未配对 A/B，B 拒绝 A 的 op（"origin is not trusted"）→ 每轮需先 QR 双向配对；node_factory 调用移入 try 块使节点创建失败也记为失败轮次。
- 资源测量坚持零新依赖（tracemalloc/process_time），文档标注为 Python 侧近似。

## [S1] Problem

现有 eval/ 框架（Phase 4 已提交）覆盖 6 项验收指标（preference/recall_at_k/P95/conflict/aggregation/evidence）。Phase 5 要求补齐：
- Recall@1/@3/@5 分档召回
- P50/P95/P99 延迟分布
- **scope 隔离正确率**（新指标）
- **CRDT 收敛率 + 同步耗时**（同步基准）
- **数据库大小 / 内存 / CPU**（系统资源基准）
- 新文件 benchmark.py / report.py / service.py

## [S2] Design

### S2.1 metrics.py 扩展（3 个新指标）

1. **Recall@1/@3/@5** — 新增 `knowledge_recall@1` / `@3` / `@5` 三个指标（对每个 RETRIEVAL case 取 prediction.knowledge_ids 前 k 个算 recall），阈值 0.85。保留现有 `recall_at_k`（按 case 声明 top_k）为主指标，分档指标为补充视角。
2. **P50/P95/P99** — 新增 `retrieval_p50_ms` / `retrieval_p95_ms`（现有，改名统一）/ `retrieval_p99_ms`。target 均为 500ms（P95 为赛题硬指标；P50/P99 信息性同阈值）。
3. **scope 隔离正确率** — 新增 `scope_isolation_accuracy`，阈值 **1.0**。机制：
   - RETRIEVAL case 的 `expected` 增加可选字段 `scope: str`（允许集加 "scope"）
   - runner prediction 增加可选字段 `knowledge_scopes: dict[str, str]`（knowledge_id → scope）
   - 对每个带 expected.scope 的 case：所有预测 knowledge_ids 的 scope == expected.scope 且无越界 → 正确
   - 无 expected.scope 的 case 不计入该指标

### S2.2 models.py 扩展

- `EvalCase` RETRIEVAL expected 允许集加 `"scope"`（字符串，可选）
- `normalize_prediction` 透传 `knowledge_scopes`（dict[str,str]，可选，校验字符串键值）
- 新增 `BenchmarkMetric`（同 MetricResult 结构，unit 扩展 `"bytes"/"count"/"ratio"/"ms"`）
- 新增 `BenchmarkReport`：`sync_convergence_rate`、`sync_latency_p50/p95_ms`、`db_size_bytes`、`peak_memory_mb`、`cpu_time_ms`、`samples`（轮次明细）+ `overall_status`

### S2.3 benchmark.py（新增）— 两个基准

**SyncBenchmark**（CRDT 收敛率 + 同步耗时）：
- 输入：SyncService 工厂（真实 store，测试注入临时 SQLite）
- 每轮：节点 A record N ops（N=10/50/100）→ 传输到节点 B → 断言 A/B 状态一致 → 记录 `converged: bool` + `elapsed_ms`
- 收敛率 = 收敛轮次 / 总轮次；同步耗时 P50/P95
- 失败轮次记录原因（不中断）

**SystemBenchmark**（资源）：
- `db_size_bytes`：SQLite 文件（db + -wal）总字节
- `peak_memory_mb`：`tracemalloc` 峰值（零新依赖；文档标注为 Python 侧近似，非 RSS）
- `cpu_time_ms`：`time.process_time` 增量
- 全部尽力而为，不做精确 OS 级采样（避免引入 psutil 依赖）

### S2.4 report.py（新增）

- `render_benchmark_markdown(report) -> str`：基准报告 Markdown（指标表 + 轮次明细）
- `write_benchmark_report(report, output_dir, *, stem, overwrite)`：JSON + Markdown 原子写出（复用 eval.py 的 `_atomic_write` 模式，或抽公共工具）

### S2.5 service.py（新增）— BenchmarkService

```python
class BenchmarkService:
    def __init__(self, *, clock=..., timestamp=...): ...
    async def run_sync_benchmark(self, node_factory, rounds, ops_per_round) -> SyncBenchmarkResult
    def measure_system(self, db_path, *, duration_ms=200) -> SystemMeasurement
    async def run_all(self, node_factory, db_path, rounds, ops_per_round) -> BenchmarkReport
```

**两套结果区分**（Phase 5 硬性要求）：
- 测试桩：`BenchmarkService.run_all(..., embedder=None)` → 用 StubTextEmbedder 模式跑，报告标注 `runtime: "stub"`
- 麒麟真实：报告标注 `runtime: "kylin"`（由外部 CLI 传参，Windows 无法本地执行）

`BenchmarkReport.runtime: Literal["stub", "kylin"]`。

### S2.6 测试

- `tests/test_eval.py` 扩展：recall@1/3/5、P50/P99、scope 隔离（命中/越界/无 scope 不计）
- 新增 `tests/test_benchmark.py`：SyncBenchmark 收敛（两节点 N ops 收敛率 1.0）、同步耗时 >0、SystemBenchmark（db_size>0、memory>0、cpu>=0）、BenchmarkReport 渲染与写出、runtime 字段

### S2.7 验收门槛映射

| 指标 | target | 实现位置 |
|------|--------|---------|
| 知识检索召回率 ≥85% | recall_at_k + recall@1/3/5 ≥0.85 | metrics.py |
| 检索 P95 ≤500ms | retrieval_p95_ms ≤500 | metrics.py |
| 聚合正确率 100% | aggregation_accuracy =1.0（已有） | metrics.py |
| 证据追溯成功率 100% | evidence_trace_accuracy =1.0（已有） | metrics.py |
| scope 隔离 100% | scope_isolation_accuracy =1.0 | metrics.py |
| 冲突正确率 ≥88% | conflict_accuracy ≥0.88（已有） | metrics.py |
| 偏好准确率 ≥85% | preference_accuracy ≥0.85（已有） | metrics.py |
| CRDT 收敛率 | sync_convergence_rate ≥1.0（基准） | benchmark.py |
| 同步耗时 / DB / 内存 / CPU | 信息性报告 | benchmark.py |

## [S3] Out of Scope

- Module D 数据集（50 组家庭支出、黄金查询集）—— 不在本模块
- backend/scripts/eval.py（Module D 压测入口）
- 麒麟真实 SDK 运行（Windows 无原生扩展，标注 runtime="kylin" 由验收机执行）
- 精确 OS 级内存/CPU 采样（避免 psutil 依赖）

## Tasks

- [x] T1: models.py — EvalCase expected +scope；normalize 透传 knowledge_scopes；新增 BenchmarkMetric/BenchmarkReport (covers: S2.1, S2.2)
- [x] T2: metrics.py — recall@1/3/5、p50/p99、scope_isolation_accuracy (covers: S2.1)
- [x] T3: benchmark.py — SyncBenchmark + SystemBenchmark (covers: S2.3)
- [x] T4: report.py — render/write benchmark report (covers: S2.4)
- [x] T5: service.py — BenchmarkService + runtime 标注 (covers: S2.5; depends: T3, T4)
- [x] T6: eval/__init__.py — 导出新模块 (covers: S2.2-S2.5)
- [x] T7: tests — test_eval.py 扩展 + test_benchmark.py 新增 (covers: S2.6; depends: T2, T3, T5)
- [x] T8: 全量回归 + 基准自检（跑一次 stub 基准产出报告） (covers: S2.7; depends: T7)
