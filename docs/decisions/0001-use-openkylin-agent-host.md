# ADR-0001：以 openKylin Agent 作为 PIXIU 宿主

- **状态**：已批准（Accepted）
- **批准日期**：2026-09-03
- **决策人**：华南理工大学 PIXIU 团队负责人
- **适用范围**：赛题作品架构、实现、测试、打包、答辩与交付

## 背景

赛题要求作品应用于麒麟 OS Agent，重点考查多源记忆、偏好与知识记忆、指定
Embedding/Vector Engine SDK、端侧性能和可验证交付。两份官方材料没有要求参赛队
从零实现标准 Agent，也没有点名允许或禁止某个 openKylin Agent；PPT 同时警示不得
把开源软件直接作为作品提交。

当前 PIXIU 已有记忆业务引擎、存储/检索/流转、分布式同步和记忆控制台，但没有
模型驱动的多轮 Agent 循环、工具自主选择、Shell/联网搜索及审批编排。从零补齐这些
通用能力会稀释记忆创新并扩大交付风险。

## 决策

1. PIXIU **不从零实现另一套完整 OS Agent**。
2. 首选系统已安装的 openKylin `kylin-agent` 作为桌面宿主，以 `agent-runtime`
   提供会话、规划、工具、Shell/浏览器、审批和运行控制。
3. 在 `integrations/kylin_agent/` 实现团队原创的 Module E 适配层，通过
   `MemoryProvider` 生命周期与 PIXIU 公共 HTTP API 连接；禁止直接导入
   `backend/engine/` 或 `backend/foundation/` 私有实现。
4. `frontend/` 保留为 PIXIU 记忆诊断、设备管理和独立演示控制台，不承担或冒充
   完整 Agent 循环。
5. `third_party/kylin-agent`、`third_party/kylin-agent-runtime` 仅作为固定版本的
   上游权威参考。优先采用外部插件/适配方式；只有扩展点确实不足时，才维护最小、
   可审计的上游补丁。
6. 作品原创主体是 PIXIU 记忆系统、Module E 适配、指定双 SDK 生产接线、分布式
   全连接记忆网络与评测证据。交付材料必须区分上游依赖、团队新增和团队修改。

## 必须满足的完成条件

- 同一完整 Agent 中跑通多会话/多轮、模型自主规划、工具选择、Shell、联网搜索、
  审批、停止与恢复。
- MemoryProvider 跑通召回、对话轮次写入、工具结果沉淀、压缩前处理、会话切换/
  结束流转和显式记忆工具。
- 银河麒麟桌面操作系统 V11 中，生产向量链路真实使用指定 Embedding 与 Vector
  Engine SDK；严格验收画像缺少任一能力时必须失败，不得静默降级。
- 至少三台设备验证并发、离线、重连、冲突、遗忘墓碑及最终收敛。
- 保存上游版本、许可证、依赖清单、原创代码范围、调用日志、测试报告和视频时间戳。

## 非目标与风险边界

- 本决策不是“赛方点名授权该基座”的声明；它是团队在官方材料未禁止情况下批准的
  工程路线。仍应向官方答疑渠道取得书面确认并归档。
- 不把未修改的上游 Agent 打包成团队成果，不宣称通用 Agent 能力由 PIXIU 从零开发。
- Debian portable 路径只用于开发回归，不能替代 V11 与双 SDK 验收。
- 若官方书面答复与本决策冲突，或固定版本的 MemoryProvider 无法满足接入，须重新
  提交 ADR；在新决策批准前不得自行扩大上游 fork。

## 关联文档

- `../OS_AGENT_INTEGRATION_ASSESSMENT.md`
- `../ARCHITECTURE.md`
- `../DEVELOPMENT_PLAN.md`
- `../API.md`
- `../AcceptanceTestSpecification.md`
