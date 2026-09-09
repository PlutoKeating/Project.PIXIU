# PIXIU 源代码规范与许可证

## 源码结构

| 目录 | 内容 | 归属 |
|------|------|------|
| `frontend/` | 内嵌记忆管理界面与 UKUI 适配 | 团队原创 |
| `backend/engine/` | 接入、偏好、知识、冲突、安全 | 团队原创 |
| `backend/foundation/` | API、存储、检索、流转、同步、评测 | 团队原创 |
| `backend/agent/` | MemoryProvider 与记忆工具 | 团队原创 |
| `build/release/` | 构建、打包、发布与源码导出 | 团队原创 |
| `backend/platform/` | 初始化、启动、升级与数据迁移 | 团队原创 |
| `tests/acceptance/` | 跨模块用户场景验证及模拟夹具 | 团队原创 |
| `third_party/` | 固定版本的上游与系统 SDK 源码 | 上游依赖 |

## 原创边界

PIXIU 原创成果包括统一记忆模型、多源接入、偏好与知识引擎、三通道混合检索、冲突仲裁、精准遗忘、CRDT/Gossip/反熵同步、Agent 适配、两个系统 SDK 的集成、管理界面和评测发布工具。

KylinAgent 与 agent-runtime 提供通用会话、规划、工具、审批和运行控制。交付材料记录这些上游组件的来源、版本和许可证。

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

## 源码交付与复现

`源代码/PIXIU源代码.tar.gz` 包含产品版本对应的前端、后端、Agent 适配、构建配置、测试、技术规范和四个固定版本上游源码。源码清单记录文件摘要、可执行权限和上游提交；保留第三方许可证及版权声明。

解压后先运行包内 `verify-source.py` 核对文件。后端测试使用 `backend/requirements.txt` 与 `backend/foundation/requirements-sync.txt` 的依赖，前端使用 CMake。严格安装包需在银河麒麟 V11 安装官方 SDK 和画像列出的开发依赖，按构建说明执行。依赖清单与源码一起提供，源码压缩包不包含预下载的系统软件或 Python wheels。

Git 工作区通过固定提交核验上游；解压源码通过 SOURCE-MANIFEST.json 核验上游文件、版本及构建时间，不需要恢复 .git。先运行 `python3 verify-source.py`，再按 `build/release/README.md` 准备系统与 Python 依赖，使用同一宿主和 Runtime 构建入口。源码不含预下载依赖；原生完整安装验证须在 V11 进行。

## 软件物料清单

安装包内置 SPDX 2.3 SBOM 与 NOTICE，覆盖宿主、Runtime 和全部 wheel 依赖。发布清单同时记录产品版本、架构、构建画像、API/schema/provider 版本、上游 commit 与 SDK 源码版本。

供应链审计要求宿主产物、对应源码、构建日志、Runtime wheelhouse、锁文件和离线安装日志摘要一致，并扫描认证信息、私钥、令牌和个人路径。
