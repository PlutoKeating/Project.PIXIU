# PIXIU 银河麒麟 V11 适配报告

## 适配结论

0.1.12 正式包已在银河麒麟 V11 amd64 完成安装与启动。系统 Embedding、Vector Engine 和产品记忆写入、查询、遗忘测试通过。三台独立虚拟机完成共享与断连并发更正验证。

## 适配范围

| 层级 | 适配内容 |
|------|----------|
| 桌面 | Qt5、UKUI 主题、快捷键、通知、桌面入口 |
| 服务 | systemd user service、XDG 配置/数据/状态目录 |
| AI | Kylin Embedding SDK、AI Runtime、模型目录 |
| 向量库 | Kylin Vector Engine SDK、应用数据库生命周期 |
| Agent | KylinAgent、agent-runtime、PIXIU MemoryProvider |
| 发布 | `.deb`、依赖、版本清单、SHA-256、Ed25519 签名 |

## 用户会话架构

系统 AI Runtime 的 Unix socket 按桌面用户 UID 隔离。PIXIU 后端因此运行在当前用户的 systemd 会话中，使 Embedding、Vector Engine、Agent Gateway 和本地数据都处于同一安全边界。

服务启动时验证 MainPID 所属 UID、loopback 端点身份、产品版本和数据库状态，避免连接到错误用户或占用相同端口的其他服务。

## Embedding SDK

系统通过 Kylin `coreai/embedding` 接口生成 gte-base 768 维文本向量。启动检查会确认模型、AI Runtime、客户端库和 SDK 调用可用，检查失败时服务停止启动并报错。

## Vector Engine SDK

产品使用系统 Vector Engine 的 `ConnectParam(appId)` 本地连接，通过 `LoadDBFile` 加载独立应用数据库，并执行集合创建、向量写入、搜索、删除、清理与断开。

启动预检在首条业务写入前验证数据库生命周期。产品 API 另行验证记忆写入、召回、遗忘和删除后不可见。

## KylinSDK 与界面

`KYSDK=ON` 构建启用系统快捷键、通知和 Qt 扩展适配。界面按浅色和深色主题设置文字、背景及状态颜色，消息区保持居中阅读宽度，长会话标题省略显示，键盘焦点和错误状态保持可见。

Debian 兼容构建使用标准 Qt 快捷键和系统托盘通知，用于验证基本桌面功能。麒麟 SDK 功能在 V11 环境单独测试。

## 安装与升级

单一 `.deb` 包含 PIXIU 后端、内嵌管理界面、记忆插件、KylinAgent 宿主适配、Runtime 离线依赖、原生扩展、SBOM 和 NOTICE。

安装前置脚本校验 V11 与架构；服务启动再次校验双 SDK；用户首次启动校验 Agent 与 Runtime。任一检查失败，系统都会停止对应步骤并报错。

图形升级在安装前校验资产摘要与独立签名，安装后核对 dpkg 版本、后端版本、数据库 schema、Provider 和服务健康。失败时恢复旧包、配置、数据和服务。

## 原生验证结果

以下结果来自 0.1.12 正式包，原生记录绑定源码提交和安装包摘要。

| 项目 | 结果 |
|------|------|
| V11 amd64 strict 单包安装 | 通过 |
| 桌面用户后端服务 | 通过 |
| Embedding runtime | `kylin`，compliant |
| Vector Engine runtime | `kylin`，compliant |
| 产品记忆写入与召回 | 通过 |
| 向量删除与遗忘隐藏 | 通过 |
| `/capabilities` | `contest_ready=true` |
| 三端共享与并发恢复 | 完整记录一致 |

## 安全与可移植性

适配层负责调用平台 SDK。V11 严格配置要求使用原生实现；Debian 兼容配置提供基础写入、检索和测试功能，并记录实际使用的实现。

用户配置权限为 0600，设备同步使用可信配对、签名和 mTLS。敏感内容不进入共享域；模型密钥不写入源码、包、日志或测试证据。
