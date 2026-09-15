# PIXIU 交付材料维护

当前提交按用户于2026-09-15提供的新版赛方图片执行，作品编号与原文名称维护在 [平台作品信息](../submission-identity.json)。两层同名目录均为：

```text
603821-PIXIU·貔貅：面向麒麟OS Agent的去中心化记忆系统设计与实现/
├── 603821-PIXIU·貔貅：面向麒麟OS Agent的去中心化记忆系统设计与实现/
│   ├── 项目报告.pptx
│   ├── 技术方案.doc
│   └── 演示视频.zip
└── 源代码/
    └── PIXIU源代码.tar.gz
```

当前命名覆盖 DELIVERY_PLAN.md §0 的历史命名，冻结原文保留作为历史记录。四项作品内容及匿名要求继续适用。制作目录与复核记录放在正式作品目录之外，不额外交付。

## 当前产物与更新入口

项目报告为用户已验收的34页科技风版本，直接复制 `submission/presentation-production/render/abc-trial/PIXIU项目报告-科技风试作版.pptx`，保留新封面和尾页且无备注。导出脚本核对其审阅摘要，禁止重新生成旧31页覆盖最终稿。

技术方案从八篇最新技术、部署、手册、流转、案例、测试、适配及源码说明合并，使用 LibreOffice 导出真正的 Word 97 DOC。复核用 DOCX/PDF 留在 `build/release/out/documents/`。依赖沿用 `build/release/requirements-docs.txt`。

演示视频采用已审阅的499.333秒版本，ZIP内部为演示视频.mp4，保留原始视频字节。源码包按当前产品源码、五个固定上游、许可证和构建配置重新生成，并逐文件核对。

```bash
python3 build/release/scripts/export-documentation.py
python3 build/release/scripts/export-documentation.py --check
python3 build/release/scripts/prepare-submission.py build-source
python3 build/release/scripts/prepare-submission.py check --require-video
```

先提交制作脚本和文档，再生成源码包，可使归档记录清洁的源码提交。作品目录中只保留规定文件，不放独立手册、额外PDF、README、安装包或原始证据。具体核对记录见 PREPARATION_CHECK.md。
