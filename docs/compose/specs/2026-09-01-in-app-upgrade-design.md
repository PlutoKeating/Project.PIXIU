# 应用内一键升级 Design Spec

> 日期：2026-09-01 · 状态：功能基线已实现；最终发布加固未完成（2026-09-03 复核）
> 定位：把「检查更新」对话框从「仅提示」升级为**真正的一键升级**——检测远程最新版本 → 下载 .deb + sha256 → 校验 → pkexec 特权安装 → 重启应用。依托**转公开的 GitHub repo**（匿名可达 Releases）。
>
> 当前代码已落地 `UpgradeController`/`UpgradeUtils`/`CheckUpdateDialog`、架构资产选择、
> 流式校验和特权安装。本文 §S1 的“现状”是 2026-09-01 实施前历史；最终交付
> 还须按 `docs/DELIVERY_PLAN.md` 补独立签名、组件兼容、回滚、健康检查和受控重启。

## [S1] 背景与目标

- 实施前现状（历史）：CheckUpdateDialog 曾仅显示「当前版本 %1。请从官方渠道获取
  最新版本…」且无下载/安装能力；该缺口现已修复，不再作为当前状态。
- 决策（用户已拍板）：①升级源 = **公开 GitHub repo**（前端直接 HTTPS 拉 GitHub Releases latest）；②特权安装 = **pkexec**（systemd 策略代理，弹系统 polkit 认证框，麒麟 UKUI 支持——本机已探明 pkexec v124 + KylinOfflineUpgradeUmount/KylinSystemUpdater 等 polkit 策略存在）。
- 目标：设置→「检查更新」→ 对比远程版本与本地（applicationVersion）→ 新版可用时提示 → 点「一键升级」→ 下载+校验+安装。
- **安全铁律**：下载必须校验 sha256（与 release 的 .sha256 比对，防篡改/中间人——走 HTTPS + sha256 双重）；升级用 pkexec 弹认证框，不绕过授权；不保存/不上传任何凭证。转公开 repo 的代码需确认无敏感信息（.env/secrets 应已在 gitignore——发布前检查）。

## [S2] 升级链路（前端 QNetworkAccessManager + QProcess）

### [S2.1] 远程版本检测
- `GET https://api.github.com/repos/PlutoKeating/Project.PIXIU/releases/latest`（公开 repo，匿名可达）→ 解析 `tag_name`（如 `v0.1.6`）+ `assets`（按本机 Debian 架构严格找同版本 `pixiu_<ver>-1_<arch>.deb` 与同名 `.sha256`）。
- 版本比较：提取数字 `major.minor.patch`，与 `QCoreApplication::applicationVersion()` 比较——有新版本才标记可升级。
- 网络失败（离线/未公开/API 限制）→ 对话框显示「无法连接更新服务器」+ 重试按钮，不崩溃、不阻塞。

### [S2.2] 下载 + 校验
- 下载 deb 到临时目录（`QStandardPaths::TempLocation` 或 `~/.cache/pixiu/updates/`），流式（QNetworkReply 进度信号 → 进度条）。
- 下载 `.sha256` 文件（release 随包），以 1 MiB 分块重算 SHA-256，并同时
  校验清单中的资产文件名——摘要或文件名不一致均中止、删除并报
  「校验失败，已中止」，避免大包整包读入内存或交叉资产替换。
- 下载完成时校验通过后才进入安装步骤。

### [S2.3] 特权安装（pkexec）
- `QProcess::start("/usr/bin/pkexec", {"/usr/lib/pixiu/install-update",
  debPath, expectedSha256})`——pkexec 触发 polkit 认证框；特权 helper 先把用户
  下载复制到 root-only 临时文件并重新校验 SHA-256，再以非交互、
  保留现有 conffile 的参数交给 `/usr/bin/dpkg`，
  消除授权等待期间替换原文件的 TOCTOU 竞态，并保留退出状态与错误摘要。
