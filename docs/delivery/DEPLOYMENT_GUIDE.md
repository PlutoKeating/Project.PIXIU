# D-04 银河麒麟 V11 部署指南工作稿

- 适用版本：0.1.7 功能基线；最终候选号待定
- 状态：Kylin V11 portable 包构建/跨 revision 安装/健康检查已通过；真实宿主和
  双 SDK 最终安装尚未闭环

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
发布流水线现生成 Ed25519 `.sha256.sig`，helper 以包内固定公钥在 dpkg 前验签；
双架构 CI 资产及 Kylin V11 有效/篡改签名已验证，轮换演练仍待取证。另需完整兼容矩阵、可信安装前备份/自动回滚和
受控前端重启。helper 会在安装前用 `dpkg-repack` 重建当前包、停服并以 SQLite backup
API 保存一致数据库和配置；安装或健康失败时恢复旧包、数据和服务。恢复成功/失败会
显示不同提示；该路径的正式故障注入证据仍待补。升级必须保留记忆数据库、配置和同步身份。
默认配置以 `/usr/share/pixiu/pixiu.env.default` 模板随包，`postinst` 仅在首次安装
创建 `/etc/pixiu/pixiu.env`；后者不属于 dpkg conffile，升级保留并幂等迁移，避免
每机随机口令导致非交互安装弹出配置冲突。
卸载与 purge 的数据语义须在最终版明确区分，并在全新机、重装、升级失败上取证。

2026-09-03 以提交 `30e0d64` 在 Kylin V11 amd64 目标环境执行兼容画像：前端
ctest 37/37，通过并打入完整 cp312 离线 wheels；`0.1.7-3` 升级到测试 revision
`0.1.7-4` 后服务 active，配置摘要与核心数据逻辑计数保持一致。再由包内特权 helper
完成同版重装，安装健康返回产品 `0.1.7`、schema 12、数据库 ready。能力端点同时
如实返回两个 SDK runtime 为 portable、`contest_ready=false`；该记录不替代原生验收。

故障排查入口、日志位置、严格/降级差异和最终依赖包名以
`../DELIVERY_PLAN.md`、`../../build/release/README.md` 及目标 profile 为准。
