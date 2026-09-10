# 测试与工具维护

## 工作范围

| 目录 | 内容 |
|---|---|
| backend/scripts/ | 后端运行和评测工具 |
| backend/engine/tests/、backend/foundation/tests/ | 记忆与基础服务测试 |
| backend/agent/tests/ | 模型工具与记忆适配测试 |
| backend/platform/tests/ | 启动、升级和迁移测试 |
| frontend/tests/ | 桌面与消息测试 |
| tests/acceptance/ | 跨模块场景、夹具和取证工具 |
| build/release/tests/ | 构建、依赖、签名和交付检查 |

## 当前结果

0.1.12 已完成原生 SDK、新装、签名升级、自动恢复、三端共享和并发恢复验证。详细结果见[测试报告](../../docs/delivery/TEST_REPORT.md)，后续验收见[发布记录](../../docs/RELEASE_0_1_10_COMPLETION_PLAN.md)。

## 记录要求

测试记录包含版本、环境、输入、操作和结果。截图使用真实桌面，数据使用公开合成资料。原始运行记录保存于被忽略的构建证据目录，报告保留可复核的编号和摘要。

## 材料生成

交付源稿位于 `docs/delivery/`，由 `build/release/scripts/export-documentation.py` 生成材料。文档制作依赖见 `build/release/requirements-docs.txt`；生成后检查文件格式、内容、图片及匿名信息。
