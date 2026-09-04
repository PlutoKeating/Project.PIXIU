# D-04 银河麒麟 V11 部署指南工作稿

- 适用版本：0.1.7 功能基线；最终候选号待定
- 状态：当前审阅候选 Kylin V11 strict 单包已完成构建、覆盖安装、事务式用户服务/gateway 迁移、
  双 SDK 产品生命周期并返回 compliant、`contest_ready=true`；最终图形安装、模型
  Agent、三设备及冻结 commit 的 A-02 证据仍未闭环

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
systemctl --user status pixiu-backend.service
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

严格激活会先核对现有用户 unit 是否确为固定 Gateway 启动形式，再进行任何 profile
修改；未知命令、额外启动钩子或符号链接均拒绝迁移。被迁移 unit 按内容 SHA-256 保留
独立恢复副本，Provider、Agent `.env`、Runtime 配置和 unit 同处一次激活事务中；配置
拒绝或 Gateway 启动失败时恢复原快照，不显示安装成功。

包构建会把同一个 `PIXIU_VERSION` 写入 `/usr/share/pixiu/VERSION`，并经 systemd 的
`PIXIU_PRODUCT_VERSION` 注入后端。安装后先检查 `GET /version` 的产品/API/schema，
再检查 `GET /health` 的数据库就绪状态，最后以 `/capabilities` 判定 V11 双 SDK；
三者用途不可互相替代。Provider 初始化会拒绝混装版本、API 漂移、未就绪后端或超出
已验证 0.9.x 范围的宿主。

安装包同时提供 `/usr/share/pixiu/release-manifest.json`。交付审查应核对其中的
Debian 版本、Git commit、构建画像、API/schema/provider 和四个上游源码钉住值；
`source_tree_clean` 必须为 `true`。`sdk_sources` 是构建所依据的官方源码，不是目标机
实际库版本；后者仍须另存包管理器输出并与 `/capabilities` 的真实 runtime 对照。

发布介质中每个架构应同时存在 `.deb`、`.deb.sha256`、`.deb.sha256.sig`、
`.assets.json`、`.assets.json.sha256`、`.assets.json.sha256.sig`。先验证资产清单
自身的摘要与 Ed25519 签名，再按 JSON 中的文件名、大小和 SHA-256 核对前三个资产；
清单不包含自身摘要，避免自引用。

V11 双 SDK 候选包使用 `kylin-v11-native-x86_64` profile。该画像令
`PIXIU_KYSDK=ON` 同时约束桌面 KylinSDK 和后端 Embedding/Vector 原生扩展；构建、
安装及真实写入/检索由独立 `pixiu-kylin-v11-native` 工作流执行并输出脱敏证据。
其 `preinst` 会在文件解包前检查 V11 与架构；双 SDK 由 Debian 依赖解析，并由 strict
后端启动预检验证实际可用性。首次以桌面用户启动时，Provider 激活器再从该用户环境
检查 `kylin-agent` 与 runtime，要求 `--version` 成功且唯一匹配 0.9.x；严格包激活
失败即停止启动，generic/portable 才允许独立控制台降级。模式可从
`/usr/share/pixiu/release-manifest.json` 的 `build.install_strict` 判别。

严格画像还要求系统已通过“设置 → AI 模块管理”安装并启用官方 AI 子系统。不要把
整套 AI 子系统作为 PIXIU 包的整体依赖：它包含大量无关模型；最终 control 只保留
经同版实测确认的最小 SDK/runtime 包。当前官方 runtime 的 Unix socket 按 UID 隔离，
历史系统级 `pixiu-backend.service` 使用专用账户，不能直接访问桌面用户会话 socket。
当前安装结构已改为 systemd user service，并把配置、数据和状态置于当前用户 XDG
目录；启动器要求 unit 的 MainPID 属于当前 UID，并核对 loopback `/version` 的组件与
包版本，拒绝端口伪服务。旧数据迁移、升级事务和 strict user-service 复验现已完成；
在完整 Agent 与同版正式 A-02 归档完成前，H-02/H-03 只能登记“部分通过”，不得声明
最终通过。

