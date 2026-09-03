# D-04 银河麒麟 V11 部署指南工作稿

- 适用版本：0.1.7 功能基线；最终候选号待定
- 状态：当前记忆包路径可用；Module E 与双 SDK 最终安装尚未闭环

## 安装目标

最终用户获得一个按架构构建的 `pixiu_<version>-<revision>_<arch>.deb`，可在 V11
图形软件安装器打开，或运行 `sudo apt install ./pixiu_*.deb`。安装应自动注册后端
服务、桌面入口、记忆控制台与 Module E，不要求手工部署源码。

## 当前开发安装

```bash
git submodule update --init --recursive
PIXIU_PROFILE=kylin-v11-x86_64 make -C build/release deb
sudo apt-get install -y ./build/release/out/pixiu_0.1.7-1_amd64.deb
systemctl status pixiu-backend.service
```

当前命令不代表完整最终交付：Module E 尚未随包，且 `KYSDK=OFF`/portable 不能
替代 V11 双 SDK 严格画像。最终安装必须记录系统版本、架构、包版本、宿主/runtime、
双 SDK capability、服务状态和首次完整 Agent 操作。

V11 双 SDK 候选包使用 `kylin-v11-native-x86_64` profile。该画像令
`PIXIU_KYSDK=ON` 同时约束桌面 KylinSDK 和后端 Embedding/Vector 原生扩展；构建、
安装及真实写入/检索由独立 `pixiu-kylin-v11-native` 工作流执行并输出脱敏证据。

## 升级、卸载与恢复

设置页可检查并一键下载安装现有 PIXIU 包；最终版还需独立签名、兼容矩阵、备份/
回滚、安装后健康检查和受控重启。升级必须保留记忆数据库、配置和同步身份。
默认配置以 `/usr/share/pixiu/pixiu.env.default` 模板随包，`postinst` 仅在首次安装
创建 `/etc/pixiu/pixiu.env`；后者不属于 dpkg conffile，升级保留并幂等迁移，避免
每机随机口令导致非交互安装弹出配置冲突。
卸载与 purge 的数据语义须在最终版明确区分，并在全新机、重装、升级失败上取证。

故障排查入口、日志位置、严格/降级差异和最终依赖包名以
`../DELIVERY_PLAN.md`、`../../build/release/README.md` 及目标 profile 为准。
