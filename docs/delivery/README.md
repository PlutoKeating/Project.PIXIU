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