旧系统账户版存在 `/var/lib/pixiu/pixiu.db` 时，首次用户启动会请求系统授权执行一次性
迁移。工具拒绝非空目标，使用 SQLite backup API 并在提交前后核对 integrity、schema、
全表逻辑计数和同步身份摘要；Vector 数据及去除旧绝对路径后的配置一并复制。中断由
journal 恢复，成功标记明确记录源数据仍保留，不在安装脚本中直接删除。
提交 `c643b1b699ba34650fdf913dd58f0cccd8168191` 的洁净 strict amd64 包已再次完成构建、
安装和失败关闭复验：保留 portable 配置时服务健康，切换 strict 后稳定暴露上述用户
会话边界，恢复配置后服务、配置和数据库摘要保持。后续提交 `1751dd6` 已完成该边界：
目标 V11 安装后旧数据迁移校验通过，user unit active，MainPID 属于桌面用户，
`/version` 返回产品 `0.1.7`/schema 12，`/capabilities` 返回两个 native runtime
compliant 与 `contest_ready=true`。该新证据仍不是完整 Agent 或最终安装矩阵证据。
Vector Engine 无需配置 TCP host/port：生产使用系统 SDK 的 `ConnectParam(appId)`
本地连接。旧配置中可能残留的 `PIXIU_VECTOR_HOST`/`PIXIU_VECTOR_PORT` 已被忽略；
新装模板不再生成它们，`PIXIU_VECTOR_APP_ID` 仍用于隔离应用数据库。
实际数据库文件由 `PIXIU_VECTOR_DB_PATH` 指定；strict 启动必须完成 `LoadDBFile`，
失败时服务拒绝就绪，不得等到第一个记忆写入才暴露错误。

## 升级、卸载与恢复

设置页可检查并一键下载安装现有 PIXIU 包。特权安装器会先验证包名、版本和架构，
安装后核对实际 dpkg 版本，并轮询 `/version`、`/health` 和包内 Provider manifest；
产品/API/schema/数据库/Provider 任一不一致都返回健康失败，GUI 不报告成功。最终版
发布流水线现生成 Ed25519 `.sha256.sig`，helper 以包内固定公钥在 dpkg 前验签；
双架构 CI 资产及 Kylin V11 有效/篡改签名已验证；临时密钥和两个真实 `.deb` 的
旧钥到新钥轮换演练也已通过。生产轮换仍必须遵循相同的双版本顺序并保留发布记录。
另需完整兼容矩阵。
helper 会通过 `PKEXEC_UID` 锁定发起升级的桌面用户，验证 GUI 传入的实际 XDG 目录
位于该用户 home 且属主一致，再用 `dpkg-repack` 重建当前包、停止该用户服务并以
SQLite backup API 保存一致数据库和配置；安装或健康失败时恢复旧包、数据和服务。恢复成功/失败会
显示不同提示。提交 `ca35117` 的 CI run `33770727108` 已在 amd64/arm64 验证注入恢复；
Kylin V11 amd64 又完成 `0.1.7-4` → 签名 `0.1.7-1` → 注入失败 → `0.1.7-4`
的跨 revision 恢复，退出码为 5，配置、核心数据逻辑摘要和服务保持。升级必须保留记忆
数据库、配置和同步身份。当前源码的前端 38/38 测试和 helper/证据契约已通过；最终
候选仍须随完整安装矩阵重验。
安装健康成功后，GUI 的“立即重启”调用无特权 `restart-client`；它验证旧进程 PID，
等待客户端释放单实例资源后启动 `/usr/bin/pixiu`。只有升级 Success 状态可进入该路径，
调度失败时保留窗口并提示手动重新打开。最终 V11 图形重启后仍须复核版本和全链路。
默认配置以 `/usr/share/pixiu/pixiu.env.default` 模板随包；桌面用户首次运行
`pixiu` 时在 `$XDG_CONFIG_HOME/pixiu/pixiu.env` 创建 0600 配置并生成随机同步口令。
该配置不属于 dpkg conffile，系统安装阶段不会冒充或扫描用户会话。
卸载与 purge 的数据语义须在最终版明确区分，并在全新机、重装、升级失败上取证。

2026-09-03 以提交 `30e0d64` 在 Kylin V11 amd64 目标环境执行兼容画像：前端
ctest 37/37，通过并打入完整 cp312 离线 wheels；`0.1.7-3` 升级到测试 revision
`0.1.7-4` 后服务 active，配置摘要与核心数据逻辑计数保持一致。再由包内特权 helper
完成同版重装，安装健康返回产品 `0.1.7`、schema 12、数据库 ready。能力端点同时
如实返回两个 SDK runtime 为 portable、`contest_ready=false`；该记录不替代原生验收。

故障排查入口、日志位置、严格/降级差异和最终依赖包名以
`../DELIVERY_PLAN.md`、`../../build/release/README.md` 及目标 profile 为准。
