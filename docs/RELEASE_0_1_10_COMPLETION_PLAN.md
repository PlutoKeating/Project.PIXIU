# 0.1.12 发布与验收记录

2026-09-10 发布：[下载正式版](https://github.com/PlutoKeating/Project.PIXIU/releases/tag/v0.1.12)。

| 项目 | 内容 |
|---|---|
| 源码 | `2ed2c38d7ed93416c61dbaf4fa27482876d321c3` |
| 安装包 | `pixiu_0.1.12-1_amd64.deb`，208108672 字节 |
| SHA-256 | `8d2f4082460e2933a062ac771b207d795749028536321c14f485c6cc36a8dda7` |
| 环境 | 银河麒麟 V11 amd64、Python 3.12、系统双 SDK、数据库版本 15 |
| 发布检查 | 通用 CI、V11 原生构建安装、SDK 与签名全部通过 |

## 已通过的验证

完整结果见[效果与测试报告](delivery/TEST_REPORT.md)。

- 正式包及资产清单摘要、签名一致。
- 新装、启动、正常升级和升级故障自动恢复通过；升级前后 47 条记忆摘要一致。
- 三台独立 V11 虚拟机配对、共享、断连及并发更正通过，恢复后完整记录和同步状态一致。
- 真实模型后台新建与更正审批、回答来源、三块文本读取通过。
- Excel 文档读取、全局快捷键、双端遗忘及相关自动化回归通过。

## 记录位置

正式包原始记录位于 `build/release/evidence/candidate-0.1.12/`：

| 文件 | 内容 |
|---|---|
| `kylin-native-evidence.json` | 原生 SDK 与产品记忆检查 |
| `fresh-install-result.json` | 安装与首次启动 |
| `upgrade-result.json` | 正常升级与数据保持 |
| `rollback-result.json` | 自动恢复与数据保持 |
| `three-device-shared-read.json` | 三端共享读取 |
| `three-device-concurrency.json` | 断连与并发更正 |

新装环境清理了旧产品数据及宿主历史会话，系统依赖保留；三台虚拟机运行于同一宿主。较早候选的功能记录位于 `candidate-0.1.10/`，对应版本见测试报告。

## 内部后续记录

按用户要求收束本轮开发与验证。后续验收清单：正式版三端遗忘重连、真实模型合并记忆、超大文档容量、V11 量化指标与三组对比、完整图形安装升级操作。多模态按用户要求暂缓，GitHub #2 保持打开。

宣传核对入口为 `submission/video-production/storyboard/shots.json`；源码结构以[目录计划](SOURCE_MIGRATION_AND_PRODUCT_PLAN.md)为准。
