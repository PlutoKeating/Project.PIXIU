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

PIXIU 是银河麒麟 V11 的个人记忆助手。它帮助用户整理资料、复用跨会话知识、查看信息来源，并在可信设备之间共享记忆。

当前版本：[0.1.12](https://github.com/PlutoKeating/Project.PIXIU/releases/tag/v0.1.12)，提供 amd64 单一安装包。

## 典型应用背景

> [!IMPORTANT]
> 记忆不该被一台台设备割裂。下面这个再普通不过的周末，正是 PIXIU 想要改变的日常。

**周六上午，书房。** 林先生是一名在家办公的设计师，家里有三台跑着银河麒麟的设备：书房的工作站、客厅的一体机、还有一台随身的麒麟笔记本。过去，每台设备的 OS Agent 都像一个"失忆"的助手——在书房交代过的事，换到客厅就得从头再说一遍。

**上个月的某天**，林太太用微信发来一份家庭支出文字清单。林先生让书房工作站的 OS Agent 把清单记到已授权的家庭共享空间。PIXIU 在后台默默完成了一整套动作：由当前聊天模型理解清单文字 → 后端引擎清洗、标准化并做敏感度评分 → 抽取"国家电网""新奥燃气"等实体并挂载到"水电燃气"类目 → 生成端侧向量写入长期记忆。**林先生什么都没多做，一条结构化、可检索、可追溯的知识就这样沉淀了下来**——而且通过去中心化网络，悄悄同步到了客厅一体机和笔记本上。

**今天下午，客厅。** 林先生靠在沙发上，突然想核对一笔开销，却只记得模糊的片段。他按下全局快捷键，PIXIU 的统一会话窗口随即出现，他随口一问：

> 「我们好像在水电燃气方面花了一些钱，花了多少钱来着？」

助手找回清单后回答：*"2026 年 4 月，你们在水电燃气方面共支出 434.50 元，其中电费 210 元、水费 68.50 元、燃气费 156 元。"* 点击回答中的来源链接，就能回溯到最初的清单原文。他没有打开任何文件管理器、没有翻聊天记录、更没有逐条加总——**系统替他记住了，也替他算好了**。

**几分钟后**，他想起燃气费记错了，便补了一句"燃气费不是 156，是 186"。PIXIU 的冲突仲裁模块自动识别出与旧记忆的矛盾，以新版本为准，同时完整保留了修改痕迹。临睡前他又说："忘记那张 4 月的支出清单吧。"——系统先展示目标和范围，确认后让知识失效并清理检索向量，再向可信设备传播共享删除状态。

**这一切，发生在三台设备之间，却像在和同一个懂你的助手对话。** 记忆数据无需云端
账号、保留在可信设备中，断网时仍可写入与检索；联网推理由系统麒灵模型或用户选择的
官方服务完成。这就是 PIXIU 想带给每一位麒麟用户的体验——**让设备彼此相通，让记忆为你所用**。

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
