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
[![Status](https://img.shields.io/badge/status-开发中·可安装-blue?style=flat-square)](docs/DEVELOPMENT_PLAN.md)

[总体架构](docs/ARCHITECTURE.md) · [开发计划](docs/DEVELOPMENT_PLAN.md) · [API 规格](docs/API.md) · [验收规范](docs/AcceptanceTestSpecification.md) · [赛题原文](docs/OriginProblemDescription.md)

</div>

---

## 这是什么

**PIXIU** 是面向银河麒麟桌面操作系统 OS Agent 的**记忆优化与高效应用解决方案**，参赛于麒麟软件《OSAgent 记忆优化及高效应用研究》赛题。

我们把目光投向**居家 / 办公的多用户协作场景**：你在书房问的问题、客厅大屏记下的待办、办公电脑沉淀的工作流——本应彼此相通，却被困在一台台孤立的设备里。

PIXIU 构建了一张**无中心节点的分布式记忆网络**，让多设备之间的知识与偏好自由共享、自动同步，并以**神经-符号混合检索**在 500ms 内给出可追溯的精准答案。

> 全程依托现有 OS Agent 基础架构，调用银河麒麟国产桌面操作系统 **KylinSDK**（embedding / OCR / 桌面环境）进行端侧开发，国产化、可离线、轻量化。

> [!NOTE]
> **平台基线：麒麟优先、Debian 可退化运行。** 银河麒麟 OS V11 是首要适配与
> 最终 SDK 验收平台；在其他 Debian 系发行版或缺少 KylinSDK 的环境中，PIXIU
> 必须仍可编译、启动并完成核心记忆流程。专有桌面能力走 Qt 降级路径，embedding
> 走本地特征哈希软件实现；降级结果不计作麒麟 SDK 性能验收。

## 一个属于你的故事

> [!IMPORTANT]
> 记忆不该被一台台设备割裂。下面这个再普通不过的周末，正是 PIXIU 想要改变的日常。

**周六上午，书房。** 林先生是一名在家办公的设计师，家里有三台跑着银河麒麟的设备：书房的工作站、客厅的一体机、还有一台随身的麒麟笔记本。过去，每台设备的 OS Agent 都像一个"失忆"的助手——在书房交代过的事，换到客厅就得从头再说一遍。

**上个月的某天**，林太太用微信发来一张家庭支出清单的照片。林先生顺手让书房工作站的 OS Agent "记一下"。PIXIU 在后台默默完成了一整套动作：调用麒麟 OCR 识别图片 → 后端引擎清洗、标准化并做敏感度评分 → 抽取"国家电网""新奥燃气"等实体并挂载到"水电燃气"类目 → 生成端侧向量写入长期记忆。**林先生什么都没多做，一条结构化、可检索、可追溯的知识就这样沉淀了下来**——而且通过去中心化网络，悄悄同步到了客厅一体机和笔记本上。

**今天下午，客厅。** 林先生靠在沙发上，突然想核对一笔开销，却只记得模糊的片段。他按下全局快捷键，UKUI 桌面角落的悬浮球展开成聊天框，他随口一问：

> 「我们好像在水电燃气方面花了一些钱，花了多少钱来着？」

**不到半秒**，答案浮现：*"2026 年 4 月，你们在水电燃气方面共支出 434.50 元，其中电费 210 元、水费 68.50 元、燃气费 156 元。"* 下方附着一张证据卡，点开就能回溯到那张最初的清单照片。他没有打开任何文件管理器、没有翻聊天记录、更没有逐条加总——**系统替他记住了，也替他算好了**。

**几分钟后**，他想起燃气费记错了，便补了一句"燃气费不是 156，是 186"。PIXIU 的冲突仲裁模块自动识别出与旧记忆的矛盾，以新版本为准，同时完整保留了修改痕迹。临睡前他又说："忘记那张 4 月的支出清单吧。"——系统精准定位目标，连带原始证据与实体关系一并干净地遗忘，不留残影，也不误删别的记忆。

**这一切，发生在三台设备之间，却像在和同一个懂你的助手对话。** 没有云端账号、没有数据外泄、断网依旧可用。这就是 PIXIU 想带给每一位麒麟用户的体验——**让设备彼此相通，让记忆为你所用**。

## 核心亮点

- **去中心化记忆网络** — 每台设备对等运行、无中心服务器；设备配对建立信任后，记忆经 Gossip 实时推送 + 反熵周期对账扩散全网，用 CRDT 自动合并并发修改，断网各自可用、重连自动收敛。同步默认开启，记忆面板「同步」Tab 一站式管理：总开关/暂停传输/附近设备发现、确认式配对（一键发现+目标机弹窗确认）/立即同步/整网退出，main 主干快进自动合并、分叉转人工仲裁。
- **多源融合接入** — 工具执行结果、用户行为、手动配置、OCR 统一接入，自动清洗、标准化与质量校验。
- **偏好动态捕捉** — 操作习惯、输出风格、安全策略自动提取，版本化管理，跨场景适配与回溯；规则与评测标签对齐后，偏好提取准确率实测 100%（15/15，见 [docs/acceptance](docs/acceptance/README.md)）。
- **神经-符号混合检索** — BM25 + 向量 ANN + 实体关系图三通道融合，结构化聚合，证据可追溯。
- **冲突智能仲裁** — 新旧知识矛盾自动检测，以新为准并保留完整审计痕迹。
- **安全与精准遗忘** — 敏感信息识别过滤，自然语言指令驱动级联遗忘。
- **端侧极致轻量** — 调用麒麟 embeddingSDK + INT8 量化 + SQLite，检索 P95 ≤ 500ms。
- **UKUI 原生体验** — Qt5 桌面悬浮球 + 聊天框，全局快捷键唤起，系统通知与主题深度融合。
- **主动递送** — 欢迎页洞察流按最近高质量记忆动态推荐问题，定时简报聚合当日记忆沉淀、「今日简报」一键直达；新录入与您近期关注相关时主动提醒，偏好学习即时通知，每日上限节制打扰。

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

| 指标 | 目标 | 当前实测（2026-08-25 基线） |
|------|------|------|
| 偏好提取准确率 | ≥ 85% | 100%（15/15，达标） |
| 知识检索召回率 | ≥ 85% | 100%（50/50，达标） |
| 知识检索响应时间 | ≤ 500ms (P95) | 115ms（达标） |
| 知识冲突处理正确率 | ≥ 88% | 96%（24/25，达标） |

> 实测值来自 `docs/acceptance/acceptance-baseline-2026-08-24.md` 的刷新基线
> （真实管线 + portable embedding 采集，非桩注入）。

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
│
├── build/release/             ★ 打包与 CICD 脚手架（整包 .deb / staging / production）
│   ├── Makefile               # make deb / publish-staging / publish-production
│   ├── profiles/              # 目标平台画像（麒麟 V11 / Ubuntu）
│   ├── scripts/               # 构建/预置/VM 部署冒烟/发布脚本
│   └── debian/                # deb 元数据与维护脚本
```

## 文档导航

| 文档 | 说明 |
|------|------|
| [开发计划与分工](docs/DEVELOPMENT_PLAN.md) | 团队结构、模块划分、契约定义 |
| [总体架构](docs/ARCHITECTURE.md) | 分层设计、数据模型、端到端流程 |
| [快速启动](docs/QUICK_START.md) | 本地开发与整包安装快速路径 |
| [打包发布 CICD](build/release/README.md) | 整包 .deb、staging/production 发布、麒麟 VM 实测 |
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
