<div align="center">

# PIXIU · 貔貅

### 面向银河麒麟 OS Agent 的去中心化分布式记忆系统

*聚财守忆 —— 让每一台设备的记忆，彼此相通。*

<br/>

[![Kylin OS](https://img.shields.io/badge/Kylin%20OS-V10-DA291C?style=flat-square&logo=linux&logoColor=white)](https://www.kylinos.cn/)
[![KylinSDK](https://img.shields.io/badge/KylinSDK-V3.0-0066CC?style=flat-square)](docs/kylin_sdk_docs/README.md)
[![Engine](https://img.shields.io/badge/Engine-Python%203.10%20%2B%20C%2B%2B-3776AB?style=flat-square&logo=python&logoColor=white)](backend/engine/docs/ARCHITECTURE.md)
[![Foundation](https://img.shields.io/badge/Foundation-FastAPI%20%2B%20SQLite-009688?style=flat-square)](backend/foundation/docs/ARCHITECTURE.md)
[![Frontend](https://img.shields.io/badge/Frontend-Qt5%20%2F%20UKUI-41CD52?style=flat-square&logo=qt&logoColor=white)](frontend/docs/ARCHITECTURE.md)
[![Latency](https://img.shields.io/badge/检索延迟-%E2%89%A4500ms-success?style=flat-square)](docs/AcceptanceTestSpecification.md)
[![Status](https://img.shields.io/badge/status-设计阶段-yellow?style=flat-square)](docs/DEVELOPMENT_PLAN.md)

[总体架构](docs/ARCHITECTURE.md) · [开发计划](docs/DEVELOPMENT_PLAN.md) · [API 规格](docs/API.md) · [验收规范](docs/AcceptanceTestSpecification.md) · [赛题原文](docs/OriginProblemDescription.md)

</div>

---

## 这是什么

**PIXIU** 是面向银河麒麟桌面操作系统 OS Agent 的**记忆优化与高效应用解决方案**，参赛于麒麟软件《OSAgent 记忆优化及高效应用研究》赛题。

我们把目光投向**居家 / 办公的多用户协作场景**：你在书房问的问题、客厅大屏记下的待办、办公电脑沉淀的工作流——本应彼此相通，却被困在一台台孤立的设备里。

PIXIU 构建了一张**无中心节点的分布式记忆网络**，让多设备之间的知识与偏好自由共享、自动同步，并以**神经-符号混合检索**在 500ms 内给出可追溯的精准答案。

> 全程依托现有 OS Agent 基础架构，调用银河麒麟国产桌面操作系统 **KylinSDK**（embedding / OCR / 桌面环境）进行端侧开发，国产化、可离线、轻量化。

## 核心亮点

- **去中心化记忆网络** — 每台设备对等运行、无中心服务器；设备配对建立信任后，记忆经 Gossip 实时推送 + 反熵周期对账扩散全网，用 CRDT 自动合并并发修改，断网各自可用、重连自动收敛。
- **多源融合接入** — 工具执行结果、用户行为、手动配置、OCR 统一接入，自动清洗、标准化与质量校验。
- **偏好动态捕捉** — 操作习惯、输出风格、安全策略自动提取，版本化管理，跨场景适配与回溯。
- **神经-符号混合检索** — BM25 + 向量 ANN + 实体关系图三通道融合，结构化聚合，证据可追溯。
- **冲突智能仲裁** — 新旧知识矛盾自动检测，以新为准并保留完整审计痕迹。
- **安全与精准遗忘** — 敏感信息识别过滤，自然语言指令驱动级联遗忘。
- **端侧极致轻量** — 调用麒麟 embeddingSDK + INT8 量化 + SQLite，检索 P95 ≤ 500ms。
- **UKUI 原生体验** — Qt5 桌面悬浮球 + 聊天框，全局快捷键唤起，系统通知与主题深度融合。

## 系统架构

```
┌──────────────────────────────────────────────────────────┐
│  Module A: UKUI 桌面客户端 frontend/                      │
│  悬浮球 + 聊天框 + 记忆面板 (Qt5 + KylinSDK)               │
│  独立 C++ 项目，固定 API 契约与后端通信                     │
└───────────────────────────┬──────────────────────────────┘
                            │  HTTP REST · WS · D-Bus
┌───────────────────────────┴──────────────────────────────┐
│  后端 backend/                                            │
│                                                          │
│  Module B: 记忆业务引擎 (engine/)                          │
│  多源接入 · 偏好捕捉 · 知识结构化 · 冲突仲裁               │
│  安全/遗忘 · KylinEmbedding 适配                          │
│                                                          │
│  Module C: 后台基础设施 (foundation/)                      │
│  API 网关 · 存储(SQLite) · 混合检索 · 记忆流转             │
│  P2P 同步(CRDT) · 评测框架                                │
└──────────────────────────────────────────────────────────┘
```

各模块完全解耦，互不依赖代码实现，详情见 [开发计划与分工](docs/DEVELOPMENT_PLAN.md)。

## 技术栈

| 层面 | 选型 |
|------|------|
| 前端 (Module A) | C++17 · Qt5 Widgets · UKUI · KylinSDK（快捷键/通知/主题/Qt 扩展控件） |
| 引擎 (Module B) | Python 3.10 · C++（KylinEmbedding shim） |
| 基础设施 (Module C) | Python 3.10 · FastAPI · asyncio · SQLite(WAL) · FTS5 · hnswlib · CRDT |
| 存储 | SQLite (WAL) · FTS5 · sqlite-vec/hnswlib · 邻接表图 |
| AI | 麒麟 `coreai/embedding`（文本/图像向量化）· OCR · INT8 量化 |
| 分布式 | CRDT · mDNS/Gossip · TLS |

## 性能指标

| 指标 | 目标 |
|------|------|
| 偏好提取准确率 | ≥ 85% |
| 知识检索召回率 | ≥ 85% |
| 知识检索响应时间 | ≤ 500ms (P95) |
| 知识冲突处理正确率 | ≥ 88% |

## 项目结构

```
Project.PIXIU/
├── docs/                      # 项目根文档
│   ├── ARCHITECTURE.md        # 总体架构
│   ├── DEVELOPMENT_PLAN.md    # 开发计划与分工
│   ├── API.md                 # API 端点规格
│   ├── QUICK_START.md         # 快速启动
│   ├── OriginProblemDescription.md  # 赛题原文
│   ├── AcceptanceTestSpecification.md  # 验收规范
│   └── kylin_sdk_docs/        # KylinSDK 参考
│
├── backend/                   # 后端
│   ├── engine/                ★ Module B: 记忆业务引擎
│   ├── foundation/            ★ Module C: 后台基础设施
│   ├── scripts/               # 工具脚本
│   ├── tests/                 # 测试
│   └── docs/                  # 后端文档
│
├── frontend/                  ★ Module A: UKUI 桌面客户端
│   └── docs/                  # 前端开发文档
```

## 文档导航

| 文档 | 说明 |
|------|------|
| [开发计划与分工](docs/DEVELOPMENT_PLAN.md) | 团队结构、模块划分、契约定义 |
| [总体架构](docs/ARCHITECTURE.md) | 分层设计、数据模型、端到端流程 |
| [API 规格](docs/API.md) | 前端↔后端通信契约（12 端点）|
| [Module A 前端架构](frontend/docs/ARCHITECTURE.md) | UKUI 交互形态、组件树、kysdk 集成 |
| [Module B 引擎架构](backend/engine/docs/ARCHITECTURE.md) | 引擎内部设计与实现机制 |
| [Module C 基础设施架构](backend/foundation/docs/ARCHITECTURE.md) | 检索、存储、同步设计 |
| [验收测试规范](docs/AcceptanceTestSpecification.md) | 功能/性能/交付逐条验收条目 |
| [赛题原文](docs/OriginProblemDescription.md) | 比赛方案与附录 A 场景 |
| [KylinSDK 指南](docs/kylin_sdk_docs/README.md) | 麒麟 V3.0 SDK API 参考 |

---

<div align="center">

依托银河麒麟国产桌面操作系统与 KylinSDK 构建 · 国产化 · 端侧 · 可离线

</div>
