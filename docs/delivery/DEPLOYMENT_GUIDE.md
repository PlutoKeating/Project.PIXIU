# PIXIU 部署指南

## 适用环境

- 操作系统：银河麒麟桌面操作系统 V11
- 架构：amd64
- 软件包：`pixiu_0.1.7-3_amd64.deb`
- 安装方式：图形软件安装器或 APT
- 运行方式：桌面用户 systemd 服务

安装前请在“设置 → AI 模块管理”中启用系统 AI 能力，并确保系统软件源可提供 Kylin Embedding、Vector Engine 与桌面 KylinSDK 运行组件。

## 校验安装包

```bash
cd submission/04-部署文档/01-可安装软件
sha256sum -c pixiu_0.1.7-3_amd64.deb.sha256
```

预期 SHA-256：

```text
24f393982ba227bb8d9feb58f1bfcd26ce83122bfa36fa505a1f3c80ffe6ec02
```

## 安装

双击 `.deb` 并在图形安装器中确认，或运行：

```bash
sudo apt install ./pixiu_0.1.7-3_amd64.deb
```

安装完成后，从应用菜单打开“PIXIU”，或运行：

```bash
pixiu
```

首次启动会为当前桌面用户创建配置与数据目录，启动 `pixiu-backend.service`，并激活包内 PIXIU MemoryProvider。严格画像会校验 KylinAgent 与 Runtime 版本。

## 验证服务

```bash
systemctl --user status pixiu-backend.service
curl -s http://127.0.0.1:8765/version
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/capabilities
```

验收时应确认：

- 服务为 `active (running)`，MainPID 属于当前桌面用户；
- `/version` 返回产品版本 `0.1.7` 与 schema 版本；
- `/health` 返回数据库就绪；
- `/capabilities` 中 Embedding 与 Vector Engine 为 `runtime=kylin`；
- `contest_ready=true`。

## 数据与配置

默认路径遵循 XDG 规范：

```text
$XDG_CONFIG_HOME/pixiu/pixiu.env
$XDG_DATA_HOME/pixiu/pixiu.db
$XDG_STATE_HOME/pixiu/
```

配置文件权限为 0600。模型密钥由 Agent Runtime 的隐藏认证入口保存，不应写入 `pixiu.env`、终端命令或交付日志。

## 多设备部署

在每台设备安装同一版本和架构的软件包。启动后进入“同步与设备”，由一台设备生成配对请求，另一台设备核对名称与六位 PIN 后确认。

设备应位于可互访的局域网，并允许 mDNS 和 PIXIU 同步端口通信。配对后检查三台设备均在线、可信连接为完全图、待同步队列为零。

## 更新

在“设置 → 关于与更新”中检查新版本。客户端会依次完成资产选择、下载、SHA-256 与 Ed25519 签名校验、系统授权、安装和健康检查。

升级会备份原软件包、配置、SQLite 数据和同步身份。安装或健康检查失败时，系统恢复旧版本与数据，并在界面中显示恢复结果。

## 卸载

```bash
sudo apt remove pixiu
```

普通卸载保留当前用户的配置与记忆数据，便于重新安装。需要彻底清理个人数据时，应先导出所需记忆，再按用户手册确认清理范围。

## 故障排查

### 后端未启动

```bash
systemctl --user restart pixiu-backend.service
journalctl --user -u pixiu-backend.service -n 100 --no-pager
```

### 双 SDK 未就绪

检查系统 AI 模块、SDK 运行包与用户会话服务，再重新启动 PIXIU。严格画像不会自动切换到 portable 实现。

### Agent 未加载 PIXIU

确认 KylinAgent Runtime 为受支持的 0.9.x 版本，并重新打开 PIXIU。启动器会幂等激活 Provider，不覆盖非 PIXIU 管理的同名插件。

### 同步未收敛

确认设备均在线、系统时间正确、同步未暂停，再查看节点状态与积压操作。离线恢复后反熵对账会自动继续。
