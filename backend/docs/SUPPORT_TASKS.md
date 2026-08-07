# 模块 D · 测试与工具（Support/QA）

> **覆盖目录**：`backend/scripts/`, `backend/tests/`, 部分 `docs/`
> **开发人员**：1人（测试/运维/工具开发）
> **对其他模块**：零依赖，可使用 mock 数据独立工作

---

## 实现状态（2026-08-07）

- ❌ **尚未开始**：`backend/scripts/`、`backend/tests/` 为空目录。
- 集成期已由团队负责人补齐的部分：foundation + engine 测试共 229 项全绿；
  `backend/.env.example` 已有内容（6 个变量，见 `backend/foundation/docs/QUICK_START.md`）。
- 待办清单见下，全部为未实现项。

---

## 开工要求（本地环境准备）

开始开发前，**必须先补齐仓库内的官方麒麟 SDK submodule**：

```bash
git submodule update --init --recursive
```

- `third_party/kylin-coreai-embedding` —— 文本向量化 SDK（C API）
- `third_party/libkysdk-vector-engine-client` —— 向量数据库客户端（C++/gRPC）

测试、压测与容器化验证均依赖完整仓库（含 submodule），请勿跳过此步骤。

---

## 职责

| 领域 | 覆盖路径 | 说明 |
|------|----------|------|
| 评测框架 | `foundation/eval/` | Module C 子包，量化指标回归 |
| 工具脚本 | `backend/scripts/` | 建库、压测、部署脚本 |
| 测试数据集 | `backend/tests/datasets/` | 结构化测试数据 + 黄金查询集 |
| 单元/集成测试 | `backend/tests/` | 全模块 pytest 测试 |
| Docker 容器化 | `backend/Dockerfile` + `docker-compose.yml` | 补全容器化 |
| 环境变量模板 | `backend/.env.example` | 补全配置模板 |
| 文档补全 | `docs/*.md` | 辅助完善项目级文档 |

## 任务清单

### 1. 基础工具

| 文件 | 说明 |
|------|------|
| `scripts/init_db.py` | 数据库初始化（建表 + 索引） |
| `scripts/run.sh` | 一键启动脚本 |
| `scripts/eval.py` | 评测脚本（调用 foundation/eval 跑全量指标） |

### 2. 测试数据集

| 文件/目录 | 说明 |
|-----------|------|
| `tests/datasets/expense_50/` | 50 组家庭支出清单（附录 A 场景） |
| `tests/datasets/queries.json` | 语义查询黄金集（top-1 命中率校验） |
| `tests/datasets/preferences.json` | 偏好提取测试用例 |
| `tests/datasets/conflicts.json` | 冲突仲裁测试用例 |

### 3. Docker 容器化

| 文件 | 当前状态 | 任务 |
|------|----------|------|
| `backend/Dockerfile` | 空 | 填入 Python + C++ 构建 |
| `backend/docker-compose.yml` | 空 | 填入编排配置 |
| `backend/.env.example` | 已有内容 | 校验/维护模板（当前 6 个变量：DB/API/EMBEDDING/LOG/DATA） |
| `frontend/Dockerfile` | 空 | 填入 Qt5 构建 |
| `frontend/docker-compose.yml` | 空 | 填入编排 |
| `frontend/.env.example` | 空 | 填入模板 |

### 4. 文档补全

- 配合其他开发者更新 `docs/` 下的项目级文档
- 编写效果演示报告（D-01）
- 编写用户手册（D-03）

## 参考文档

| 内容 | 路径 |
|------|------|
| 验收规范 | `docs/AcceptanceTestSpecification.md` |
| 赛题原文 | `docs/OriginProblemDescription.md` |
| 开发计划 | `docs/DEVELOPMENT_PLAN.md` |
