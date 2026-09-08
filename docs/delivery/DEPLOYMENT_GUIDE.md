# PIXIU 部署指南

## 安装环境

本指南适用于银河麒麟桌面操作系统 V11、amd64 架构，以下命令使用 `pixiu_0.1.9-1_amd64.deb`。软件安装后在当前桌面用户的会话中运行。

安装前，在系统“设置 → AI 模块管理”中启用 AI 能力，并确认软件源提供 Kylin Embedding、Vector Engine 和桌面 KylinSDK 运行组件。

## 校验安装文件

准备同一版本的软件包、摘要和签名文件，在下载目录运行：

```bash
sha256sum -c pixiu_0.1.9-1_amd64.deb.sha256
```

摘要用于检查文件是否完整，发布公钥和 Ed25519 签名用于验证文件来源。签名验证步骤见同版发布说明。当前 `submission` 中保存的 0.1.7 安装包属于历史归档。

## 安装与启动

双击 `.deb` 文件并按系统安装器提示操作，或在终端运行：

```bash
sudo apt install ./pixiu_0.1.9-1_amd64.deb
```

安装完成后，从应用菜单打开“PIXIU”，或运行：

```bash
pixiu
```

首次启动会创建当前用户的配置和数据目录，启动 `pixiu-backend.service`，并激活包内记忆插件。启动器会检查桌面程序和 Runtime 的版本是否兼容。

## 检查服务

在“设置 → 服务与能力”点击“读取服务与能力”，确认桌面与后端版本一致、数据库就绪，以及两个系统 SDK 正常运行。终端检查命令如下：

```bash
systemctl --user status pixiu-backend.service
curl -s http://127.0.0.1:8765/version
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/capabilities
```

| 检查项 | 0.1.9 的预期结果 |
|---|---|
| 后台服务 | `active (running)`，属于当前桌面用户 |
| 版本 | 产品 `0.1.9`、HTTP API `0.5.0`、数据库版本 `13` |
| 健康状态 | `ready`、数据库 `ok` |
| 系统 SDK | Embedding 与 Vector Engine 均为 `runtime=kylin` |

能力接口中的 `contest_ready=true` 表示当前系统与 SDK 已就绪。业务功能、性能和多设备结果还需按验收方案测试。

## 配置与数据位置

软件按 XDG 约定保存当前用户的配置和数据：

```text
$XDG_CONFIG_HOME/pixiu/pixiu.env
$XDG_DATA_HOME/pixiu/pixiu.db
$XDG_STATE_HOME/pixiu/
```

这些环境变量为空时，分别使用 `~/.config`、`~/.local/share` 和 `~/.local/state`。配置文件权限为 0600，仅供当前用户读写。模型密钥通过 Agent 设置界面交给 Runtime 保存。

## 多设备部署

每台设备安装与其架构匹配的同一版本软件。设备之间需要局域网互通，并允许 mDNS 发现和同步服务通信。按用户手册的令牌交换步骤建立双向信任。

三设备验证时，分别检查每台设备都信任另外两台，再完成共享写入、离线恢复和遗忘测试，记录各端结果。节点在线和队列为空只能说明当前连接及积压状态。

## 升级

在“设置 → 应用与升级”点击“检查更新”。软件依次下载文件、核对摘要和签名、请求系统授权、安装并检查服务。

升级会备份旧包、配置、数据库和同步身份。安装或健康检查失败时，系统尝试恢复备份并显示结果。升级成功后，保存工作并重启整个应用，让新程序生效。

## 卸载

```bash
sudo apt remove pixiu
```

普通卸载会保留当前用户的配置与记忆数据，重新安装后可继续使用。需要清理个人数据时，先备份所需内容，再核对要删除的数据目录。

## 故障排查

后端启动失败时，可重启服务并查看最近日志：

```bash
systemctl --user restart pixiu-backend.service
journalctl --user -u pixiu-backend.service -n 100 --no-pager
```

SDK 未就绪时，检查系统 AI 模块、SDK 运行组件和用户会话服务。修复依赖后重新启动 PIXIU。麒麟严格配置会在必需依赖不可用时停止启动并报错。

助手未加载记忆插件时，检查包内 Runtime 版本和启动错误，再重新打开 PIXIU。同步长时间没有完成时，检查设备连接、系统时间、暂停开关和待同步操作。
