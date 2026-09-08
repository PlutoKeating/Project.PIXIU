# PIXIU 交付材料维护

`submission/` 只保存按赛方要求命名的正式文件。编写源、截图、检查记录和中间导出物在该目录之外维护。唯一权威要求见 [交付计划第 0 节](../DELIVERY_PLAN.md#0-赛方交付作品要求唯一权威永久冻结)。

提交目录有两层同名目录，名称由学校、作品名称、主申报人姓名以 `+` 连接。外层还包含与内层并列的 `源代码/`。内层保存 `项目报告.pptx`、`技术方案.doc`，视频制作完成后放入同层并命名为 `演示视频.zip`。视频为 5-10 分钟，压缩包大小不超过 200M，讲解演示已实现的核心功能，建议配字幕。

技术方案合并架构、算法、实现、安装部署、用户手册、记忆流转、真实案例、测试结果、效果验证与适配说明。源码目录保存一份完整源码压缩包，包含必要技术规范、固定上游源码、许可证和构建配置。提交区不存放 README、占位文件、独立手册、分篇 PDF、原始截图、旧安装包或第二份技术方案。

## 生成与检查

先更新本目录各篇 Markdown 和 `assets/项目报告.pptx`，再运行：

```bash
python3 build/release/scripts/export-documentation.py
python3 build/release/scripts/prepare-submission.py build-source
python3 build/release/scripts/prepare-submission.py check
```

文档工具使用 `build/release/requirements-docs.txt` 和系统 LibreOffice，先内嵌图片，再转换为真正的 Word 97 `.doc`。中间 DOCX 和从最终 DOC 回读的 PDF 位于 `build/release/out/documents/`，须逐页观察。原始图片保存在 `assets/operations/`。

`check` 严格核对目录、文件名、文件集合、格式、源码文件清单与摘要。视频未放入时只报告该缺项；放入后使用 `check --require-video`。视频时长、核心功能覆盖和匿名内容仍需实际观看核验。

## 中文写作与匿名

每段围绕一个意思，先说明结果，再给出理解或复现所需的细节。操作步骤用编号，平行项和比较项用列表或表格。使用实际按钮名称、具体动作和真实结果，删除空泛过渡、自问自答和无关对照。

学校和申报人信息仅用于目录命名与内部记录。项目报告、技术方案、截图、视频和提交说明不得出现学校、学院、校徽、指导教师或参赛学生姓名。检查结论见 [材料检查记录](PREPARATION_CHECK.md)。
