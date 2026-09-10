# PIXIU · 貔貅

PIXIU 是银河麒麟 V11 的个人记忆助手。它帮助用户整理资料、复用跨会话知识、查看信息来源，并在可信设备之间共享记忆。

当前版本：[0.1.12](https://github.com/PlutoKeating/Project.PIXIU/releases/tag/v0.1.12)，提供 amd64 单一安装包。

## 日常使用

- 在会话中说明目标，添加文本、PDF 或 Office 资料。
- 助手整理内容、保存记忆并主动报告进度。
- 在新会话中查询过去的信息，点击回答来源阅读原文。
- 审批更正计划，管理偏好、目录权限与可信设备。
- 设备联网后自动同步共享资料，软件更新保留已有数据。



![0.1.12 实拍：查询资料并查看来源](docs/delivery/assets/operations/02-current-release/conversation.png)

0.1.12 实拍：查询资料并查看来源。

## 已验证结果

0.1.12 已通过通用构建、麒麟原生安装、系统双 SDK 调用、发布签名、升级与自动恢复。三台独立 V11 虚拟机完成共享、断连与并发更正，恢复后完整记录一致。

详细版本和测试范围见[测试报告](docs/delivery/TEST_REPORT.md)。

## 源码结构

| 目录 | 职责 |
|---|---|
| `frontend/` | 桌面、工作区、消息呈现和宿主补丁 |
| `backend/engine/` | 知识、偏好、冲突和安全 |
| `backend/foundation/` | API、文档解码、存储、检索和同步 |
| `backend/agent/` | Agent 记忆适配、文档工具和后台整理 |
| `backend/platform/` | 启动、升级与数据迁移 |
| `tests/acceptance/` | 跨模块场景验证 |
| `build/release/` | 构建、打包、发布和材料导出 |
| `third_party/` | 固定版本上游与系统 SDK |
| `docs/` | 使用、设计、开发和测试文档 |

## 文档

[用户手册](docs/delivery/USER_MANUAL.md) · [安装指南](docs/delivery/DEPLOYMENT_GUIDE.md) · [总体架构](docs/ARCHITECTURE.md) · [API](docs/API.md) · [开发计划](docs/DEVELOPMENT_PLAN.md) · [发布记录](docs/RELEASE_0_1_10_COMPLETION_PLAN.md) · [交付要求](docs/DELIVERY_PLAN.md)

桌面与 Agent 运行时复用 openKylin 项目，PIXIU 实现记忆服务、分布式同步与集成适配。来源及许可证见[源码说明](docs/delivery/SOURCE_AND_LICENSES.md)。
