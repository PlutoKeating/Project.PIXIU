# AGENT.md

给专业 Agent 的开发规范。本文件约束所有由 AI Agent 执行的项目开发、整理、修复、文档和交付工作。

---

## 1. 开工前强制阅读流程

每一个用户需求开始操刀前，Agent 必须先阅读并理解项目文档。没有完成本节阅读，不得开始修改文件。

### 1.1 必读根目录文档

每次需求开始前必须阅读：

- `README.md` —— 项目总览与故事
- `docs/ARCHITECTURE.md` —— 总体架构（分层、数据模型、业务全链路、去中心化同步）
- `docs/API.md` —— 接口约定（当前为占位，空白时以各模块 `ARCHITECTURE.md` 的 API 摘要为准）

如任务涉及赛题目标或验收口径，还必须阅读：

- `docs/OriginProblemDescription.md` —— 赛题原文与附录 A 场景
- `docs/AcceptanceTestSpecification.md` —— 功能/性能/交付验收条目

> 注意：本仓库**无根级** `ARCHITECTURE.md` / `QUICK_START.md` / `.env.example`，这些文件位于各模块目录下（见 §1.2）。

### 1.2 必读模块文档

本项目当前有两个二级核心模块：**后端记忆服务（`backend/`）** 与 **UKUI 桌面前端（`frontend/`）**。模块文档统一位于各自的 `docs/` 子目录。

如果任务涉及某个模块，Agent 必须阅读该模块文档，以 `README.md` 和 `ARCHITECTURE.md` 为主：

- 前端任务：阅读 `frontend/docs/README.md`、`frontend/docs/ARCHITECTURE.md`
- 后端任务：阅读 `backend/docs/README.md`、`backend/docs/ARCHITECTURE.md`

如任务涉及模块启动、环境变量、脚本或部署，还必须阅读该模块的：

- `<module>/docs/QUICK_START.md`
- `<module>/.env.example`
- `<module>/scripts/` 相关脚本

> 涉及**多设备记忆共享/去中心化同步**的任务（CRDT、Gossip、反熵对账、设备配对、墓碑回收等），必须先读 `backend/docs/ARCHITECTURE.md` 的「分布式同步层」一章，并注意区分：同步层（CRDT）解决数据层并发，M4 模块解决知识层矛盾，二者正交、不可混淆。
>
> 说明：早期文档曾提及的「开发者前端 `backfrontend/`」模块当前**不存在**，已从规范中移除；如未来新增，再补充对应必读项。

### 1.3 阅读后的执行要求

Agent 必须把文档中确认的项目结构、API 约定、模块边界、环境变量和已有工作流作为实现约束。不得凭记忆、猜测或通用经验覆盖本项目文档。

如果文档缺失、过时或互相矛盾，Agent 必须先说明冲突，再基于当前代码和用户最新要求做最小必要变更。

---

## 2. 核心职责

Agent 的目标不是“尽快改完”，而是在本地完成可追踪、可回滚、可审查的工程变更。

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
git add <changed-files>
git commit -m "<clear local commit message>"
```

执行原则：

- 一个逻辑变更一个提交。
- 文档整理、结构调整、功能修改、修复问题应尽量分开提交。
- 提交信息必须说明真实意图，不允许使用 `update`、`fix`、`misc` 这类无法审查的消息。
- 提交前必须检查变更范围，避免把 `.env`、构建产物、依赖目录、缓存、本地数据库等内容纳入提交。
- 如果当前环境缺少 Git 命令，应明确告知用户，并继续保证文件变更本身可审查。

### 3.2 严令禁止 git push

Agent 严令禁止执行任何远程推送命令，包括但不限于：

```bash
git push
git push origin <branch>
git push --force
git push --force-with-lease
git push --tags
```

禁止原因：

- 远程分支会影响多人协作和发布流水线。
- 推送可能触发 CI/CD、部署、合并规则或生产流程。
- 远程发布权必须由人类开发者或项目维护者控制。

Agent 只允许在本地完成 commit。是否 push、何时 push、push 到哪个远程分支，必须由 Human 决定并执行。

---

## 4. 分支工作流

本项目采用面向多人协作的标准环境流：

```text
personal feature branch -> staging branch -> production branch
```

Agent 必须默认理解以下含义：

- `feature/<name>` 或个人特性分支：开发和修复的工作区。
- `staging`：集成验证分支，对应预生产或测试环境。
- `production`：生产发布分支，只接受已经验证并批准的变更。

Agent 的工作边界：

- 可以在当前本地分支上修改、暂存、提交。
- 不得自行把变更合并到 `staging` 或 `production`。
- 不得自行创建远程分支或推送远程。
- 如果用户要求涉及 `staging` 或 `production`，必须先说明风险，并只在本地准备变更。

推荐流程：

1. 从最新的个人特性分支开始工作。
2. 小步提交本地 commit。
3. 本地验证通过后，交给 Human 审查。
4. Human 负责 push、创建 Pull Request / Merge Request、触发 CI、合并到 `staging`。
5. `staging` 验证通过后，由 Human 或发布负责人合并到 `production`。

---

## 5. 本地开发规范

修改前：

- 完成“开工前强制阅读流程”。
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

---

## 6. 文档和流程参考

这些规则参考了主流 Git 协作实践：

- GitHub Flow: https://docs.github.com/en/get-started/using-github/github-flow
- GitLab Flow best practices: https://about.gitlab.com/topics/version-control/what-are-gitlab-flow-best-practices/
- GitLab branching strategies: https://docs.gitlab.com/user/project/repository/branches/strategies/
- Atlassian Gitflow workflow: https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow