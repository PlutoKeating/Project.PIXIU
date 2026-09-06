# Module C · 旧范围验收清单（赛题 P0 已重新打开）

> 2026-09-06 复核：本文保留原日期对应的测试/审计快照，不将历史数量、环境或待办状态当作当前结论。现行 API 为 32 个 REST 端点、六类 WS 事件，schema v12；2026-09-06 CI（`fd1a6d7`）在 Python 3.12/3.13 各通过 823 项测试。默认 auto 可降级至 portable，严格 V11 则必须使用双 SDK。原生产品链、完整 Agent 场景和三物理设备验收分别取证，最新发布规则见 `docs/DELIVERY_PLAN.md`。

> 对照 `docs/AcceptanceTestSpecification.md` 与赛题验收追踪重点。
> 状态列：✅=旧范围本地已验证；🟡=需环境执行；🔴=完整 PPT 下的硬缺口。
> 刷新于 2026-08-29：Module A 已联调完成（前端 ctest 32/32 + regression.sh 双路径），
> portable 基线见 `docs/acceptance/`（达到数值阈值，但不等于赛题最终验收）。
> 2026-09-04 复核确认：revision 8 已取得 V11 系统 Vector Engine 产品链强实证，
> 但最终 user service/安装依赖未闭环，H-02 仍未通过。Module E 已实现并进入真实
> Runtime 发现探针；A-11～A-14 原创/上游边界检查仍未通过。

## 一、验收追踪重点映射

| 能力 | 验收项 | 实现证据 | 状态 |
|------|--------|---------|------|
| 关联检索 | F3-02 / SC-02 / SC-03 | `retrieval/` 三通道（BM25+ANN+Graph）混合检索；`test_e2e_stories.py::test_story_s1`（检索+证据回溯）；`test_retrieval.py`（14 项） | ✅ |
| 轻量存储与性能 | F4-03～F4-05 / P-03 | portable/stub 压测 P95=19.18ms；生产向量仍未接系统 Vector Engine | 🔴 H-02 未通过；V11 双 SDK 待测 |
| 记忆流转 | F6-01～F6-03 / D-05 | `flow/` promote/demote/TTL；`test_flow.py`；`/memory/flow/promote` 真实端点 | ✅ |
| 评测机制 | F7-01～F7-05 | `eval/` 评测引擎（Recall@1/3/5、P50/P95/P99、scope 隔离、聚合/追溯/冲突/偏好 12 指标）+ 基准框架（CRDT 收敛/同步耗时/DB/内存/CPU）+ CLI | ✅ |
| 模糊检索 | SC-04 / SC-08 | BM25 长句滑动窗口回退 + ANN 语义通道（`retrieval/bm25.py`、`ann.py`） | ✅ |
| 跨文档聚合 | SC-09 / SC-K3 | `retrieval/assembler.py` 金额聚合（`aggregation_accuracy`=1.0 门槛） | ✅ |
| 证据追溯 | SC-05 / SC-K4 | `source_evidence` 回溯 + `evidence_trace_accuracy`=1.0 门槛；S1 故事验证 | ✅ |
| 去中心化同步 | 核心创新 | `sync/` 全链路（身份/CRDT/配对/TLS/Gossip/反熵/墓碑）；`test_sync_*`（33 项）；S4 双设备故事 | ✅ |
| API/WS/D-Bus | Module A 联调 | REST 全部真实端点 + WS 事件 + D-Bus（Write/Query/Forget/SyncStatus）；`test_api.py`（18 项）、`test_dbus_service.py`（10 项） | ✅（2026-08-29 已与 Module A 真实联调：前端 ctest 32/32 + regression.sh 双路径绿） |

## 二、Phase 7 专项验收

| 专项 | 结果 | 证据 |
|------|------|------|
| 四条完整故事 | 4/4 PASS | `tests/test_e2e_stories.py` |
| WAL 并发读写 | PASS（无锁错误） | `test_hardening.py::test_wal_concurrent_read_write` |
| 多请求同时 embedding | PASS（20 并发不串扰） | `test_hardening.py::test_concurrent_embedding_requests` |
| API 错误码 + request_id | PASS（`{error,message,request_id}` + X-Request-Id） | `test_hardening.py` + `test_api.py` |
| 日志敏感数据脱敏 | PASS（password/token→***） | `test_logger.py` + `test_hardening.py` |
| 数据库升级迁移 | PASS（幂等 + 失败回滚） | `test_hardening.py::test_migration_*` |
| 进程崩溃恢复 | PASS（未 commit 自动回滚） | `test_hardening.py::test_crash_recovery_*` |
| 安装后组件健康 | PASS（版本/API/schema/数据库/Provider 不一致拒绝） | `test_install_health.py` + `build/release/tests/test-update-helper.sh` |
| 磁盘/内存占用 | PASS（<10MB / <256MB 峰值） | `test_hardening.py` |
| 1000 次查询压测 | P50=16.99 / P95=19.18 / P99=20.73 ms，0 错误 | `evidence/pressure_report.json`、`pressure_latencies.csv`、`pressure_test_report.md` |
| ARM/x86 麒麟兼容 | 🟡 需麒麟环境 | `engine/kylin/cpp/` 绑定源码 + submodule 已就位 |

## 三、开发回归指标（stub runtime，不是最终赛题结果）

| 指标 | 门槛 | stub 实测 | 状态 |
|------|------|----------|------|
| 知识检索召回率 | ≥85% | 命中率 100%（reference 数据集待麒麟） | ✅/🟡 |
| 检索 P95 | ≤500ms | 19.18ms | ✅ stub 回归；最终待测 |
| 聚合正确率 | 100% | 门槛内置（`aggregation_accuracy`=1.0） | ✅ |
| 证据追溯成功率 | 100% | 门槛内置 | ✅ |
| scope 隔离 | 100% | 门槛内置（`scope_isolation_accuracy`=1.0） | ✅ |
| 冲突正确率 | ≥88% | 门槛内置 | ✅ |
| 偏好准确率 | ≥85% | 门槛内置 | ✅ |
| CRDT 收敛率 | 100% | SyncBenchmark 实测 1.0 | ✅ |

## 四、测试统计

- 2026-09-04 最新组合回归：pytest 809 passed（Foundation 636 + Engine 154 +
  Module E 19），既有依赖弃用告警，无失败。
- 同步物化测试覆盖远端知识向量首次创建、更新后重建、墓碑删除，以及 mainline
  自动仲裁结果进入同一索引写入器；最终仍须在 V11 系统 Vector Engine 画像复验。
- knowledge/evidence 跨批次逆序到达时，待补 citation 经 `sync_meta` 持久化并在后续
  evidence 物化时恢复；回归确认修复后待补记录清零。
- 旧范围快照：Foundation 356 项 + Engine 21 项，共 377 项；仅用于阶段追溯。
- 运行：`pytest backend/foundation/tests/ backend/engine/tests/ -q`

## 五、赛题 P0 遗留（允许并要求实现）

1. 麒麟环境：官方组件修复组合下 PIXIU binding 已返回 768 维真实向量；仍需最终可安装依赖和 reference-v1 数据集验收（产出 runtime="kylin" 报告）
2. **H-02 阻塞项**：revision 8 写入/检索/遗忘已通过；待最终 user service、依赖与正式取证闭环
3. Agent 宿主/Runtime 可重建离线供应链，以及模型驱动的多轮/工具结果端到端闭环
4. Agent 公共契约：capability、`CONVERSATION`、evidence 关联 ID、完成态持久化
   幂等、审计式失败恢复、预算化安全查询上下文和六类 context 生命周期已完成；
   Module E 真实宿主端到端与长期化仍待完成
5. ~~Module A 三通道联调~~ ✅ 已完成（2026-08-29，前端全量回归绿）
6. 根文档/API 实现状态由 Module D/Human 更新（2026-09-03 已随决策巡检刷新）
