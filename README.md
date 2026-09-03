<div align="center">

# PIXIU · 貔貅

### 面向银河麒麟 OS Agent 的分布式记忆增强系统

*让多台设备上的 Agent 共享、同步并安全使用同一张记忆网络。*

[![Kylin OS](https://img.shields.io/badge/Galaxy%20Kylin%20OS-V11-DA291C?style=flat-square&logo=linux&logoColor=white)](https://www.kylinos.cn/)
[![Status](https://img.shields.io/badge/contest%20status-P0%20整改中-orange?style=flat-square)](docs/AcceptanceTestSpecification.md)
[![Foundation](https://img.shields.io/badge/Foundation-FastAPI%20%2B%20SQLite-009688?style=flat-square)](backend/foundation/docs/ARCHITECTURE.md)
[![Frontend](https://img.shields.io/badge/Memory%20Console-Qt5%20%2F%20UKUI-41CD52?style=flat-square)](frontend/docs/ARCHITECTURE.md)

[赛题与口径](docs/OriginProblemDescription.md) · [验收清单](docs/AcceptanceTestSpecification.md) · [关键问题与接入结论](docs/OS_AGENT_INTEGRATION_ASSESSMENT.md) · [总体架构](docs/ARCHITECTURE.md) · [开发计划](docs/DEVELOPMENT_PLAN.md) · [API](docs/API.md)

</div>

## 项目定位与当前状态

PIXIU 参加麒麟软件“OS Agent 记忆能力优化与应用”赛题。团队的核心创新是一个面向多台设备的、去中心化的全连接记忆网络：可信设备通过 CRDT、Gossip 与反熵对账共享长期记忆，离线可用，重连后收敛，并保留来源、冲突和遗忘审计。

> [!CAUTION]
> **当前仓库尚不能宣称完整赛题验收通过。** 现有代码主体是记忆业务引擎、基础设施和专用记忆控制台；它没有实现完整的多轮 Agent 会话、模型规划循环、工具自主选择、Shell/联网搜索调用与审批闭环。当前向量检索也主要由 SQLite 中的 INT8 扫描承担，尚未把赛方指定的系统向量数据库 SDK 接入生产读写/检索链路。

经过对 [完整赛题要求 PPTX](docs/完整赛题要求.pptx)、本地代码和 openKylin 官方源码的核对，项目采用以下路线：

1. **不从零重造完整 OS Agent。** 以赛方/openKylin 的 `kylin-agent` 与 `agent-runtime` 为 Agent 基座；优先通过 `MemoryProvider` 生命周期和 PIXIU HTTP API 接入，只有在扩展点不足时才做最小、可维护的上游补丁。
2. **PIXIU 聚焦记忆创新。** 完成长短期/中期/长期记忆流转、工具结果沉淀、主动召回、偏好与知识记忆，以及多设备同步。
3. **三个硬门槛单独验收。** 必须在银河麒麟桌面操作系统 V11 部署；向量数据库必须走 `kylin-ai-vector-engine`/官方客户端；文本向量化必须走 `kylin-coreai-embedding`。Debian 降级路径只用于开发回归，不能替代赛题验收。

完整证据、差距矩阵和接入方案见 [OS Agent 接入与赛题差距评估](docs/OS_AGENT_INTEGRATION_ASSESSMENT.md)。

## 关键亮点

- **去中心化全连接记忆网络**：每台设备持有可工作的本地副本；可信节点经 Gossip 实时扩散、反熵周期对账，使用 CRDT 合并并发更新。
- **隐私分域**：仅 `shared:*` 记忆参与设备同步，`user:*` 记忆不离开本机；配对、签名、mTLS 与墓碑回收均有明确协议。
- **多源记忆**：统一接入多轮对话、工具执行结果、用户行为和手动配置，完成清洗、标准化、质量与敏感度判断。
- **偏好与知识双通道**：提取操作习惯、输出风格和安全策略；沉淀工作流、历史案例和可复用模板，并处理版本冲突。
- **混合检索与可追溯证据**：BM25、向量和实体关系图融合，结果关联原始 evidence。
- **精准遗忘**：自然语言定位目标，级联清理关联实体和证据，并通过墓碑在共享网络中传播。

多设备同步是团队的差异化创新，但不是替代赛题硬门槛的理由；优先级始终是 V11、指定双 SDK、完整 OS Agent 接入和可复现量化评测。

## 目标架构

```text
┌────────────────────────────────────────────────────────────┐
│ 官方 OS Agent 基座                                         │
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

## 仓库结构

```text
Project.PIXIU/
├── frontend/                         # PIXIU 记忆控制台（Qt5/UKUI）
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
