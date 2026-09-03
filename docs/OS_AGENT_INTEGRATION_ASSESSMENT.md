# OS Agent 接入与赛题差距评估

> 核对日期：2026-09-03
>
> 结论适用：赛题设计、实现优先级、验收与答辩口径
> 权威输入：[完整赛题要求 PPTX](完整赛题要求.pptx)、[赛题文字方案](OriginProblemDescription.md)、本仓库代码、`third_party/` 中 openKylin 官方源码

## 1. 结论

### 1.1 官方材料能够直接确认的结论

1. 交付对象是“应用于麒麟操作系统 OS Agent 的多源融合偏好与知识记忆优化解决方案”，重点是记忆模块，不是从零实现一套标准 Agent。
2. 两份材料都没有发布必须遵循的“标准 Agent 架构”，也没有“参赛队必须自行实现完整 OS Agent”的条款。
3. 两份材料没有点名说明“允许使用 `kylin-agent`/`agent-runtime`”，也没有禁止基于现有 Agent 或开源依赖开发。
4. PPT 将“直接用开源软件作为作品提交”列为踩雷点；文字方案要求提交源代码、保证可读可复用且无知识产权纠纷。这意味着不能把现成开源 Agent 原样包装成参赛作品。

### 1.2 工程结论（明确标注为推断，而非赛方原文）

**不从零实现另一套完整 OS Agent；以 openKylin `kylin-agent` 和 `agent-runtime`
为基座，把 PIXIU 作为原创记忆提供者接入。** 这是与题目范围相符、且官方材料
没有禁止的工程解释，但不是赛方对该具体依赖的书面授权。为了规避“直接用开源
软件作为作品提交”，最终交付必须清楚划分上游依赖与团队原创代码，展示实质性
集成、双 SDK 合规、多设备记忆创新和量化效果。若需要零争议的“正式允许”结论，
仍应向赛题答疑联系人取得书面确认。

当前仓库不能把 `frontend/` 的聊天外观等同于完整 Agent。代码事实是：普通输入直接调用 `/memory/query`，后端返回记忆检索结果；仓库内没有模型驱动的 Agent 循环、会话消息持久化、工具自主选择、Shell/联网搜索执行与审批编排。

## 2. 权威材料、角色与源码依据

官方平台文字方案与 2026.05 技术/赛事团队 PPT 共同构成权威要求：前者给出完整
赛题、评分和精确提交规则，后者进一步细化技术硬门槛、Agent 特征、交付格式与
常见失分点。二者都是只读原件，所有合并解释只写在本派生文档中。

| 资料 | 仓库位置 | 用途 |
|------|----------|------|
| 2026.05 完整赛题要求 PPTX | `docs/完整赛题要求.pptx` | 硬门槛、OS Agent 定义、记忆分层、交付与常见失分点 |
| 赛题文字方案及附录 A | `docs/OriginProblemDescription.md` | 7 项功能、量化阈值、100 分评分表、示例场景 |
| 官方桌面 Agent | `third_party/kylin-agent` | 会话 UI、SSE、模型/工具/记忆设置及 Agent API 参考 |
| 官方 Agent 运行时 | `third_party/kylin-agent-runtime` | Agent 循环、工具、Shell、浏览器、MCP、审批、插件与记忆扩展点 |
| 指定 Embedding SDK | `third_party/kylin-coreai-embedding` | 文本向量化权威接口与示例 |
| 指定向量数据库客户端 | `third_party/libkysdk-vector-engine-client` | 系统向量数据库建库、写入和检索权威接口与示例 |

