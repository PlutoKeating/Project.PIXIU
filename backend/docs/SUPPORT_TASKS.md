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

材料与截图使用 Git LFS；首次克隆后先按 [材料下载说明](../../build/release/README.md#材料下载) 安装 Git LFS 并拉取实物。PPTX 下载指针不是演示文稿，不能用 WPS 打开；恢复后核对对象摘要与 ZIP 完整性。

交付源稿位于 `docs/delivery/`，由 `build/release/scripts/export-documentation.py` 生成材料。文档制作依赖见 `build/release/requirements-docs.txt`；生成后检查文件格式、内容、图片及匿名信息。

文档导出会把 Word 表格限制在 A4 正文宽度内。交付物统一修订与新版界面采集见 `docs/delivery/MATERIAL_ALIGNMENT.md`；图文与视频采用同一组场景事实，逐页检查导出实物。

项目报告由 `build/release/scripts/build-presentation.py` 调用 `submission/presentation-production/scripts/build_deck.py` 生成31页可编辑路演稿；当前实拍、故事板与事实来源均记录输入摘要。`export-documentation.py --check` 核对源与交付文件。制作依赖见 `build/release/requirements-docs.txt`；本次用 WPS 导出 PDF、Poppler 渲染全部页面并人工复核。过程文件与独立虚拟环境只在该制作子目录内；重建候选须重新渲染复核后再替换正式材料。
