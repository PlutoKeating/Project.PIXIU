# PIXIU 后端 · 记忆服务守护进程（Memory Daemon）

> 本文用通俗语言说明**后端做了哪些事**、**用什么技术实现**、以及**怎么把它跑起来**。
> 想了解内部模块如何协作，请看同目录的 [`ARCHITECTURE.md`](./ARCHITECTURE.md)；想了解整个产品，请看仓库根目录 [`README.md`](../../README.md)。

---

## 一句话介绍

PIXIU 后端是一个**常驻在麒麟设备本地的记忆服务**。它把 OS Agent 在各处产生的零散信息（工具执行结果、用户操作行为、手动配置、图片 OCR 文字）接收进来，清洗成规整、可检索、可追溯的"记忆"，并在用户提问时于 **500ms 内**给出带证据的精准答案。多台设备上的同一个服务还能**互相同步记忆**，且全程**不依赖云端、断网可用**。

---

## 它解决了什么问题

OS Agent 的记忆此前面临几个痛点：来源杂、质量参差、偏好提取不准、新旧知识会打架、检索只能"对关键词"、敏感信息难管控。PIXIU 后端针对性地提供了 7 项能力（对应赛题要求 1~7）：

- **多源统一接入** — 工具结果、用户行为、手动配置、OCR 四类来源走同一个入口，自动去噪、去重、补缺、标准化，并打质量分。
- **偏好动态捕捉** — 自动识别用户的操作习惯、输出风格、安全策略偏好，做版本化管理，支持跨场景复用和历史回溯。
- **知识结构化整合** — 把信息整理成事实 / 工作流 / 案例 / 模板四类结构化知识，建立实体-关系图。
- **混合检索** — BM25 全文 + 向量语义 + 实体关系图三通道并行检索，融合重排后聚合出答案，并附上可点击追溯的原始证据。
- **冲突智能仲裁** — 新信息和旧记忆矛盾时自动检测，以新为准，同时完整保留修改审计痕迹。
- **安全与精准遗忘** — 自动识别身份证、银行卡等敏感信息并过滤；支持用自然语言下达遗忘指令（如"忘记那张 4 月支出清单"）做级联清理。
- **记忆流转兼容** — 与 OS Agent 的短期、中期记忆双向流转，长期沉淀有价值的内容。

此外还有：

- **去中心化同步** — 多设备对等组网，基于 CRDT + Gossip 自动合并记忆，无中心服务器、无单点故障。
- **量化评测框架** — 一套可复现的脚本，验证偏好提取准确率、检索召回率、延迟、冲突处理正确率等指标。

---

## 技术栈

| 层面 | 选型 | 说明 |
|------|------|------|
| 编排语言 | **Python 3.10** | 业务逻辑、模块编排、API 服务 |
| 原生扩展 | **C++17** | embedding 的 SDK 绑定层（性能敏感、需对接 C 接口）|
| Web 框架 | **FastAPI + Uvicorn** | 提供 localhost HTTP / WebSocket 接口 |
| 异步运行时 | **asyncio** | 写入异步化、检索三通道并行 |
| 存储 | **SQLite（WAL 模式）** | 单文件、零运维、端侧轻量 |
| 全文检索 | **SQLite FTS5（BM25）** | 关键词通道 |
| 向量检索 | **sqlite-vec / hnswlib（INT8 量化）** | 语义 ANN 通道 |
| 图存储 | **SQLite 邻接表** | 实体-关系图通道，无需额外图数据库 |
| 向量化 | 麒麟 **`coreai/embedding`** C 接口 | 文本/图像向量化（强制使用麒麟 SDK）|
| OCR / 文本生成 | 麒麟 AI SDK 9.4.1 / 9.5.1 | 图片接入、离线抽取（仅写入路径）|
| 分布式同步 | 自研 **CRDT + mDNS/Gossip + TLS** | 去中心化对等同步 |

> **核心红线**：在线检索路径**禁用 LLM 与网络**，只用本地 embedding + SQL + 图遍历，确保 P95 ≤ 500ms。

---

## 构建与工具链

| 用途 | 工具 |
|------|------|
| 依赖管理 | `pip` + `requirements.txt`（或 `pyproject.toml`）|
| 原生扩展构建 | `CMake` + `pybind11`（封装 `coreai/embedding`）|
| 运行 | `uvicorn pixiu.api.http_app:app` |
| 测试 | `pytest`（含 `MockEmbedding` 离线后端）|
| 评测 | `scripts/eval.py`（指标回归）|
| 容器化 | `Dockerfile` + `docker-compose.yml`（开发联调）|
| 打包部署 | `.deb`（端侧）/ systemd 守护进程 |

> **开发机友好**：非麒麟环境下可启用 `MockEmbedding`，整条写入→检索→遗忘链路可离线跑通与单测。

---

## 目录结构

```
backend/
├── pixiu/
│   ├── api/          # 对外接口（HTTP / WebSocket / D-Bus / Unix socket）
│   ├── m1_ingest/    # 多源数据接入：清洗、标准化、质量校验
│   ├── m2_preference/# 偏好动态捕捉：提取、版本化、跨场景适配
│   ├── m3_knowledge/ # 知识结构化整合 + 实体关系图 + 向量写入
│   ├── m4_conflict/  # 新旧知识冲突仲裁与审计
│   ├── m5_retrieval/ # 混合检索：路由 / BM25 / ANN / Graph / 融合 / 重排 / 组装
│   ├── m6_flow/      # 短/中/长期记忆流转
│   ├── m7_security/  # 敏感识别 + 自然语言精准遗忘
│   ├── m8_eval/      # 量化评测框架
│   ├── kylin/        # KylinSDK 适配层（embedding C++ shim）
│   ├── storage/      # SQLite + 索引 + 仓储
│   ├── sync/         # P2P CRDT 同步
│   └── core/         # 数据模型、配置、日志、ID 生成
├── scripts/          # 建库 / 评测 / 压测脚本
└── docs/             # 本目录文档
```

---

## 快速开始

详细步骤见 [`QUICK_START.md`](./QUICK_START.md)，环境变量模板见 [`../.env.example`](../.env.example)。核心流程：

1. 安装依赖：`pip install -r requirements.txt`
2. 配置环境变量（embedding 后端选 `mock` 或 `kylin`、监听端口、数据库路径等）
3. 初始化数据库：`python scripts/init_db.py`
4. 启动服务：`uvicorn pixiu.api.http_app:app --host 127.0.0.1 --port 8765`
5. 运行评测：`python scripts/eval.py`

---

## 对外接口速览

| 方法 | 路径 | 模块 | 作用 |
|------|------|------|------|
| POST | `/memory/write` | M1 | 多源数据统一写入 |
| POST | `/memory/query` | M5 | 混合检索，返回答案 + 证据 |
| POST | `/preference/extract` | M2 | 触发偏好提取 |
| GET | `/preference/{id}/history` | M2 | 偏好版本回溯 |
| POST | `/forget` | M7 | 自然语言遗忘指令 |
| GET | `/conflicts` | M4 | 冲突记录审计 |
| POST | `/memory/flow/promote` | M6 | 短/中期 → 长期流转 |
| WS | `/events` | 全部 | 事件推送（供前端通知）|

接口字段、数据模型、性能预算等完整设计见 [`ARCHITECTURE.md`](./ARCHITECTURE.md)。
