# 模块 D · 测试与工具（Support/QA）

> **覆盖目录**：`backend/scripts/`, `backend/tests/`, 部分 `docs/`
> **开发人员**：1人（测试/运维/工具开发）
> **对其他模块**：零依赖，可使用 mock 数据独立工作

> [!CAUTION]
> mock/stub/portable 只用于开发回归。赛题最终报告必须在银河麒麟桌面操作系统
> V11 上真实调用指定 Embedding 与 Vector Engine，并覆盖完整 Agent 和多设备闭环。
> 团队已批准 ADR-0001；Module D 还必须验证 Module E 生命周期以及 A-11～A-14
> 上游版本、许可证、原创边界和实质性集成，不得只验证上游 Agent 能启动。

---

## 实现状态（2026-09-04）

- 🟡 **当前总览**：组合回归 809 passed、前端 ctest 38/38；版本化 `.deb`、签名
  升级/回滚、submission fail-closed 打包器、Agent 供应链门禁和三逻辑节点协议 JSON
  证据已接线；Agent 供应链门禁已拒绝无实物布尔自述、占位 SBOM/NOTICE，并要求构建/
  离线安装日志、源码/锁文件和逐项摘要互相绑定；真实 V11 三节点清单采集/全连接校验器也已落地，但尚无三机实测输入，
  且固定不冒充最终场景证据。portable 数据集与性能报告已有，但最终 V11 双 SDK、
  完整 Agent、三台设备场景、图形安装升级和 D-01～D-10 同版成品仍未完成。D-03
  完整源码归档及 D-02/D-03/D-04/D-06～D-10 DOCX/PDF 渲染/格式门已落地，当前仅生成
  带禁提交标识的草稿，最终模式继续等待同版实证与人工审核。
  D-07 原始证据归档器也已按七类主记录建立同 commit/候选包交叉校验与敏感扫描；
  真实 Agent 两阶段采集器及 7 项契约测试已落地，要求三轮、双进程重启、Shell/联网/
  记忆工具、现场审批和跨会话召回；当前仍缺最终 V11 实测、最终性能和安装矩阵等输入，
  因此按设计不能生成最终 ZIP。
  最终性能汇总器及 4 项契约测试也已落地，强制四项指标原始样本、三组各 30 例消融
  和 strict/Agent/数据集/候选包同版；现有 portable 报告按设计不能通过该门。
  数据集冻结器及 4 项测试已补齐：固定 50 fixture/90 test case、附录 A 派生的团队
  合成来源、规范化/实物/划分摘要和敏感扫描；最终 clean release 输出仍待生成。
  D-07 归档器现执行 native/Agent/性能/数据集/安装矩阵深验和跨附件摘要复算；安装矩阵
  采集器 6/6，通过 V11/dpkg/systemd/API/SQLite 去敏快照约束首装、重装、升级、回滚、
  GUI 升级、卸载及数据保留；
  逐样本报告、三变体矩阵或冻结 JSON 缺失/被替换时，生成与解包复验均失败。

- 🟡 **历史测试基线（2026-08-11）**：foundation+engine 全量测试已由 A/C 模块补齐（麒麟 V11 真机
  pytest 377 passed）；`backend/.env.example` 已覆盖全部配置变量（含 `PIXIU_SYNC_*`，见
  `backend/foundation/docs/QUICK_START.md`）；前端回归脚本
  `frontend/scripts/regression.sh` 已固化。
- ✅ **打包发布脚手架**：`build/release/` 提供整包 .deb 构建、目标机预置
  （`provision-target.sh`）、目标系统本地安装验收与
  staging/production 发布；已在麒麟 V11 真机验证并发布 `v0.1.0-staging`。
- 🟡 **portable 回归已完成（2026-08-29），最终验收未完成**：自建测试数据集（`pixiu-family-expense-v1`：50 检索 +
  15 偏好 + 25 冲突）、性能压测（检索 P95 115ms ≤500ms）、验收评测报告
  `docs/acceptance/`（portable 管线达到数值阈值，非桩注入；不作为 H-01～H-03 证据）。
- ❌ **Docker 容器化**：本项目交付物为原生 `.deb` 安装包，不依赖 Docker，相关文件已移除。

---

## 开工要求（本地环境准备）

开始开发前，**必须先补齐仓库内的官方麒麟 SDK submodule**：

```bash
git submodule update --init --recursive
```

- `third_party/kylin-coreai-embedding` —— 文本向量化 SDK（C API）
- `third_party/libkysdk-vector-engine-client` —— 向量数据库客户端（C++/gRPC）
- `third_party/kylin-agent`、`third_party/kylin-agent-runtime` —— 完整 Agent 与记忆接入的官方参考

测试、压测与容器化验证均依赖完整仓库（含 submodule），请勿跳过此步骤。

---

## 职责

| 领域 | 覆盖路径 | 说明 |
|------|----------|------|
| 评测框架 | `foundation/eval/` | Module C 子包，量化指标回归 |
| 工具脚本 | `backend/scripts/` | 建库、压测、部署脚本 |
| 测试数据集 | `backend/tests/datasets/` | 结构化测试数据 + 黄金查询集 |
| 单元/集成测试 | `backend/tests/` | 全模块 pytest 测试 |
| 环境变量模板 | `backend/.env.example` | 补全配置模板 |
| 文档补全 | `docs/*.md` | 辅助完善项目级文档 |

## 任务清单

### 1. 基础工具

| 文件 | 说明 |
|------|------|
| `scripts/init_db.py` | 数据库初始化（建表 + 索引） |
| `scripts/run.sh` | 一键启动脚本 |
| `scripts/eval.py` | 评测脚本（foundation/eval 已提供 CLI `python -m backend.foundation.eval`，可复用） |

> Module C 已交付 `foundation/scripts/phase7_pressure.py`（1000 次压测证据生成器，
> 产出 `foundation/evidence/` 报告），本岗位无需重复实现。

### 2. 测试数据集

| 文件/目录 | 说明 |
|-----------|------|
| `tests/datasets/expense_50/` | 50 组家庭支出清单（附录 A 场景） |
| `tests/datasets/queries.json` | 语义查询黄金集（top-1 命中率校验） |
| `tests/datasets/preferences.json` | 偏好提取测试用例 |
| `tests/datasets/conflicts.json` | 冲突仲裁测试用例 |

### 3. 文档补全

- 配合其他开发者更新 `docs/` 下的项目级文档
- 编写效果/测试报告（D-07）
- 编写用户手册（D-06）

## 参考文档

| 内容 | 路径 |
|------|------|
| 验收规范 | `docs/AcceptanceTestSpecification.md` |
| 赛题原文 | `docs/OriginProblemDescription.md` |
| 开发计划 | `docs/DEVELOPMENT_PLAN.md` |
| 完整交付主实施计划 | `docs/IMPLEMENTATION_MASTER_PLAN.md` |
