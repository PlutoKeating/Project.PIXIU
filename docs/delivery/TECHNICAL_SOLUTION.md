# D-02 PIXIU 技术方案工作稿

- 产品版本：0.1.7 功能基线（非最终候选）
- 更新日期：2026-09-03
- 状态：strict 单包、Agent 供应链、Module E 与双 SDK 产品链已纳入；模型端到端、三设备和最终性能待补

## 问题与目标

PIXIU 面向“OS Agent 记忆能力优化与应用”，解决记忆散落在单设备、单会话和单
工具中的问题。原创重点是端侧分布式全连接记忆网络，以及统一接入、偏好/知识、
冲突、安全遗忘、流转与评测能力。

## 已批准总体方案

完整 Agent 不从零重造：openKylin `kylin-agent`/`agent-runtime` 提供会话、规划、
工具、Shell/联网搜索和审批；PIXIU Module E 以 MemoryProvider 通过公共 API 接入。
记忆后端由 engine 与 foundation 组成，Module A 是独立记忆控制台。详细边界见
`../decisions/0001-use-openkylin-agent-host.md` 和 `../ARCHITECTURE.md`。

宿主表现层不直接修改官方 submodule：ADR-0004 批准的第二顺序补丁只作用于固定上游
的隔离构建副本，以双主题语义令牌替换页面硬编码颜色，重构 PIXIU 产品层级、会话、
云端模型、消息与输入区域，并用 4.5:1 对比度门和 V11 视觉矩阵约束发布。

## 核心技术

- 多源 evidence：对话、工具结果、用户行为、手动配置和 OCR；保留来源与质量。
- 神经—符号检索：BM25、向量与实体关系图融合，结果可追溯原始 evidence。
- 偏好与知识：版本化偏好、事实/工作流/案例/模板、冲突检测和审计。
- 精准遗忘：自然语言定位、关联清理、共享墓碑传播。
- 分布式同步：可信配对、CRDT、Gossip、反熵、离线写入和最终收敛。
- 平台适配：V11 生产路径使用指定 Embedding/Vector Engine；Debian 保留显式降级。

## 当前缺口与完成标准

H-02/H-03 技术门已由 `829d944` strict 同包原生证据通过；`CONVERSATION`/provenance/完成态
幂等、审计式失败恢复、预算化召回和六类生命周期 context 入口已实现，Module E
已在包内 Runtime 中被发现并选中。V11 可重建宿主、离线 Runtime、Gateway/会话 API
与供应链 `ready=true` 已通过；模型驱动的真实触发和跨会话长期化实证尚未完成。只有
`AcceptanceTestSpecification.md` 全门通过后，才能把本稿状态
改为“最终已审核”。性能数值必须引用最终原始 JSON/CSV，不沿用 portable 基线冒充。
