# PIXIU 源代码规范与许可证

## 源码结构

| 目录 | 内容 | 归属 |
|------|------|------|
| `frontend/` | 内嵌记忆管理界面与 UKUI 适配 | 团队原创 |
| `backend/engine/` | 接入、偏好、知识、冲突、安全 | 团队原创 |
| `backend/foundation/` | API、存储、检索、流转、同步、评测 | 团队原创 |
| `backend/agent/` | MemoryProvider、文档工具与 Dreaming 后台整理 | 团队原创 |
| `build/release/` | 产品构建、打包及依赖锁定 | 团队原创 |
| `backend/platform/` | 初始化、启动、升级与数据迁移 | 团队原创 |
| `third_party/` | 固定版本的宿主和运行时源码、SDK 头文件及许可证 | 上游依赖 |

## 原创边界

PIXIU 原创成果包括统一记忆模型、多源接入、目录监控、Dreaming 受控文档整理与审批、偏好与知识引擎、三通道混合检索、冲突仲裁、精准遗忘、CRDT/Gossip/反熵同步、Agent 适配、两个系统 SDK 的集成、管理界面和评测发布工具。

KylinAgent 与 agent-runtime 提供通用会话、规划、工具、审批和运行控制。交付材料记录这些上游组件的来源、版本和许可证。

## 主要上游依赖

| 依赖 | 用途 | 许可证 |
|------|------|--------|
| `kylin-agent` | 桌面 Agent 宿主 | AGPL-3.0-only |
| `agent-runtime` | Agent 运行时与 MemoryProvider 接口 | MIT |
| `kylin-coreai-embedding` | 指定文本向量接口 | GPL-3.0-or-later |
| `openpyxl` / `Pillow` | XLSX 图片、公式、批注和图表内容 | MIT / HPND（许可证随 wheel 安装） |
| `kreuzberg` 4.10.3 | 后台 Office/PDF 解码 | MIT（安装包附带本地组件许可证） |
| `libkysdk-vector-engine-client` | 指定系统向量数据库客户端 | Apache-2.0 |

每个上游组件固定 commit，并随源码归档提供许可证、NOTICE、补丁、构建记录和摘要。Runtime 的 Python 依赖以哈希锁定 wheelhouse 离线安装。

## 源码质量规范

- Python 使用类型标注、清晰命名和 pytest；C++/Qt 遵循模块现有风格与 CTest。
- Engine 只通过 Repository 接口访问基础设施；Agent 适配只调用公共 HTTP API。
- 专有 Kylin SDK 位于适配层后，Debian 构建提供明确降级路径。
- 源码归档仅包含产品构建输入、公开配置模板和必要许可证。
- 一个逻辑变更对应一个本地 Git 提交，版本由根目录 `VERSION` 单一派生。

## 源码交付与复现

`源代码/PIXIU源代码.tar.gz` 是最小产品构建归档，包含 frontend、backend、build/release 和必要 third_party 输入。它排除 .git、.github、website、独立测试工程、网站、演示素材、历史文档、缓存及本地产物。产品运行所需的界面资源和 Runtime 技能仍保留。

宿主和 Runtime 保留固定版本的构建源码；两个麒麟 SDK 保留编译接口头文件和许可证，其库由目标系统提供。Kreuzberg 使用依赖锁中的 wheel，归档保留其许可证，不携带 Rust 网站和开发仓库。首次构建需要联网下载依赖，不能将本归档视为离线依赖包。

解压后的 README 给出编译及安装命令，与本技术方案首章一致。SOURCE-MANIFEST.json 记录每个文件的摘要、权限和上游提交；运行 python3 verify-source.py 可核对完整性。构建脚本从该清单读取上游版本，无需 Git 仓库。编译步骤、系统依赖、产物路径及故障处理均见本方案首章，不要求评委查阅额外文档。

## 软件物料清单

安装包内置 SPDX 2.3 SBOM 与 NOTICE，覆盖宿主、Runtime 和全部 wheel 依赖。发布清单同时记录产品版本、架构、构建画像、API/schema/provider 版本、上游 commit 与 SDK 源码版本。

供应链审计要求宿主产物、对应源码、构建日志、Runtime wheelhouse、锁文件和离线安装日志摘要一致，并扫描认证信息、私钥、令牌和个人路径。
