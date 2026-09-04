# 赛事交付文档工作区

本目录维护最终 D-01～D-10 的可审查 Markdown 工作源。官方赛题原文和官方 PPTX
保持只读；所有解释、截图索引、测试数据和发布信息只更新在本目录及
`docs/DELIVERY_PLAN.md`。

工程实现与取证的关键路径、阶段门和提交序列见
`docs/IMPLEMENTATION_MASTER_PLAN.md`；本目录状态不得早于对应阶段门更新为“已审核”。
对外最终文件不在本目录手工复制维护，而由根目录 `submission/` 的机器可读清单统一
收集、校验和打包；这样可防止工作稿与最终 release commit 分叉。

`submission/render_documents.py` 已提供统一 A4 中文排版：可在正式目录外生成带
“不得提交”标识的草稿 PDF/DOCX，最终模式只有在其他发布门全通过、状态行无待办且
工作树固定到 `release_commit` 时才写入正式目录。`build_submission.py --package`
会验证办公文件、PDF、ZIP、视频和安装资产的真实结构，并复核安装包摘要与签名。

| 编号 | 工作源 | 最终产物 | 状态 |
|------|--------|----------|------|
| D-01 | `PRESENTATION_AND_VIDEO.md` | 项目报告 `.pptx` | 内容骨架完成，最终证据待补 |
| D-02 | `TECHNICAL_SOLUTION.md` | 技术方案 `.docx` + `.pdf` | 工作稿已建立，最终数据待补 |
| D-03 | `SOURCE_AND_LICENSES.md` | 源码包/仓库快照 + 清单 | Agent SBOM/NOTICE/源码证据已通过；最终 commit 冻结后生成 |
| D-04 | `DEPLOYMENT_GUIDE.md` | 部署文档 `.pdf` | 工作稿已建立，最终包待重验 |
| D-05 | `PRESENTATION_AND_VIDEO.md` | ≤7 分钟演示视频 | 脚本已建立，最终录制待完成 |
| D-06 | `USER_MANUAL.md` | 用户手册 `.pdf` | Module E 契约已写，真实宿主截图待补 |
| D-07 | `TEST_REPORT.md` | 效果/测试报告 `.pdf` + 原始数据 + 三设备最终 JSON | portable 证据及 Agent 两阶段采集器已有；总 JSON 已纳入打包硬门，真实 V11 待补 |
| D-08 | `MEMORY_LIFECYCLE.md` | 记忆流转说明 `.pdf` | Module E 映射已写，宿主/长期化实证待补 |
| D-09 | `APPLICATION_CASES.md` | 实际应用案例章节/附件 | 流程已写，最终截图/日志待补 |
| D-10 | `KYLIN_V11_ADAPTATION_REPORT.md` | V11 适配报告 `.pdf` | strict 单包与双 SDK 产品链已实测；完整 Agent/三设备待补 |

维护规则：每份文档首页记录产品版本、Git commit、日期、作者/审核人和状态；所有
数值、截图与视频时间戳链接同一候选 release 的原始证据。导出 PDF/PPT 前必须执行
`docs/DELIVERY_PLAN.md` 的发布门禁，不在仓库外维护不可追溯的分叉版本。
