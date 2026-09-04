<div align="center">

# PIXIU · 貔貅

### 面向银河麒麟 OS Agent 的分布式记忆增强系统

*让多台设备上的 Agent 共享、同步并安全使用同一张记忆网络。*

[![Kylin OS](https://img.shields.io/badge/Galaxy%20Kylin%20OS-V11-DA291C?style=flat-square&logo=linux&logoColor=white)](https://www.kylinos.cn/)
[![Status](https://img.shields.io/badge/contest%20status-P0%20整改中-orange?style=flat-square)](docs/AcceptanceTestSpecification.md)
[![Foundation](https://img.shields.io/badge/Foundation-FastAPI%20%2B%20SQLite-009688?style=flat-square)](backend/foundation/docs/ARCHITECTURE.md)
[![Frontend](https://img.shields.io/badge/Memory%20Console-Qt5%20%2F%20UKUI-41CD52?style=flat-square)](frontend/docs/ARCHITECTURE.md)

[赛题与口径](docs/OriginProblemDescription.md) · [验收清单](docs/AcceptanceTestSpecification.md) · [完整交付主实施计划](docs/IMPLEMENTATION_MASTER_PLAN.md) · [最终交付计划](docs/DELIVERY_PLAN.md) · [Agent 宿主决策](docs/decisions/0001-use-openkylin-agent-host.md) · [用户会话后端决策](docs/decisions/0002-run-native-backend-in-user-session.md) · [Agent 供应链决策](docs/decisions/0003-package-openkylin-agent-supply-chain.md) · [宿主 UI 决策](docs/decisions/0004-maintain-kylin-agent-visual-accessibility-patch.md) · [关键问题与接入结论](docs/OS_AGENT_INTEGRATION_ASSESSMENT.md) · [总体架构](docs/ARCHITECTURE.md) · [开发计划](docs/DEVELOPMENT_PLAN.md) · [API](docs/API.md)

</div>

## 项目定位与当前状态

PIXIU 参加麒麟软件“OS Agent 记忆能力优化与应用”赛题。团队的核心创新是一个面向多台设备的、去中心化的全连接记忆网络：可信设备通过 CRDT、Gossip 与反熵对账共享长期记忆，离线可用，重连后收敛，并保留来源、冲突和遗忘审计。

> [!CAUTION]
> **当前仓库尚不能宣称完整赛题验收通过。** strict 单包、完整 Agent 宿主/Runtime、
> Module E、用户服务和双麒麟 SDK 产品链已经落地并在 V11 候选上实测；尚缺的是配置
> 推理提供商后的真实 Agent 自主工具生命周期、三台独立 V11 设备同步、最终性能与完整
> 安装/GUI 升级矩阵。这些缺口继续由交付门禁失败关闭，不能用 mock 或协议模拟代替。

工程链路已新增一套**确定性、无推理**的 OpenAI-compatible 测试节点：真实 Runtime
仍负责会话、SSE、审批和工具调度，真实 Shell、DDGS 联网搜索及 PIXIU 本地/共享记忆
API 仍被实际调用；测试节点只按可观察状态返回固定 tool call。该链路已验证系统提示
每次随请求发送、持久化会话历史逐轮增长、工具结果回送模型，以及记忆写入、检索、
更新和同步状态调用。它只用于工程回归，证据类别固定为 `pixiu-agent-mock-e2e`，不得
替代 DeepSeek 官方云端的自主规划实测或写入正式 D-07。

2026-09-04 的目标 V11 严格候选已越过此前的用户会话和 Agent 供应链阻断。提交
`829d944` 的 amd64 单包安装后，systemd user service、`/version`、双 SDK direct
生命周期和产品写入/检索/遗忘均通过；`/capabilities` 返回 Embedding/Vector
`runtime=kylin`、两者 compliant 且 `contest_ready=true`。该候选 SHA-256 为
`43780c6a8460d8a518811d1968ff20bb6eceeae0c6da6344b5f18b4339e3f180`。包内同时包含
可重建 `kylin-agent`、54 个哈希锁定 Runtime wheels、PIXIU Provider、SBOM、NOTICE
和对应源码/构建证据。最终文档冻结后仍须对新 commit 重建并重新绑定证据。

严格原生画像现带分阶段 fail-closed 门禁：`preinst` 在 dpkg 写入文件前核对麒麟
V11 与架构；双 SDK 由包依赖解析，并由后端严格启动预检验证实际可用性；桌面用户
激活 Provider 时再检查 `kylin-agent` 与唯一、成功返回的 0.9.x runtime。通用 Debian
画像保持非严格降级，两类包的 `install_strict` 会写入组件清单，不能混报。

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

Agent 供应链候选门现采用互相绑定的实物证据，而不是接受“已重建/已离线安装”的
布尔自述：宿主必须同时提供目标架构产物、完整对应源码归档和构建日志及各自摘要；
Runtime 必须提供全量 wheel、锁文件和离线安装日志；SPDX 2.3 必须精确覆盖两个固定
上游及全部 wheel 包；NOTICE 必须记录来源、固定 commit 与精确许可证边界。宿主官方
仓库元数据的 `AGPL-3.0` 已按 SPDX 3.0 规范化为 `AGPL-3.0-only`，但对应源码和 NOTICE
义务仍未免除。当前发布适配会在隔离副本中删除未使用的在线引导脚本、净化上游认证式
URL，并对实际入包范围复扫；宿主 V11 重建、Runtime 网络隔离离线安装、SPDX/NOTICE
交叉校验均已通过 `ready=true`。因此 strict `.deb` 已内置可分发完整 Agent；但没有
模型提供商配置时，真实推理与自主工具生命周期仍按设计阻断。
Runtime 的 CPython 3.12/amd64 全闭包及构建工具锁均已提交为构建输入；构建只接受
`--require-hashes` 下载并反向重建锁比对。strict 打包还要求供应链证据的目标架构与
`.deb` 架构完全相同，禁止把 amd64 实证复用于 arm64。用户态 Agent 激活在变更前会
严格识别可迁移 unit，并在 Provider、配置写入或 Gateway 启动失败时恢复事务快照。
离线 Runtime 闭包现包含 58 个哈希锁定 wheel 及官方支持的免密 `ddgs` 搜索后端；
发布适配会把上游 setuptools 遗漏的 bundled `plugin.yaml` 清单纳入 Runtime wheel，
离线门禁再从全新 venv 验证 DDGS 被实际发现并成为可用 provider；安装/升级会在哈希
锁约束下强制收敛到包内 Runtime，避免同一上游版本残留旧文件。因此安装后无需另配
商业搜索 API Key；用户态激活事务会显式重启包管 Gateway，确保新 provider 当场生效。
目标 V11 的真实 Gateway 已完成一次 `web_search` 成功调用；完整 Agent 生命周期仍以
固定三轮、审批、记忆写入和重启后跨会话召回全部成功为准。

KylinAgent 宿主界面现按
[ADR-0004](docs/decisions/0004-maintain-kylin-agent-visual-accessibility-patch.md)
维护独立下游补丁：浅色/深色主题使用统一语义令牌，消除页面局部硬编码颜色，重做
PIXIU 品牌层级、会话侧栏、云端模型选择、消息画布、输入区与无路径泄露的空状态。
每条消息使用独立行容器承担 Qt 所有权，刷新时同步销毁容器，防止侧栏折叠或历史刷新后出现
重复气泡、错位残影和空状态遮挡；该结构由宿主适配回归门禁固定。关键普通文本和交互配色由
自动化复算 4.5:1 对比度；长会话标题采用右侧省略且关闭横向滚动。最终状态仍须绑定新候选包完成
V11 双主题、缩放、键盘和运行状态截图复核，不能沿用旧界面截图。
推理入口同时执行“仅直连云端”边界：DeepSeek 官方 `deepseek-chat` 为首选，另保留
Anthropic/OpenAI 官方直连；OpenRouter 和 Ollama/LM Studio/vLLM/llama.cpp 不进入
产品下拉框。密钥只能通过 Runtime 隐藏输入保存，禁止写入仓库或命令行。

同步控制台现只呈现真实动作：设备发现/确认式配对、自动 Gossip/反熵状态、暂停、
状态刷新和整网退出。旧“立即同步”按钮实际只刷新状态、没有触发后端同步动作，现已
删除；旧后端返回 `not_implemented` 时明确显示版本不兼容，不再误写成当前功能待实现。

赛事交付区现已具备两条 fail-closed 生成链：D-03 源码归档会带入四个 submodule
实体、供应链证据和逐文件摘要，并把每个归档文件的类型与摘要反向核对到洁净 release
checkout，不能通过同时替换文件和 manifest 伪造同版源码；D-02/D-03/D-04/D-06～D-10 由统一排版器生成真实
DOCX/PDF。草稿强制显示“不得提交”，最终模式绑定 release commit 和发布门；总打包器
还会解析办公文件、PDF、视频、ZIP 与 Debian 包结构，并核验安装包摘要和签名。
D-07 原始证据 ZIP 不是任意日志合集：机器策略要求双 SDK、完整 Agent 生命周期、
最终性能、三设备、安装升级、数据集和供应链七类记录同 commit、同候选包通过，并对
附件做摘要与敏感信息扫描。

D-07 归档现不再只信任记录的外层 `status=pass`：生成和解包复验都会重新调用原生
SDK、Agent 生命周期、最终性能、冻结数据集、安装/升级矩阵、三设备套件和 Agent
供应链的深度验证契约。Agent 必须引用归档内
同一份原生证据；性能记录必须引用三份对应主记录及两个不同的逐样本/消融附件；冻结
数据集 JSON 也会重新规范化并复算 50/15/25 用例构成。缺附件、替换附件或手填绿色
字段均不能过门。三设备会从最终套件递归复算两份拓扑、四类场景、六份节点清单及
各场景检查点；供应链会重读宿主构建/源码/日志、Runtime wheels/锁文件/离线日志、
SBOM 和 NOTICE，并按摘要及固定上游策略交叉核对。

消融证据也纳入相同的递归复验：归档器从性能记录定位矩阵，再打开固定任务集、三份
逐任务变体报告、六份 Runtime 配置快照及分布式节点 manifest，重算任务覆盖、成功率、
平均轮数，并重新证明无记忆隔离、单机关闭同步以及分布式跨两个不同节点；仅伪造矩阵
摘要或遗漏失败样本无法进入最终 D-07。

安装/升级矩阵已有真机状态采集与离线汇总器：在每个动作前后读取 V11、dpkg、systemd、
`/version`、`/health`、`/capabilities`、配置摘要、数据库完整性/逻辑计数和设备身份摘要，
并把独立操作日志绑定到首装、重装、升级、故障回滚、GUI 升级和卸载六条记录。最终
记录要求配置、业务数据及设备身份在重装/升级/回滚中保持，普通卸载保留用户数据；
D-07 还会打开所有快照和操作记录重新核对。工具契约 6/6 通过，最终 V11 候选尚未实测，
因此 R-01～R-05 仍不能标记通过。

真实 Agent 生命周期门禁现已实现为两阶段采集：它会读取持久化消息并通过固定 Runtime 的 `/v1/runs`
`conversation_history` 继续多轮上下文，而不假定 session ID 会让 Gateway 自动回填历史；
和 SSE 事件验证同会话三轮、模型选择 Shell/联网搜索/PIXIU 记忆工具、现场一次性审批
与工具结果沉淀；重启宿主和 Runtime 后，再核对原消息摘要并由全新会话主动召回随机
标记。随机标记只通过临时受控文件暴露给 Shell 结果，最终报告不保留提示词、输出、
URL、进程号或会话 ID。采集器已具备 9 项自动化契约测试，但尚未在最终 V11 候选上采集，
因此当前完整 Agent 状态仍为未通过。确定性 Mock 已将上述请求形状和真实工具管线跑通，
但因其不执行模型推理，不能用于证明 A-03/A-04 或真实云端生命周期通过。

最终性能汇总门也已落地：它拒绝 portable/non-strict 原生证据，要求逐样本 acceptance
报告至少覆盖 50 个检索、15 个偏好、25 个冲突用例和 1000 个延迟样本，并逐项重验
85%/85%/500ms/88% 基础线；同时强制无记忆、单机记忆、分布式记忆三组同任务集、
各不少于 30 例的对比/消融。汇总记录与原生 SDK、完整 Agent、冻结数据集及候选包
摘要必须完全一致。三变体现在另有真实 Agent 采集器：固定 30 个合成跨会话任务，核对
Runtime 明确启停项、strict provider、同步状态与进程身份；分布式教学/召回必须绑定
同一三设备拓扑中的不同节点。它只输出逐任务布尔结果、轮数、工具名和摘要，并从原始
结果复算指标，不保存模型正文或会话标识。当前采集器契约测试通过，但最终 V11 三组
运行、最终数据集和原始报告未生成，不能据此填写最终性能成绩。

最终逐样本报告的产生端也已失败关闭：`capture_final_eval.py` 必须由已安装 PIXIU venv
和 `/usr/lib/pixiu` 组件运行，绑定同版 strict native 证据，并以隔离状态真实调用
Kylin Embedding 与 Vector Engine；报告写入不可伪装为 portable 的执行来源。性能汇总
及 D-07 解包复验都会核对该来源、candidate/commit 和 native 文件摘要。当前只有工具
契约与 portable 兼容回归通过，尚未在最终 V11 候选上生成报告。

最终 acceptance 数据集也已有独立冻结器：从当前 release commit 的确定性参考生成器
导出 50 份附录 A 家庭支出 fixture 与 90 个测试用例，规范化摘要保持与评测报告算法
一致；manifest 如实标记为“团队编写的合成语料、派生自赛题附录 A、非第三方数据集”，
并固定 0/0/90 的 train/validation/test 划分、官方原文摘要、候选包摘要和敏感扫描。
当前 4 项工具测试通过；只有最终 clean commit 和 strict 原生证据才能实际导出。

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

远端首次物化的共享知识不会绕过语义冲突服务；同步来源按
`updated_at`、`created_at`、`id` 的稳定全序裁决，已用两节点相反收包顺序证明最终
ACTIVE/SUPERSEDED、version、时间与正文一致。该自动化结果仍属于本地集成证据，三机 V11
场景必须按下述取证门重跑。
CRDT 胜者现统一复用 `KnowledgeService` 重建实体图与 embedding/VectorStore 索引；
远端更新会替换旧向量，远端墓碑会同步移除生产向量，避免“状态已同步但语义检索仍旧”的假收敛。
若知识操作先于其 evidence 跨批次到达，接收端会持久保存待补引用，并在 evidence 到达
后自动恢复关联；Agent 上下文不会因网络乱序永久丢失可追溯来源。

三节点协议回归现覆盖离线节点重连补墓碑、旧操作重复/乱序重放防复活，以及全部
活跃 peer ACK 后才安全回收。它使用三份独立数据库验证协议语义；最终“全连接记忆
网络”验收仍须在三台 V11 设备上以同一候选版本复验，不能用该模拟结果替代。
协议回归可通过 `python -m backend.foundation.eval.sync_evidence` 生成绑定 commit/版本
的 JSON；报告固定标记 `final_device_evidence=false`，只进入开发证据层。
真实三机拓扑另由 `build/release/scripts/three-device-evidence.py` 在各节点本地采集：
它绑定 strict V11 原生证据与同一候选包，去敏校验三个不同身份构成完全图、全在线且
队列归零。拓扑报告仍固定为非最终证据，五项跨设备业务场景完成前不得宣称通过。
同一工具现还可分别采集并校验并发更新、单节点离线重连的 9 个去敏检查点：前者验证
两条不同版本分支的确定性收敛，后者验证其余两端离线期间可写可同步且恢复节点追平；
私域不传播另以 6 个检查点证明仅写入端可见且同步确认计数不增长。实际三机执行前
仍不计通过。墓碑防复活取证再绑定去载荷 CRDT 状态，以 12 个检查点证明离线旧副本
回归后仍保持删除，并在追加一次反熵周期后状态不变。最终总门还要求四类报告位于
两份不同的全连接拓扑取证之间；只有总门可产生 `final_device_evidence=true`。

多设备同步是团队的差异化创新，但不是替代赛题硬门槛的理由；优先级始终是 V11、指定双 SDK、完整 OS Agent 接入和可复现量化评测。

当前 Agent 记忆接入进度：`POST /memory/write` 已支持独立 `CONVERSATION` 来源，
并将 session/run/turn/tool-call/审批/时间 provenance 与原始正文分离持久化；完成态
请求具备跨重启幂等 receipt；`POST /agent/context` 已提供 scope/敏感度硬过滤、字符
预算、freshness/冲突状态和 evidence 引用。写入入口现已先执行敏感检测：`user:*`
内容可本地标记隔离，敏感内容不得写入 `shared:*` 或同步；检测异常时 fail closed。
`POST /memory/update` 已提供同一知识 ID 的原子版本 compare-and-swap、更新 evidence、
图/向量重建索引和 shared 同步操作，为多设备离线并发修改进入 CRDT 仲裁提供正式入口。
`POST /memory/write` 的 shared 冲突写入会在仲裁完成后重新读取最终持久化条目，再把
MERGE/NEW_WINS 的最终正文与版本写入同步日志，避免其他设备收到仲裁前的陈旧输入。
Module E 已实现独立 `pixiu`
MemoryProvider：严格 capability 预检、后台召回/写入、六类生命周期映射、五个显式
记忆工具、背压诊断及两阶段遗忘均有契约测试；初始化还会校验 `/version`、`/health`、
同包组件版本和已验证的 Agent runtime 0.9.x 范围。`.deb` 已携带 Provider，并在用户
启动 PIXIU 时幂等安装/升级到当前 Agent profile。失败 receipt 已支持提交完整原请求、
显式确认重复副作用风险并记录原因后授权一次重试。尚未完成的是真实宿主多轮取证
和长期化策略，因此这仍不是完整 Agent 闭环。

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
| H-01 | 软件部署在银河麒麟桌面操作系统 V11；不满足计 0 分 | **产品安装/启动已通过，赛事总门仍待闭环**：strict 单包已在 V11 安装、升级并运行；完整 Agent/三设备/视频仍待最终同版取证 | V11 安装、启动、全链路视频与机器信息 |
| H-02 | 使用系统向量数据库 SDK | **技术门已通过、最终归档待重跑**：`829d944` 同包 direct SDK 与产品写查遗忘链均通过，Vector `runtime=kylin`/compliant | 最终冻结 commit 的同版原始 JSON 与 D-07 归档 |
| H-03 | 使用系统 Embedding 接口 | **技术门已通过、最终归档待重跑**：`829d944` 同包实际调用 runtime 1.3.0/gte-base 768 维向量，Embedding `runtime=kylin`/compliant | 最终冻结 commit 的同版原始 JSON 与 D-07 归档 |

现有 portable 基线（偏好 100%、召回 100%、冲突 96%、P95 115ms）只证明通用软件路径可回归，**不代表 H-01～H-03 或最终比赛性能验收通过**。详见 [验收证据说明](docs/acceptance/README.md)。

## 评分与交付

初评总分 100：技术创新性 30、方案可行性 30、性能指标 25、实用性 10、文档规范性 5。性能基础线为偏好提取准确率 ≥85%、知识检索召回率 ≥85%、检索响应时间 ≤500ms、知识冲突处理正确率 ≥88%。完整逐项清单、复评分值、PPT 交付格式和证据要求见 [验收测试规范](docs/AcceptanceTestSpecification.md)。

PPT 中的饼图显示 32%/32%/26%/11%，是把前四项 95 分自动归一化后的比例，并非新的原始分值；完整评分表仍按 30/30/25/10/5 计 100 分。

团队追加的发布硬门是：最终提供一个可在银河麒麟 V11 图形安装器打开的一体化
`.deb`，内含 PIXIU 记忆服务、控制台和 Module E；软件内可检查版本并一键完成
下载、签名/摘要校验、授权安装、健康检查和恢复。当前 `.deb` 与 GUI 更新基线已经
存在，Module E 也已纳入安装/升级路径；特权安装器会校验包名/版本/架构，并在安装
后自动核对 dpkg 版本、后端 `/version`、数据库 `/health`/schema 与包内 Provider
版本，全部通过才向 GUI 报告成功。Ed25519 固定公钥验签、发布 Secret、双架构 CI
签名资产及 Kylin V11 有效/篡改签名取证已完成；升级 helper 的旧包重建、SQLite/
配置一致性备份和健康失败自动回滚已通过双架构 CI，并在 Kylin V11 amd64 上完成
跨 revision 故障注入，恢复后版本、配置、核心数据和服务均保持。GUI 成功态现提供
“立即重启”：无特权 helper 等待旧客户端有序退出后再启动新版本；源码测试已通过，
`.deb` 还内置可机读的组件清单，记录产品/API/schema/provider、构建画像、上游宿主
与双 SDK 源码钉住版本；生成器会拒绝偏离 gitlink 或含本地修改的子模块，托管 CI
会从成包中反向提取并核对。根 `VERSION` 已成为发布脚本和前端 CMake/独立打包的
权威版本输入；Module E 源码也只保留模板，打包时生成合法 manifest。发布流程现为
每个架构生成包外 `.assets.json`，记录 `.deb`、摘要与签名的大小/SHA-256/通道/commit，
其中 commit/版本/架构须与包内组件清单和 dpkg 元数据自洽，并记录规范化生成命令；
随后对清单自身再做 Ed25519 签名。原生取证脚本现会把包内 commit/版本/架构/strict
画像、本次 `.deb` SHA-256 与已装 PIXIU、双 SDK 包版本、Agent runtime、`/version`、
`/health`、`/capabilities` 绑定；另以独立临时数据库和隔离集合直接执行 SDK 的
LoadDBFile/create/load/upsert/search/delete/drop/disconnect，再验证产品 API 写入/
召回/遗忘。首次目标 V11 严格候选证据仍待
生成，未生成前不得将 H-02/H-03 标为通过。
2026-09-04 的首次严格安装运行检查进一步确认：麒麟 AI runtime 的 Unix socket 按
调用进程 UID 隔离；后端现已改为桌面用户 systemd user service，从而复用该用户会话中的
runtime；strict 后端因此按设计失败关闭。ADR-0002 获批后，安装包已切换为 root
所有的 systemd user unit，启动器在桌面用户上下文创建 XDG 私有配置/数据/状态目录
并启动服务；启动完成还必须同时通过 user manager MainPID/UID 与后端组件/版本握手，
端口上的无关或错误版本进程不能冒充就绪。旧系统数据库与 Vector 数据采用授权的一次性
迁移，复制前后核对 SQLite 完整性、schema、全表计数与同步身份摘要，源数据在成功后仍
保留。GUI 升级现把当前用户的实际 XDG 目录传入特权边界，helper 以 `PKEXEC_UID`
锁定授权用户、验证目录位于其 home 且属主一致，再停启该用户服务并备份/恢复其
数据库与配置；完成最终候选实测后须以同一候选包重跑
直接 SDK 与产品 API 生命周期。完整 AI 子系统属于系统级前置
能力，不作为 PIXIU 安装包的整套强依赖；最终仅声明经实测确认的最小运行依赖。
同次检查还发现 Vector 客户端误用了官方标注“for test”的 host/port 构造；生产路径
已改回 demo 使用的 `ConnectParam(appId)` 本地传输并补齐 LoadDBFile/Disconnect。
提交 `4011d0d` 的 V11 strict revision 7 已用固定测试向量完成 direct SDK 全生命周期；
这不包含 Embedding 或产品 API，故只计底层适配证据，不计 H-02 最终通过。
Embedding 的 err=3/err=10 已定位为系统组件组合问题：官方 embedding engine 从
`3fbfeb6` 起生成 `model_catalog`，abstract-models/model_bank 从 `b999d89`
（首个包含标签 `build/1.2.0.0-0k0.16`）起把 YAML `others_info` 输出为
`othersInfo`。以这两项官方修复做兼容性验证后，官方 demo 与 PIXIU 原生绑定均成功
使用 runtime 1.3.0、`ensemble-embd_gte-base_uint8-text` 并返回 768 维非零向量。
这证明根因和修复方向，但手工对齐的系统组件不是最终交付方案，H-03 仍须由最终包
及声明的最小依赖重验。随后同用户产品 API 探针又发现生产 DI 未先 `LoadDBFile`；
当前源码已补数据库路径、严格启动装载、进程级复用与关闭；提交 `6f6002e` 的 strict
revision 8 已在 V11 同用户会话通过写入、向量检索、遗忘和删除后隐藏。正式取证器
随后正确拒绝继续：目标系统没有 `kylin-agent`/`agent-runtime` 可执行文件。因此该
结果仍是 SDK/产品记忆链强实证，不是完整 Agent 或最终交付通过。
提交 `c643b1b699ba34650fdf913dd58f0cccd8168191` 又从洁净固定源码完成 strict amd64
重建、38/38 前端测试与安装；portable 配置可健康运行，strict 系统服务则再次因用户级
AI runtime 边界失败关闭，恢复后配置和数据库摘要保持。该复验排除了构建漂移，但未
实现 user service 之前的历史证据，也没有完整 Agent，故不改变验收状态。
随后 Agent 供应链闭环解决了无模型探针发现的问题：固定上游源码经最小适配后在 V11
网络隔离环境成功重建，Runtime 全量 wheelhouse 通过网络隔离安装，认证式 URL 不进入
发行范围，SPDX/NOTICE/源码/构建日志和产物摘要交叉核对为 `ready=true`。strict 单包
已实际安装宿主、Runtime 和 Provider。剩余 P0 是配置推理提供商后的模型自主行为，
不能把 Gateway 健康或无模型探针解释为该生命周期已通过。
最终 Agent/三设备/性能与全新机图形升级取证尚未闭环。Kylin V11 amd64 目标环境已完成
`KYSDK=OFF` 的跨 revision 安装、离线依赖与健康检查回归，但该结果明确不计双 SDK，
因此状态仍是“部分完成”。完整门禁和 D-01～D-10 台账见
[最终交付与版本管理计划](docs/DELIVERY_PLAN.md)。

从当前差距到最终候选版本的关键路径、阶段门、逐工作包完成定义和预期提交序列见
[完整交付主实施计划](docs/IMPLEMENTATION_MASTER_PLAN.md)。该计划是执行台账；两份
官方赛事原件仍是不可修改的权威要求来源。
宿主供应链的调查事实、建议边界和批准门见
[ADR-0003](docs/decisions/0003-package-openkylin-agent-supply-chain.md)。

## 仓库结构

```text
Project.PIXIU/
├── frontend/                         # PIXIU 记忆控制台（Qt5/UKUI）
├── integrations/kylin_agent/         # Module E：原创 Agent/MemoryProvider 适配与契约测试
├── backend/engine/                   # 记忆业务引擎
├── backend/foundation/               # API、存储、检索、流转、同步、评测
├── backend/tests/                    # 自动化测试
├── build/release/                    # Debian/银河麒麟构建与发布画像
├── docs/                             # 架构、API、赛题、验收与报告
├── submission/                       # 官方清单驱动的最终赛事交付区与 fail-closed 打包器
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
仓库已提供独立 `kylin-v11-native-x86_64` 严格画像和手动原生 CI 工作流；双 SDK
技术门已有同包真实证据，最终冻结 commit 仍须重新生成并进入 D-07 归档。