上游链接：[`kylin-agent`](https://gitee.com/openkylin/kylin-agent)、
[`agent-runtime`](https://gitee.com/openkylin/agent-runtime)、
[`kylin-aiassistant`](https://gitee.com/openkylin/kylin-aiassistant)、
[`kylin-coreai-embedding` 文本向量化示例](https://gitee.com/openkylin/kylin-coreai-embedding/blob/openkylin/nile-sp2/test/TestTextEmbedding.cpp)、
[`libkysdk-vector-engine-client` 示例](https://gitee.com/openkylin/libkysdk-vector-engine-client/tree/openkylin/nile-sp2/demo/client)。

### 2.1 官方 Agent 选型比较

| 候选 | 检查结果 | 本项目决定 |
|------|----------|------------|
| `kylin-aiassistant` | 成熟 Qt 桌面助手，具备历史会话、模型切换、联网搜索和系统控制 UI；核心 `OsAssistant` 来自外部 `libkyai-assistant-dev`，仓库本身不是完整可改的 Agent 内核 | 作为银河麒麟既有助手和 UI/SDK 参考，不作为主要可扩展内核 |
| `kylin-agent` | 新的官方桌面 Agent，提供会话和 run/SSE 客户端、模型/技能/工具/记忆/计划任务设置；运行时由外部仓库提供 | 作为最终桌面宿主首选；已固定为 submodule |
| `agent-runtime` | 含实际 Agent 循环、会话、Shell、浏览器/搜索、MCP、审批、插件与 `MemoryProvider` 接口 | 作为 PIXIU 的直接集成基座；已固定为 submodule |

工程方案不是“重写原有麒麟助手”，而是“复用 openKylin 可执行 Agent + 插入
PIXIU 原创记忆提供者”。这同时避免复制通用能力和长期维护大规模上游分叉；但
答辩必须主动披露上游边界、许可证、团队修改和原创贡献，不能暗示 Agent 基座由
团队从零开发。

这些 submodule 是上游权威参考。除非形成明确的补丁维护策略，不直接修改 submodule 工作树。当前固定版本中，`kylin-agent` 为 AGPL-3.0，`agent-runtime` 为 MIT；打包或派生分发前必须完成许可证、版权声明、依赖清单和供应链审查。任何上游脚本也必须在执行前审阅，不能盲跑。

### 2.2 允许性风险分级

| 做法 | 与官方材料的关系 | 建议 |
|------|------------------|------|
| 将未修改的 openKylin Agent 直接打包，主体功能几乎全来自上游 | 命中 PPT“直接用开源软件作为作品提交”的踩雷点 | 禁止采用 |
| 把系统已安装的 openKylin Agent 当宿主，通过独立适配器调用 PIXIU | 官方材料未禁止，作品主体仍是原创记忆系统 | **首选**；保留架构、接口、代码量与贡献证明 |
| fork Agent 并大范围改写后整体提交 | 未被明文禁止，但原创边界、AGPL、维护和答辩风险更高 | 仅在扩展接口无法满足时采用最小补丁 |
| 团队从零开发完整 Agent | 未被要求，且会稀释记忆创新与时间 | 不建议 |

## 2.3 建议向赛方取得的书面确认

为把“材料未禁止”升级为“赛方明确允许”，建议在官方答疑群或邮件提交下面这个
封闭问题，并保存带时间和身份的回复：

> 参赛作品的原创主体为 OS Agent 记忆模块及多设备分布式同步能力。我们计划将其
> 作为插件/适配器接入 openKylin 官方 `kylin-agent`/`agent-runtime`，明确披露
> 上游许可证和代码边界，不把未修改的开源 Agent 作为作品成果。请确认这种“官方
> Agent 基座 + 参赛团队原创记忆模块”的交付方式是否符合“不得直接用开源软件作为
> 作品提交”的要求，以及提交时是否需排除上游源码、仅提供依赖清单和适配代码。

## 3. PPT 明确的验收口径

### 3.1 三个硬门槛

| 编号 | 要求 | 判定 |
|------|------|------|
| H-01 | 软件必须部署在银河麒麟桌面操作系统 V11 | 不满足按 PPT 计 0 分 |
| H-02 | 数据库必须使用系统向量数据库 SDK（`kylin-ai-vector-engine`/官方客户端） | SQLite、hnswlib 或自研扫描不能冒充最终合规路径 |
| H-03 | 文本向量表示必须使用系统 Embedding 接口（`kylin-coreai-embedding`） | portable/hash/stub 仅可作开发降级或对照 |

### 3.2 OS Agent 和记忆分层

PPT 将 OS Agent 定义为系统级智能助手：能够理解复杂指令、规划并调用系统或外部工具、执行任务、适应用户习惯，而不只是聊天。其记忆输入至少包括多轮对话、工具结果、用户行为和手动配置。

- 短期记忆：当前对话/任务上下文，受上下文窗口限制，通常随会话结束。
- 中期记忆：项目或会话周期的状态、摘要和中间结果，持续小时或数日，承担 scratchpad/状态机作用。
- 长期记忆：本赛题重点，跨对话、跨时间持久化，通过检索注入短期上下文。

因此，“记忆 API 能写能查”不足以证明已接入 OS Agent；必须展示 Agent 在真实多轮任务中自主决定何时读写记忆、何时调用哪些工具，并将工具结果继续沉淀。

### 3.3 功能、指标、评分与交付

完整功能项、四项量化阈值、初评/复评分值和交付格式已经逐项固化在 [验收测试规范](AcceptanceTestSpecification.md)。其中初评为 30+30+25+10+5=100 分。PPT 饼图的 32/32/26/11 是前四项 95 分被图表自动归一化后的显示，不应改写为新的原始分值。

## 4. 本仓库事实与关键缺口

| 领域 | 已有事实 | 结论/缺口 |
|------|----------|-----------|
| Agent 主体 | `frontend/` 有悬浮球、聊天窗和记忆面板 | 是记忆控制台，不是完整 Agent |
| 会话 | API 没有 session/message/run/tool-call 契约 | 缺多轮会话与任务运行状态 |
| 自主规划/工具 | 没有模型工具循环、审批、Shell、联网搜索编排 | 项目决定接入 openKylin Agent 基座，非赛方指定 |
| Embedding | 有 SDK submodule、pybind 源码和适配层 | 需补最终版本的 V11 真实调用证据 |
| 向量数据库 | 有客户端 submodule 和封装，但生产检索走 SQLite INT8 扫描 | H-02 当前未通过，是最高优先级缺口 |
| 记忆引擎 | 多源接入、偏好、知识、冲突、安全、遗忘已有实现 | 需通过 Agent 生命周期触发，而非仅独立 API 演示 |
| 记忆流转 | 有短/中/长期流转设计 | 需映射真实 session、压缩前和会话结束事件 |
| 分布式同步 | CRDT、Gossip、反熵、配对、签名、mTLS、墓碑 | 是主要创新项，需做多机收敛实证 |
| 指标 | portable 基线 100%/100%/96%/115ms | 仅开发回归；不能替代 H-01～H-03 和最终数据集验收 |

## 5. 推荐接入设计

`agent-runtime` 已提供单一外部 `MemoryProvider` 生命周期接口，是首选接缝：

| Agent 生命周期 | PIXIU 行为 |
|----------------|------------|
| `initialize` | 探测 PIXIU 服务、V11 与双 SDK 能力；严格画像缺失即失败 |
| `prefetch(query, session_id)` | 调用 `/memory/query`，把来源可追溯的长期记忆注入本轮上下文 |
| `sync_turn(user, assistant, session_id)` | 将完整对话轮次送入多源接入，异步提取偏好与知识 |
| `get_tool_schemas` / `handle_tool_call` | 暴露显式查询、记住、遗忘、同步状态等记忆工具 |
| `on_memory_write` | 接收 Agent 原生记忆写入并标准化为 PIXIU evidence/knowledge |
| `on_pre_compress` | 压缩前生成中期摘要，保留任务状态与未完成事项 |
| `on_session_end` / `on_session_switch` | 执行短→中→长期流转、作用域映射与清理 |
| `on_delegation` | 在子 Agent/任务委派时传递最小必要记忆上下文 |

推荐边界：

```text
kylin-agent UI
      │ SSE / run API
agent-runtime ── MemoryProvider adapter ── PIXIU REST API
      │                                      │
 shell/browser/MCP/tools            engine + foundation + P2P sync
                                             │
                               Kylin Embedding + Vector Engine
```

适配器只依赖稳定的 HTTP/API 契约，不直接导入 `backend/engine` 或 `backend/foundation` 私有实现。现有 `frontend/` 保留为记忆诊断、设备管理和独立演示控制台；是否最终并入官方桌面 UI，应在许可证、打包和体验评估后决定。

## 6. 实施优先级

1. **P0 合规闭环**：在 V11 将指定 Embedding 和 Vector Engine 同时接入生产路径；严格模式不允许静默降级。
2. **P0 Agent 闭环**：实现 MemoryProvider 适配器，跑通多轮会话→自主召回→工具执行→工具结果写入→后续轮次复用。
3. **P0 证据闭环**：分别产出 Debian portable 回归与 V11 `KYSDK=ON` 最终验收报告。
4. **P1 分布式亮点**：至少三台设备验证并发写、离线、重连、冲突、遗忘墓碑与最终收敛。
5. **P1 评测与答辩**：用合法、标准化数据集覆盖偏好、召回、延迟、冲突和 Agent 端到端自主性。

## 7. 必须补齐的端到端证据

- V11 系统版本、安装包、服务启动和完整操作录像。
- 双 SDK 实际动态链接/进程调用、建库/写入/查询日志、严格失败测试。
- 同一 session 至少三轮对话，历史消息与工具调用可恢复。
- Agent 自主选择记忆读取/写入、Shell 与联网搜索工具；高风险工具有审批记录。
- 工具结果被写入长期记忆，并在后续新 session 中被正确召回。
- 短期、中期、长期记忆的提升、归档、清理和注入记录。
- 多设备同时修改、断网与重连后的 CRDT 收敛和精准遗忘证据。
- 四项性能指标在最终 V11 双 SDK 路径上的原始数据、脚本、环境与报告。

## 8. 两份官方材料的共同适用方式

文字方案的 2026-09-15 前提交、9 月底初审、10 月指导完善和 11 月终审，是平台
发布的精确节点；PPT 的“10 月上旬提交、10 月评审、11～12 月总决赛”作为赛事
阶段概览留档。项目排期采用更精确、更早的 9 月 15 日，不把 PPT 概览解释为延期。
PPT 新增的 V11、双 SDK、视频格式/时长和踩雷提示则完整叠加执行。
