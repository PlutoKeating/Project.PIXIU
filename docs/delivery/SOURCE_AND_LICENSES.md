# 源码说明与许可证

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

上游源码以提交编号固定版本，源码归档提供对应许可证和补丁。Runtime 的 Python 依赖按文件摘要锁定，并从构建阶段准备的依赖目录离线安装。构建日志和产物摘要由构建过程生成。

## 源码质量规范

- Python 使用类型标注、清晰命名和 pytest；C++/Qt 遵循模块现有风格与 CTest。
- Engine 只通过 Repository 接口访问基础设施；Agent 适配只调用公共 HTTP API。
- 专有 Kylin SDK 位于适配层后，Debian 构建提供明确降级路径。
- 源码归档仅包含产品构建输入、公开配置模板和必要许可证。
- 一个逻辑变更对应一个本地 Git 提交，版本由根目录 `VERSION` 单一派生。

## 源码交付与复现

源代码/PIXIU源代码.tar.gz 包含 frontend、backend、build/release 和必要的 third_party 构建输入，以及运行所需界面资源和 Runtime 技能。归档范围限于产品复现所需文件。

宿主和 Runtime 提供固定版本源码；两个麒麟 SDK 提供编译头文件和许可证，运行库由目标系统安装。Kreuzberg 按锁定的预编译包安装。首次构建需要联网下载依赖。

按照首章可完成依赖安装、源码核对、编译、安装和操作验证。SOURCE-MANIFEST.json 记录文件摘要、权限和上游提交，运行 python3 verify-source.py 可核对完整性。解压后的 README 提供相同的编译入口。

## 软件物料清单

安装包内置 SPDX 2.3 格式的软件物料清单和 NOTICE，记录桌面宿主、Runtime 及 Python 依赖。发布清单还记录产品版本、架构、构建配置、接口版本和上游源码版本。

构建检查核对源码、程序、依赖锁及安装日志的摘要，并扫描认证信息、私钥、令牌和个人路径，确保组件来源可追溯。
