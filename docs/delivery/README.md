# PIXIU 交付材料维护

当前提交按用户于2026-09-15提供的新版赛方图片执行，作品编号与原文名称维护在 [平台作品信息](../submission-identity.json)。两层同名目录均为：

```text
603821-PIXIU·貔貅：面向麒麟OS Agent的去中心化记忆系统设计与实现/
├── 603821-PIXIU·貔貅：面向麒麟OS Agent的去中心化记忆系统设计与实现/
│   ├── 项目报告.pptx
│   ├── 技术方案.docx
│   └── 演示视频.zip
└── 源代码/
    ├── PIXIU源代码.tar.gz
    ├── pixiu_0.1.12-1_amd64.deb
    └── pixiu_0.1.12-1_amd64.deb.sha256
```

当前命名覆盖 DELIVERY_PLAN.md §0 的历史命名，冻结原文保留作为历史记录。四项作品内容及匿名要求继续适用。制作目录与复核记录放在正式作品目录之外，不额外交付。

## 当前产物与更新入口

项目报告保留用户最新编辑的35页正式版本及新封面、尾页，全部备注为空。文档导出只保留并记录当前正式PPT，不再复制制作模板覆盖用户的新编辑；本轮仅清除办公文件作者元数据，页面内容未改。

技术方案从八篇最新技术、部署、手册、流转、案例、测试、适配及源码说明合并，使用 LibreOffice 导出真正的 DOCX，首章给出独立可执行的编译和安装说明。复核用 PDF 留在 `build/release/out/documents/`。依赖沿用 `build/release/requirements-docs.txt`。

演示视频采用已审阅的499.333秒版本，ZIP内部为演示视频.mp4，保留原始视频字节。源码包按当前产品源码、必要固定上游输入、许可证和构建配置重新生成，并逐文件核对。

```bash
python3 build/release/scripts/export-documentation.py
python3 build/release/scripts/export-documentation.py --check
python3 build/release/scripts/prepare-submission.py build-source
python3 build/release/scripts/prepare-submission.py check --require-video
```

先提交制作脚本和文档，再生成源码包，可使归档记录清洁的源码提交。作品目录中只保留规定文件，不放独立手册、额外PDF、README或原始证据；用户明确要求的x64安装包及摘要与源码归档并列。具体核对记录见 PREPARATION_CHECK.md。

随包文档不得出现参赛者身份、个人代码托管地址或本机用户路径。DOCX使用黑色实线全边框表格和带提示符的终端代码框，禁止emoji及符号字体列表。


技术方案包含独立匿名封面、原生自动目录和正文页眉页脚。目录由一级、二级标题生成，使用Word的TOC域；页眉左侧为PIXIU技术方案，右侧通过STYLEREF域读取当前大章节，页脚使用居中的PAGE域。封面不显示页眉页码，目录使用罗马页码，正文从1开始。修改内容后可在Word中右键目录选择“更新域／更新整个目录”。导出脚本通过系统python3-uno调用LibreOffice生成并更新目录及页码，复核PDF仅存于制作输出目录。

标题采用Word原生多级编号：八个一级标题使用一、二、三等汉字编号，63个二级标题使用1.1、1.2、2.1等阿拉伯数字。二级编号启用legal numbering，确保上级汉字不会带入二级编号。编号后刷新原生目录及页码；number-document-headings.py可直接处理现有DOCX以保留人工排版。

图注紧随图片并居中；全部23个表格及终端代码框均有上方居中的表注，按全文顺序编号。`format-document-captions.py`维护表注名称与段落对齐，并设置与下方表格同页衔接；应用后刷新自动目录和页码。

全文表述复核以用户最新保存的DOCX为编辑基准，修改记录见editorial-revision.json，工具为revise-document-prose.py。当前文档8个大章节、63个二级标题，43页。效果验证章包含数据集与标注、对比实验设计、量化实施方案和指标分析，实测数字保留对应环境与样本范围。Times New Roman四种常用字形已在本机安装并刷新字体缓存。