- **postinst 兼容**：T24 已修复 venv 复用 + conffile 幂等追加，dpkg -i 增量升级保留记忆/配置/venv。
- 安装过程状态：对话框显示「正在升级（需要授权）… pkexec 认证框正确弹出时用户输入密码」；退出码 0 → 「升级成功，将重启应用」→ 关闭当前应用，提示用户重启（或自动重启——自动重启需谨慎，倾向提示手动重启，说明理由）。
- **失败路径**：pkexec 被取消（退出码 126/127）→ 「已取消，升级未执行」；dpkg 报错 → 显示错误摘要不崩溃。
- **取消边界**：下载/校验可取消并清理唯一临时文件；进入安装后禁用取消与关闭，
  应用退出也不杀死 dpkg，避免软件包数据库处于半配置状态。

### [S2.4] UI（CheckUpdateDialog 改造）
- 控件：当前版本行 + **远程最新版本行**（对比） + 状态区（检测中/可升级/已是最新/校验中/安装中/结果） + 「检查更新」按钮 + 「一键升级」按钮（仅可升级时 enabled）+ 「知道了」关闭。
- 安全提示文案：升级需系统授权（pkexec），升级保留记忆与配置。
- objectName 语义化（供测试）：`remoteVersionLabel`/`upgradeButton`/`checkAgainButton`/`updateStatusLabel`。

## [S3] 契约与既有设施
- **依赖**：QNetworkAccessManager（HttpBackendTransport 已用先例）、QProcess（FloatingBall/ThemeService 先例）、QStandardPaths、std 哈希/`QCryptographicHash`（sha256 校验——Qt 内置 QCryptographicHash::Sha256，无需新依赖）。
- **不引入** curl/系统工具于生产路径（QNetworkAccessManager 原生 HTTP）；sha256 用 `QCryptographicHash`（纯 Qt）或调用 `sha256sum`（deb 校验用哈希库更稳，选 QCryptographicHash，说明理由）。
- **BackendTransport 不动**：升级是前端独立设施（不经后端 HTTP 网关——那会多一跳且后端是 Python 服务无 GUI 提权能力），走 `UpgradeController`（仿 SyncController/DeliveryController 状态机模式）。

## [S4] 测试策略
- 前端 ctest（offscreen）：
  - 版本解析/比较（`compareVersions`：1.2.3 vs 1.2.4、相等、前缀差异）;
  - sha256 校验（假 hash 一致/不一致）;
  - CheckUpdateDialog 状态机（检测中→可升级→install 中→成功/取消/失败）;
  - URL 构造（latest API 与 asset URL 解析——用假 JSON fixture）。
- i18n：新增文案 tr() 中文源文本（如「检测到新版本 %1」「下载中…%2%」「正在申请安装权限…」「升级成功」），lupdate/lrelease 0 unfinished。
- 回归：前端 OFF/ON ctest + regression.sh；真机用假 manifest 或真实 repo 冒烟（公开后）。

## [S5] 范围边界（不做）
- 不做自动重启（提示手动重启，避免安装中断会话/数据未保存）；
- 不做多通道/镜像源；不做 beta/预发布通道（只 latest 稳定）；
- 不做后端参与（后端无 GUI/polkit，升级是前端职责）；
- 不做离线包管理/缓存清理策略（升级后临时 deb 删除）。

## [S6] 风险与开放点
- **转公开 repo 前必须审计**：git grep secrets/credentials/.env/私钥——确保公开后无敏感泄露（发布前扫描）。
- GitHub API 匿名限流（60 req/h）——单用户单次检测足够，可接受；失败走「无法连接」友好提示。
- pkexec 需 polkit 规则允许 pixiu 调 `dpkg -i`——麒麟默认 polkit 是否放行？若被拒（认证框报「未授权」），需提供 .policy 规则或降级提示（记录：真机验证，失败则提示用户手动 `sudo dpkg -i` 并给出命令——兜底不阻塞）。
- 下载取消/断网中途——清理唯一临时文件，状态回「已取消/失败」，可重试；
  GitHub 每次 30x 重定向目标均重新执行 HTTPS + 精确 host 白名单检查。
- 版本号权威：GitHub tag（v0.1.6）与包内 applicationVersion（0.1.6）必须一致——V-1 发布预检已保证 tag 与三处版本源同步，升级后 applicationVersion 随新安装更新。
