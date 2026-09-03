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

## 实现状态（2026-08-11）

- 🟡 **测试与工具侧**：foundation+engine 全量测试已由 A/C 模块补齐（麒麟 V11 真机
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
