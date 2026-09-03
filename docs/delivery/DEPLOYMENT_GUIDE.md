# D-04 银河麒麟 V11 部署指南工作稿

- 适用版本：0.1.7 功能基线；最终候选号待定
- 状态：记忆包与 Module E 安装结构可用；真实宿主和双 SDK 最终安装尚未闭环

## 安装目标

最终用户获得一个按架构构建的 `pixiu_<version>-<revision>_<arch>.deb`，可在 V11
图形软件安装器打开，或运行 `sudo apt install ./pixiu_*.deb`。安装应自动注册后端
服务、桌面入口、记忆控制台与 Module E，不要求手工部署源码。

## 当前开发安装

```bash
git submodule update --init --recursive
sudo bash build/release/scripts/provision-target.sh \
  kylin-v11-x86_64 --with-build-deps
PIXIU_PROFILE=kylin-v11-x86_64 make -C build/release deb
sudo apt-get install -y ./build/release/out/pixiu_0.1.7-1_amd64.deb
systemctl status pixiu-backend.service
```

`kylin-v11-x86_64` 已明确声明 CMake/Ninja/Qt5 等通用构建依赖，预置脚本可幂等建立
`KYSDK=OFF` 的目标系统打包环境；双 SDK 开发包只属于严格原生画像，缺失时不得把
兼容画像结果记作原生验收。

包内已含 Module E 的只读 Provider 副本；首次以桌面用户启动 `pixiu` 时，启动器把
它幂等安装/升级到当前 Agent profile、保留显式配置，并设置
`memory.provider=pixiu`。若同名目录不是 PIXIU 管理的插件则拒绝覆盖；若宿主 runtime
不存在则控制台仍可启动，但 Agent 集成必须判为未就绪。`KYSDK=OFF`/portable 仍不能
替代 V11 双 SDK 严格画像。最终安装必须记录系统版本、架构、包版本、宿主/runtime、
双 SDK capability、服务状态和首次完整 Agent 操作。

包构建会把同一个 `PIXIU_VERSION` 写入 `/usr/share/pixiu/VERSION`，并经 systemd 的
`PIXIU_PRODUCT_VERSION` 注入后端。安装后先检查 `GET /version` 的产品/API/schema，
再检查 `GET /health` 的数据库就绪状态，最后以 `/capabilities` 判定 V11 双 SDK；
三者用途不可互相替代。Provider 初始化会拒绝混装版本、API 漂移、未就绪后端或超出
已验证 0.9.x 范围的宿主。

V11 双 SDK 候选包使用 `kylin-v11-native-x86_64` profile。该画像令
`PIXIU_KYSDK=ON` 同时约束桌面 KylinSDK 和后端 Embedding/Vector 原生扩展；构建、
安装及真实写入/检索由独立 `pixiu-kylin-v11-native` 工作流执行并输出脱敏证据。

## 升级、卸载与恢复

设置页可检查并一键下载安装现有 PIXIU 包。特权安装器会先验证包名、版本和架构，
安装后核对实际 dpkg 版本，并轮询 `/version`、`/health` 和包内 Provider manifest；
产品/API/schema/数据库/Provider 任一不一致都返回健康失败，GUI 不报告成功。最终版
还需独立签名、完整兼容矩阵、可信安装前备份/自动回滚和受控前端重启。当前健康失败
不会自动恢复旧包，运维人员必须把它视为升级失败而不是已回滚。升级必须保留记忆
数据库、配置和同步身份。
默认配置以 `/usr/share/pixiu/pixiu.env.default` 模板随包，`postinst` 仅在首次安装
创建 `/etc/pixiu/pixiu.env`；后者不属于 dpkg conffile，升级保留并幂等迁移，避免
每机随机口令导致非交互安装弹出配置冲突。
卸载与 purge 的数据语义须在最终版明确区分，并在全新机、重装、升级失败上取证。

故障排查入口、日志位置、严格/降级差异和最终依赖包名以
`../DELIVERY_PLAN.md`、`../../build/release/README.md` 及目标 profile 为准。
