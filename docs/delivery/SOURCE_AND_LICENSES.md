# PIXIU 源代码规范与许可证

## 源码结构

| 目录 | 内容 | 归属 |
|------|------|------|
| `frontend/` | PIXIU 记忆控制台与 UKUI 适配 | 团队原创 |
| `backend/engine/` | 接入、偏好、知识、冲突、安全 | 团队原创 |
| `backend/foundation/` | API、存储、检索、流转、同步、评测 | 团队原创 |
| `integrations/kylin_agent/` | MemoryProvider 与记忆工具 | 团队原创 |
| `build/release/` | 构建、打包、升级、取证与交付门禁 | 团队原创 |
| `third_party/` | 固定版本的上游与系统 SDK 源码 | 上游依赖 |

## 原创边界

PIXIU 原创成果包括统一记忆模型、多源接入、偏好与知识引擎、三通道混合检索、冲突仲裁、精准遗忘、CRDT/Gossip/反熵同步、Agent 适配、双 SDK 产品接线、控制台和评测发布体系。

KylinAgent 与 agent-runtime 提供通用会话、规划、工具、审批和运行控制。交付材料明确披露上游来源，不把这些通用能力宣称为团队原创。

## 主要上游依赖

| 依赖 | 用途 | 许可证 |
|------|------|--------|
| `kylin-agent` | 桌面 Agent 宿主 | AGPL-3.0-only |
| `agent-runtime` | Agent 运行时与 MemoryProvider 接口 | MIT |
| `kylin-coreai-embedding` | 指定文本向量接口 | GPL-3.0-or-later |
| `libkysdk-vector-engine-client` | 指定系统向量数据库客户端 | Apache-2.0 |

每个上游组件固定 commit，并随源码归档提供许可证、NOTICE、补丁、构建记录和摘要。Runtime 的 Python 依赖以哈希锁定 wheelhouse 离线安装。

## 源码质量规范

- Python 使用类型标注、清晰命名和 pytest；C++/Qt 遵循模块现有风格与 CTest。
- Engine 只通过 Repository 接口访问基础设施；Agent 适配只调用公共 HTTP API。
- 专有 Kylin SDK 位于适配层后，Debian 构建提供明确降级路径。
- 密钥、`.env`、用户数据库、日志、缓存和构建产物不得进入源码归档。
- 一个逻辑变更对应一个本地 Git 提交，版本由根目录 `VERSION` 单一派生。

## 可重建性

完整源码应从同一标签的洁净 checkout 和四个固定 gitlink 重建；GitHub 自动生成的
Source code 压缩包不包含 submodule 实体，不能作为完整离线源码交付。
`submission` 当前人工维护，仓库已无旧文档所称的源码/总提交 ZIP 自动归档器。
严格安装包内的宿主对应源码、适配补丁、许可证、SPDX 与 Runtime 锁由供应链脚本
生成和校验；最终赛事源码归档仍须核对完整文件集合、许可证、摘要和候选 commit。

`submission/03-源代码及规范/Project.PIXIU-source.tar.gz` 是既有历史归档，不能代表
新 Release 的源码。当前版本请 checkout 对应标签并初始化 submodule，再通过
`.github/workflows/release.yml` 的通用 CI 与 V11 原生构建门重建。

文档导出使用独立可选依赖 `build/release/requirements-docs.txt`（Markdown）和
LibreOffice；它们不进入产品运行依赖。原目录中的 Markdown 更新后执行
`python build/release/scripts/export-documentation.py`，重导出已有 PDF/DOCX，
并仅更新项目 PPT 的版本与已复核文本，保留幻灯片、形状和媒体。
`--check` 校验 `build/release/document-export-manifest.json` 的源稿/导出物摘要；
该校验不代替人工排版复核或赛事交付验收。官方原件和 README 不参与导出。

## 软件物料清单

安装包内置 SPDX 2.3 SBOM 与 NOTICE，覆盖宿主、Runtime 和全部 wheel 依赖。发布清单同时记录产品版本、架构、构建画像、API/schema/provider 版本、上游 commit 与 SDK 源码版本。

供应链审计要求宿主产物、对应源码、构建日志、Runtime wheelhouse、锁文件和离线安装日志摘要一致，并扫描认证信息、私钥、令牌和个人路径。
