<div align="center">

# PIXIU · 貔貅

### 面向银河麒麟 OS Agent 的分布式记忆增强系统

*让多台设备上的 Agent 共享、同步并安全使用同一张记忆网络。*

[![Kylin OS](https://img.shields.io/badge/Galaxy%20Kylin%20OS-V11-DA291C?style=flat-square&logo=linux&logoColor=white)](https://www.kylinos.cn/)
[![Status](https://img.shields.io/badge/contest%20status-P0%20整改中-orange?style=flat-square)](docs/AcceptanceTestSpecification.md)
[![Foundation](https://img.shields.io/badge/Foundation-FastAPI%20%2B%20SQLite-009688?style=flat-square)](backend/foundation/docs/ARCHITECTURE.md)
[![Frontend](https://img.shields.io/badge/Memory%20Console-Qt5%20%2F%20UKUI-41CD52?style=flat-square)](frontend/docs/ARCHITECTURE.md)

[赛题与口径](docs/OriginProblemDescription.md) · [验收清单](docs/AcceptanceTestSpecification.md) · [完整交付主实施计划](docs/IMPLEMENTATION_MASTER_PLAN.md) · [最终交付计划](docs/DELIVERY_PLAN.md) · [已批准架构决策](docs/decisions/0001-use-openkylin-agent-host.md) · [关键问题与接入结论](docs/OS_AGENT_INTEGRATION_ASSESSMENT.md) · [总体架构](docs/ARCHITECTURE.md) · [开发计划](docs/DEVELOPMENT_PLAN.md) · [API](docs/API.md)

</div>

## 项目定位与当前状态

PIXIU 参加麒麟软件“OS Agent 记忆能力优化与应用”赛题。团队的核心创新是一个面向多台设备的、去中心化的全连接记忆网络：可信设备通过 CRDT、Gossip 与反熵对账共享长期记忆，离线可用，重连后收敛，并保留来源、冲突和遗忘审计。

> [!CAUTION]
> **当前仓库尚不能宣称完整赛题验收通过。** 现有代码主体是记忆业务引擎、基础设施和专用记忆控制台；它没有实现完整的多轮 Agent 会话、模型规划循环、工具自主选择、Shell/联网搜索调用与审批闭环。当前向量检索也主要由 SQLite 中的 INT8 扫描承担，尚未把赛方指定的系统向量数据库 SDK 接入生产读写/检索链路。

> [!IMPORTANT]
> **团队决策已批准。** 2026-09-03，华南理工大学 PIXIU 团队负责人批准
> [ADR-0001](docs/decisions/0001-use-openkylin-agent-host.md)：不从零重造完整 OS Agent，
> 以 openKylin `kylin-agent`/`agent-runtime` 为宿主，通过团队原创适配层接入 PIXIU。
> 这是团队工程决策，不得表述成赛方点名指定或书面授权。

经过对两份赛事官方材料、本地代码和 openKylin 官方源码的核对，项目正式采用以下路线：

1. **不从零重造完整 OS Agent。** 这是项目工程选型，不是赛方明示指定。正式材料既没有要求参赛队从零实现标准 Agent，也没有点名授权某个 Agent；PPT 同时警示不得“直接用开源软件作为作品提交”。因此选用 openKylin `kylin-agent` 与 `agent-runtime` 作基座，必须由 PIXIU 原创记忆模块、适配代码、系统 SDK 接线和实测证据形成实质性作品，而非原样转交上游项目。
2. **PIXIU 聚焦记忆创新。** 完成长短期/中期/长期记忆流转、工具结果沉淀、主动召回、偏好与知识记忆，以及多设备同步。
3. **两个官方材料共同执行。** 平台发布的文字方案提供完整赛题、评分和精确提交规则；技术/赛事团队 PPT 补充 V11、双 SDK、交付格式、OS Agent 特征和评审注意事项。二者均为只读权威原件。

完整证据、差距矩阵和接入方案见 [OS Agent 接入与赛题差距评估](docs/OS_AGENT_INTEGRATION_ASSESSMENT.md)。

### 作品与上游边界

| 类别 | 内容 | 对外交付口径 |
|------|------|--------------|
| PIXIU 原创作品 | 记忆引擎、存储/检索/流转、分布式同步、Module E Agent 适配、双 SDK 接线与评测 | 作为团队实现和核心亮点提交证据 |
| openKylin 上游依赖 | `kylin-agent`、`agent-runtime` | 披露固定版本与许可证，不宣称为团队原创，不原样作为作品主体提交 |
| 官方 SDK | Embedding、Vector Engine 客户端 | 作为指定系统能力调用，保存生产调用和严格失败证据 |
| 独立记忆控制台 | `frontend/` | 用于诊断、管理和演示，不称为完整 OS Agent |

## 关键亮点

- **去中心化全连接记忆网络**：每台设备持有可工作的本地副本；可信节点经 Gossip 实时扩散、反熵周期对账，使用 CRDT 合并并发更新。
- **隐私分域**：仅 `shared:*` 记忆参与设备同步，`user:*` 记忆不离开本机；配对、签名、mTLS 与墓碑回收均有明确协议。
- **多源记忆**：统一接入多轮对话、工具执行结果、用户行为和手动配置，完成清洗、标准化、质量与敏感度判断。
- **偏好与知识双通道**：提取操作习惯、输出风格和安全策略；沉淀工作流、历史案例和可复用模板，并处理版本冲突。
- **混合检索与可追溯证据**：BM25、向量和实体关系图融合，结果关联原始 evidence。
- **精准遗忘**：自然语言定位目标，级联清理关联实体和证据，并通过墓碑在共享网络中传播。

多设备同步是团队的差异化创新，但不是替代赛题硬门槛的理由；优先级始终是 V11、指定双 SDK、完整 OS Agent 接入和可复现量化评测。

当前 Agent 记忆接入进度：`POST /memory/write` 已支持独立 `CONVERSATION` 来源，
并将 session/run/turn/tool-call/审批/时间 provenance 与原始正文分离持久化；幂等写入、
上下文预算与生命周期 API、Module E 宿主适配仍在实施中，因此这不是完整 Agent 闭环。

## 目标架构

```text
┌────────────────────────────────────────────────────────────┐
│ 项目选定的 openKylin OS Agent 基座                         │
│ kylin-agent（桌面） + agent-runtime（会话/规划/工具/审批）   │
└───────────────────────────┬────────────────────────────────┘
                            │ MemoryProvider / HTTP adapter
┌───────────────────────────▼────────────────────────────────┐
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

frontend/：现阶段是 PIXIU 记忆控制台和独立演示客户端，不等同于上述完整 Agent。
```

## 赛题硬门槛与当前证据

| 门槛 | 赛方要求 | 当前状态 | 最终通过证据 |
|------|----------|----------|--------------|
| H-01 | 软件部署在银河麒麟桌面操作系统 V11；不满足计 0 分 | 部分具备 V11 构建/桌面记录，仍需按最终版本重验 | V11 安装、启动、全链路视频与机器信息 |
| H-02 | 使用系统向量数据库 SDK | **未通过**：生产检索仍是 SQLite/INT8 扫描 | SDK 建库、写入、查询日志与端到端测试 |
| H-03 | 使用系统 Embedding 接口 | 绑定和适配代码已存在，最终运行证据待补 | `runtime=kylin` 报告、调用日志与故障即失败验证 |

现有 portable 基线（偏好 100%、召回 100%、冲突 96%、P95 115ms）只证明通用软件路径可回归，**不代表 H-01～H-03 或最终比赛性能验收通过**。详见 [验收证据说明](docs/acceptance/README.md)。

## 评分与交付

初评总分 100：技术创新性 30、方案可行性 30、性能指标 25、实用性 10、文档规范性 5。性能基础线为偏好提取准确率 ≥85%、知识检索召回率 ≥85%、检索响应时间 ≤500ms、知识冲突处理正确率 ≥88%。完整逐项清单、复评分值、PPT 交付格式和证据要求见 [验收测试规范](docs/AcceptanceTestSpecification.md)。

PPT 中的饼图显示 32%/32%/26%/11%，是把前四项 95 分自动归一化后的比例，并非新的原始分值；完整评分表仍按 30/30/25/10/5 计 100 分。

团队追加的发布硬门是：最终提供一个可在银河麒麟 V11 图形安装器打开的一体化
`.deb`，内含 PIXIU 记忆服务、控制台和 Module E；软件内可检查版本并一键完成
下载、签名/摘要校验、授权安装、健康检查和恢复。当前 `.deb` 与 GUI 更新基线已经
存在，但 Module E、独立签名/回滚、最终 V11 双 SDK 与全新机/升级取证尚未闭环，
因此状态仍是“部分完成”。完整门禁和 D-01～D-10 台账见
[最终交付与版本管理计划](docs/DELIVERY_PLAN.md)。

从当前差距到最终候选版本的关键路径、阶段门、逐工作包完成定义和预期提交序列见
[完整交付主实施计划](docs/IMPLEMENTATION_MASTER_PLAN.md)。该计划是执行台账；两份
官方赛事原件仍是不可修改的权威要求来源。

## 仓库结构

```text
Project.PIXIU/
├── frontend/                         # PIXIU 记忆控制台（Qt5/UKUI）
├── integrations/kylin_agent/         # Module E：待实现的原创 Agent/MemoryProvider 适配
├── backend/engine/                   # 记忆业务引擎
├── backend/foundation/               # API、存储、检索、流转、同步、评测
├── backend/tests/                    # 自动化测试
├── build/release/                    # Debian/银河麒麟构建与发布画像
├── docs/                             # 架构、API、赛题、验收与报告
└── third_party/
    ├── kylin-agent/                  # openKylin 官方 Agent 桌面端（submodule）
    ├── kylin-agent-runtime/          # openKylin 官方 Agent 运行时（submodule）
    ├── kylin-coreai-embedding/       # 指定文本向量化 SDK（submodule）
    └── libkysdk-vector-engine-client/# 指定向量数据库客户端（submodule）
```

克隆时使用：

```bash
git clone --recurse-submodules <repository-url>
```

平台策略与启动方法见 [快速启动](docs/QUICK_START.md)。任何 `KYSDK=OFF` 或 portable 结果都必须与银河麒麟 V11、`KYSDK=ON` 的最终验收结果分开汇报。
仓库已提供独立 `kylin-v11-native-x86_64` 严格画像和手动原生 CI 工作流；首次
双 SDK 真实写入/检索证据生成前，H-02/H-03 状态仍保持未通过/待最终证据。
