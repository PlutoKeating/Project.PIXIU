<div align="center">

# PIXIU · 貔貅

### 面向银河麒麟 OS Agent 的去中心化分布式记忆系统

*聚财守忆 —— 让每一台设备的记忆，彼此相通。*

<br/>

[![Kylin OS](https://img.shields.io/badge/Kylin%20OS-V11-DA291C?style=flat-square&logo=linux&logoColor=white)](https://www.kylinos.cn/)
[![KylinSDK](https://img.shields.io/badge/KylinSDK-V3.0-0066CC?style=flat-square)](docs/kylin_sdk_docs/README.md)
[![Engine](https://img.shields.io/badge/Engine-Python%203.10%20%2B%20C%2B%2B-3776AB?style=flat-square&logo=python&logoColor=white)](backend/engine/docs/ARCHITECTURE.md)
[![Foundation](https://img.shields.io/badge/Foundation-FastAPI%20%2B%20SQLite-009688?style=flat-square)](backend/foundation/docs/ARCHITECTURE.md)
[![Frontend](https://img.shields.io/badge/Frontend-Qt5%20%2F%20UKUI-41CD52?style=flat-square&logo=qt&logoColor=white)](frontend/docs/ARCHITECTURE.md)
[![Latency](https://img.shields.io/badge/检索延迟-%E2%89%A4500ms-success?style=flat-square)](docs/AcceptanceTestSpecification.md)
[![Status](https://img.shields.io/badge/status-交付版-blue?style=flat-square)](docs/DEVELOPMENT_PLAN.md)

[总体架构](docs/ARCHITECTURE.md) · [开发计划](docs/DEVELOPMENT_PLAN.md) · [API 规格](docs/API.md) · [验收规范](docs/AcceptanceTestSpecification.md) · [赛题原文](docs/OriginProblemDescription.md)

</div>

---

## 这是什么

**PIXIU** 是面向银河麒麟桌面操作系统 OS Agent 的**记忆优化与高效应用解决方案**，参赛于麒麟软件《OSAgent 记忆优化及高效应用研究》赛题。

我们把目光投向**居家 / 办公的多用户协作场景**：你在书房问的问题、客厅大屏记下的待办、办公电脑沉淀的工作流——本应彼此相通，却被困在一台台孤立的设备里。

PIXIU 构建了一张**无中心节点的分布式记忆网络**，让多设备之间的知识与偏好自由共享、自动同步，并以**神经-符号混合检索**在 500ms 内给出可追溯的精准答案。

> 全程依托现有 OS Agent 基础架构，调用银河麒麟国产桌面操作系统 **KylinSDK**（embedding / OCR / 桌面环境）进行端侧开发，国产化、可离线、轻量化。

## 典型应用背景

> [!IMPORTANT]
> 记忆不该被一台台设备割裂。下面这个再普通不过的周末，正是 PIXIU 想要改变的日常。

**周六上午，书房。** 林先生是一名在家办公的设计师，家里有三台跑着银河麒麟的设备：书房的工作站、客厅的一体机、还有一台随身的麒麟笔记本。过去，每台设备的 OS Agent 都像一个"失忆"的助手——在书房交代过的事，换到客厅就得从头再说一遍。

**上个月的某天**，林太太用微信发来一张家庭支出清单的照片。林先生顺手让书房工作站的 OS Agent "记一下"。PIXIU 在后台默默完成了一整套动作：调用麒麟 OCR 识别图片 → 后端引擎清洗、标准化并做敏感度评分 → 抽取"国家电网""新奥燃气"等实体并挂载到"水电燃气"类目 → 生成端侧向量写入长期记忆。**林先生什么都没多做，一条结构化、可检索、可追溯的知识就这样沉淀了下来**——而且通过去中心化网络，悄悄同步到了客厅一体机和笔记本上。

**今天下午，客厅。** 林先生靠在沙发上，突然想核对一笔开销，却只记得模糊的片段。他按下全局快捷键，UKUI 桌面角落的悬浮球展开成聊天框，他随口一问：

> 「我们好像在水电燃气方面花了一些钱，花了多少钱来着？」

**不到半秒**，答案浮现：*"2026 年 4 月，你们在水电燃气方面共支出 434.50 元，其中电费 210 元、水费 68.50 元、燃气费 156 元。"* 下方附着一张证据卡，点开就能回溯到那张最初的清单照片。他没有打开任何文件管理器、没有翻聊天记录、更没有逐条加总——**系统替他记住了，也替他算好了**。

**几分钟后**，他想起燃气费记错了，便补了一句"燃气费不是 156，是 186"。PIXIU 的冲突仲裁模块自动识别出与旧记忆的矛盾，以新版本为准，同时完整保留了修改痕迹。临睡前他又说："忘记那张 4 月的支出清单吧。"——系统精准定位目标，连带原始证据与实体关系一并干净地遗忘，不留残影，也不误删别的记忆。

**这一切，发生在三台设备之间，却像在和同一个懂你的助手对话。** 记忆数据无需云端
账号、保留在可信设备中，断网时仍可写入与检索；联网推理由系统麒灵模型或用户选择的
官方服务完成。这就是 PIXIU 想带给每一位麒麟用户的体验——**让设备彼此相通，让记忆为你所用**。

## 核心亮点

- **去中心化记忆网络** — 每台设备对等运行、无中心服务器；设备配对建立信任后，记忆经 Gossip 实时推送 + 反熵周期对账扩散全网，用 CRDT 自动合并并发修改，断网各自可用、重连自动收敛。
- **多源融合接入** — 工具执行结果、用户行为、手动配置、OCR 统一接入，自动清洗、标准化与质量校验。
- **偏好动态捕捉** — 操作习惯、输出风格、安全策略自动提取，版本化管理，跨场景适配与回溯。
- **神经-符号混合检索** — BM25 + 向量 ANN + 实体关系图三通道融合，结构化聚合，证据可追溯。
- **冲突智能仲裁** — 新旧知识矛盾自动检测，以新为准并保留完整审计痕迹。
- **安全与精准遗忘** — 敏感信息识别过滤，自然语言指令驱动级联遗忘。
- **端侧极致轻量** — 调用麒麟 Embedding 与 Vector Engine SDK，检索 P95 ≤ 500ms。
- **UKUI 原生体验** — Qt5 桌面悬浮球 + 聊天框，全局快捷键唤起，系统通知与主题深度融合。

## 系统架构

```
┌────────────────────────────────────────────────────────────┐
│ 项目选定的 openKylin OS Agent 基座                         │
│ kylin-agent（桌面） + agent-runtime（会话/规划/工具/审批）   │
└────────────────────┬───────────────────┬───────────────────┘
                     │                   └─ Kylin GenAI 回环适配 → 系统云模型
                     │ MemoryProvider / HTTP adapter
┌────────────────────▼───────────────────────────────────────┐
│ PIXIU 记忆系统                                              │
│ engine：多源接入/偏好/知识/冲突/安全                         │
│ foundation：API/存储/检索/记忆流转/P2P CRDT/评测             │
└───────────────┬───────────────────────────┬────────────────┘
                │                           │
     Kylin Embedding SDK          Kylin Vector Engine SDK
                │                           │
┌───────────────▼───────────────────────────▼────────────────┐
│ 多台银河麒麟 V11 设备：本地副本 + 可信 P2P 同步             │
└────────────────────────────────────────────────────────────┘

```

各模块完全解耦，互不依赖代码实现，详情见 [开发计划与分工](docs/DEVELOPMENT_PLAN.md)。

## 技术栈

| 层面 | 选型 |
|------|------|
| 前端 (Module A) | C++17 · Qt5 Widgets · UKUI · KylinSDK（快捷键/通知/主题/Qt 扩展控件） |
| 引擎 (Module B) | Python 3.10 · C++（KylinEmbedding shim） |
| 基础设施 (Module C) | Python 3.10 · FastAPI · asyncio · SQLite(WAL) · FTS5 · hnswlib · CRDT |
| 存储 | Kylin Vector Engine · SQLite (WAL) · FTS5 · 邻接表图 |
| AI | 麒麟 `coreai/embedding`（文本/图像向量化）· Kylin GenAI 系统云模型 · OCR · INT8 量化 |
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
├── frontend/                         # PIXIU 记忆控制台（Qt5/UKUI）
├── integrations/kylin_agent/         # Module E：原创 Agent/MemoryProvider 适配与契约测试
├── backend/engine/                   # 记忆业务引擎
├── backend/foundation/               # API、存储、检索、流转、同步、评测
├── backend/tests/                    # 自动化测试
├── build/release/                    # Debian/银河麒麟构建、发布画像与交付校验工具
├── docs/                             # 架构、API、赛题、验收与报告
├── submission/                       # 打开即见 00 说明和官方 01～05 五类交付实物
└── third_party/
    ├── kylin-agent/                  # openKylin 官方 Agent 桌面端（submodule）
    ├── kylin-agent-runtime/          # openKylin 官方 Agent 运行时（submodule）
    ├── kylin-coreai-embedding/       # 指定文本向量化 SDK（submodule）
    └── libkysdk-vector-engine-client/# 指定向量数据库客户端（submodule）
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
