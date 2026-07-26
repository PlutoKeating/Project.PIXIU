# AGENTS.md

给专业 Agent 的开发规范。本文件约束所有由 AI Agent 执行的项目开发、整理、修复、文档和交付工作。

---

## 1. 开工前强制阅读流程

每一个用户需求开始操刀前，Agent 必须先阅读并理解项目文档。没有完成本节阅读，不得开始修改文件。

### 1.1 必读根目录文档

每次需求开始前必须阅读：

- `README.md` —— 项目总览与故事
- `docs/DEVELOPMENT_PLAN.md` —— 开发计划、模块划分、契约定义
- `docs/ARCHITECTURE.md` —— 总体架构（分层、数据模型、业务全链路）
- `docs/API.md` —— API 端点规格（前后端通信契约）

如任务涉及赛题目标或验收口径，还必须阅读：

- `docs/OriginProblemDescription.md` —— 赛题原文与附录 A 场景
- `docs/AcceptanceTestSpecification.md` —— 功能/性能/交付验收条目

### 1.2 必读模块文档

本项目按架构维度拆分为三个独立开发模块 + 一个支持岗位：

| 模块 | 目录 | 文档路径 |
|------|------|----------|
| **Module A** — UKUI 桌面客户端 | `frontend/` | `frontend/docs/ARCHITECTURE.md`、`frontend/docs/DEV_TASKS.md` |
| **Module B** — 记忆业务引擎 | `backend/engine/` | `backend/engine/docs/ARCHITECTURE.md`、`backend/engine/docs/DEV_TASKS.md` |
| **Module C** — 后台基础设施 | `backend/foundation/` | `backend/foundation/docs/ARCHITECTURE.md`、`backend/foundation/docs/DEV_TASKS.md` |
| **Module D** — 测试与工具 | `backend/scripts/`、`backend/tests/` | `backend/docs/SUPPORT_TASKS.md` |

如果任务涉及某个模块，Agent 必须阅读该模块的全部文档。

> 涉及**多设备记忆共享/去中心化同步**的任务（CRDT、Gossip、反熵对账、设备配对、墓碑回收等），必须先读 `backend/foundation/docs/ARCHITECTURE.md` 的「sync/ —— P2P CRDT 同步」一章。

### 1.3 禁止跨模块修改

Agent 须严格遵守 [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) 第 5.1 节的文件归属铁律：

| 任务涉及模块 | 可修改的文件范围 | 严禁触碰 |
|-------------|-----------------|----------|
| Module A | `frontend/` 全部 | `backend/` 任何文件 |
| Module B | `backend/engine/` + `backend/foundation/core/`（仅接口） | `backend/foundation/api/storage/retrieval/flow/sync/eval/` |
| Module C | `backend/foundation/`（engine 除外） | `backend/engine/` 任何文件 |

### 1.4 阅读后的执行要求

Agent 必须把文档中确认的项目结构、API 约定、模块边界、环境变量和已有工作流作为实现约束。不得凭记忆、猜测或通用经验覆盖本项目文档。

如果文档缺失、过时或互相矛盾，Agent 必须先说明冲突，再基于当前代码和用户最新要求做最小必要变更。

---

## 2. 核心职责

Agent 的目标不是"尽快改完"，而是在本地完成可追踪、可回滚、可审查的工程变更。

必须做到：

- 先理解当前仓库结构、现有代码风格、已有文档和用户的最新要求。
- 只修改与任务直接相关的文件，不做无关重构。
- 每次改动后进行必要的本地验证，例如结构检查、类型检查、测试、构建或人工可读核对。
- 在回复用户时说明做了什么、哪些检查通过、哪些检查无法执行以及原因。

---

## 3. Git 强制规则

### 3.1 必须经常本地提交

Agent 必须经常执行本地 Git 暂存和提交：

```bash
git diff # 注意首先检查现有的所有修改，如果出现预料之外的文件则需要在之后单独创建commit
git add <files to be committed>
git commit -m "<clear local commit message>"
git diff # 注意时刻避免孤儿文件
```

执行原则：

- 一个逻辑变更一个提交。
- 提交信息必须标注模块前缀：`feat(engine/ingest):`、`fix(foundation/retrieval):`、`feat(frontend):`
- 禁止跨模块的混合提交。

### 3.2 严令禁止 git push

Agent 严令禁止执行任何远程推送命令，包括但不限于：

```bash
git push
git push origin <branch>
git push --force
git push --force-with-lease
git push --tags
```

---

## 4. 分支工作流

本项目采用面向多人协作的标准环境流：

```text
personal feature branch -> staging branch -> production branch
```

Agent 的工作边界：

- 可以在当前本地分支上修改、暂存、提交。
- 不得自行把变更合并到 `staging` 或 `production`。
- 不得自行创建远程分支或推送远程。

推荐流程：

1. 从最新的个人特性分支开始工作。
2. 小步提交本地 commit。
3. 本地验证通过后，交给 Human 审查。
4. Human 负责 push、创建 Pull Request / Merge Request、触发 CI、合并到 `staging`。

---

## 5. 本地开发规范

修改前：

- 完成"开工前强制阅读流程"。
- 查看相关配置文件、入口文件、类型定义和调用链。
- 确认任务范围，避免误改其他模块。
- 检查当前工作区是否已有用户未提交改动，不得回滚不属于自己的改动。

修改中：

- 保持改动小而清晰。
- 复用现有模式和依赖，不轻易引入新框架。
- 不把密钥、令牌、私有地址、个人机器路径写入仓库文档或源码。
- 不提交 `.env` 的真实内容，只维护 `.env.example` 模板。

修改后：

- 执行与改动匹配的验证。
- 检查目录结构是否符合项目约定。
- 本地 `git add` 和 `git commit`，保持审查边界清晰。
- 回复用户时列出文件、验证结果和未完成风险。
