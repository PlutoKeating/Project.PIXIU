# PIXIU 部署指南

## 安装环境

银河麒麟桌面操作系统 V11，amd64 架构，Python 3.12。系统 AI 模块提供 Embedding、Vector Engine 和麒灵模型服务。

0.1.12 安装包包含桌面程序、后台服务、Agent Runtime、文档解码组件及所需 Python 依赖。文档处理全程在后台运行，安装包自带解码能力。

## 下载与安装

从 0.1.12 发布页面下载安装包及对应校验文件。在下载目录执行：

```bash
sha256sum -c pixiu_0.1.12-1_amd64.deb.sha256
sudo apt install ./pixiu_0.1.12-1_amd64.deb
```

正式发布提供 SHA-256 和 Ed25519 签名。应用内更新会自动完成签名校验。

## 启动

从应用菜单打开 PIXIU，或执行：

```bash
pixiu
```

首次启动自动创建当前用户的数据目录，启动后台服务并激活记忆插件。在设置中查看模型连接及服务状态，即可开始会话。



![0.1.12：启动后版本一致，记忆服务和系统 SDK 就绪](assets/operations/02-current-release/sdk.png)

0.1.12：启动后版本一致，记忆服务和系统 SDK 就绪。

## 数据与升级

配置、记忆和设备身份保存在当前用户目录。升级会保留这些数据，并在完成后核对版本和服务状态。

正式包测试已通过新装启动、签名升级和自动恢复。升级前后 47 条记忆的完整摘要一致；第三台新装测试机生成了独立设备身份。

## 运行检查

```bash
systemctl --user status pixiu-backend.service
journalctl --user -u pixiu-backend.service -n 50
```

正常启动后，设置页显示服务就绪。麒麟模型授权由系统“AI 模块管理”维护。
