# PIXIU 交付材料维护

`submission/` 只保存按赛方要求命名的正式文件。编写源、截图、检查记录和中间导出物在该目录之外维护。唯一权威要求见 [交付计划第 0 节](../DELIVERY_PLAN.md#0-赛方交付作品要求唯一权威永久冻结)。

提交目录有两层同名目录，名称由学校、作品名称、主申报人姓名以 `+` 连接。外层还包含与内层并列的 `源代码/`。内层保存 `项目报告.pptx`、`技术方案.doc`，视频制作完成后放入同层并命名为 `演示视频.zip`。视频为 5-10 分钟，压缩包大小不超过 200M，讲解演示已实现的核心功能，建议配字幕。

技术方案合并架构、算法、实现、安装部署、用户手册、记忆流转、真实案例、测试结果、效果验证与适配说明。源码目录保存一份完整源码压缩包，包含必要技术规范、固定上游源码、许可证和构建配置。提交区不存放 README、占位文件、独立手册、分篇 PDF、原始截图、旧安装包或第二份技术方案。

## 生成与检查

2026-09-10 起按 [统一修订台账](MATERIAL_ALIGNMENT.md) 重新采集当前界面，并统一目录监控、Dreaming 与多设备协作的功能表述。作品使用正面、平实的语言，直接说明操作与实际结果；测试数字同时注明版本、环境和样本量。

先更新本目录各篇 Markdown，以及 `build/release/scripts/build-presentation.py` 中的演示叙事和图形，再运行：

```bash
python3 build/release/scripts/export-documentation.py
python3 build/release/scripts/prepare-submission.py build-source
python3 build/release/scripts/prepare-submission.py check
```

PPT 从源脚本生成18页可编辑图文，并嵌入真实操作短片。图片、视频片段及输入摘要分别保存在 `assets/operations/03-current-workflows/`、`assets/presentation-clips/` 与 `assets/presentation-manifest.json`。页面对应视频分镜见 [项目报告与演示说明](PRESENTATION_AND_VIDEO.md)。

文档工具使用 `build/release/requirements-docs.txt`、系统 LibreOffice 和 FFmpeg，先内嵌图片，再转换为真正的 Word 97 `.doc`。中间 DOCX 和从最终 DOC 回读的 PDF 位于 `build/release/out/documents/`，须逐页观察。原始图片保存在 `assets/operations/`。

`check` 严格核对目录、文件名、文件集合、格式、源码文件清单与摘要。完整材料使用 `check --require-video`。通过实际观看核对视频时长、功能覆盖和匿名内容。

## 中文写作与匿名

每段围绕一个意思，先说明结果，再给出理解或复现所需的细节。操作步骤用编号，平行项和比较项用列表或表格。使用实际按钮名称、具体动作和真实结果，删除空泛过渡、自问自答和无关对照。

学校和申报人信息仅用于目录命名与内部记录。项目报告、技术方案、截图、视频和提交说明使用匿名作品信息。检查结论见 [材料检查记录](PREPARATION_CHECK.md)。

## 插图排版

真实截图与对应操作放在一起，图片按比例缩放至正文宽度内，图注紧随画面。导出保留原图字节，自动分页并限制显示高度，便于连续阅读。
