# 应用内一键升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 「检查更新」对话框升级为真正的一键升级：检测公开 GitHub repo 最新版本 → 下载 deb + sha256 校验 → pkexec 特权安装 → 重启提示。

**Architecture:** 前端新增 `UpgradeController`（仿 SyncController/DeliveryController 状态机）；`CheckUpdateDialog` 全面改造（远程版本对比 + 状态机 + 一键升级按钮 + 进度）；网络用 `QNetworkAccessManager`；下载/校验/安装用 `QProcess` + `QCryptographicHash::Sha256`；安装经 `pkexec dpkg -i`。

**Tech Stack:** C++17 · Qt5 Widgets · QNetworkAccessManager · QProcess · QtTest(offscreen)

## Global Constraints

- **升级源**：公开 GitHub repo `PlutoKeating/Project.PIXIU`（匿名可达 `GET .../releases/latest`）。**前提：repo 转公开前完成安全审计**（已做——无真实机密；`pixiu.env` 示例口令将改占位符）。
- **安全铁律**：HTTPS + sha256 双校验（`QCryptographicHash`，防篡改）；安装经 `pkexec`（polkit 认证框，不绕过授权）；不存/不上传凭证；下载失败/校验失败中止并清理。
- **版本权威**：GitHub tag `vX.Y.Z` ↔ 包内 applicationVersion `X.Y.Z`（V-1 预检保证 tag 与三处版本源同步）。
- 文案 tr() 中文源文本；offscreen 测试；禁 push；单一逻辑一个提交；不引入新第三方依赖。

---

## Task U-1: 版本工具 + sha256 校验（无 UI，纯工具）

**Files:** Create `frontend/src/app/UpgradeUtils.h/.cpp`；Test `frontend/tests/t_upgrade_utils.cpp`

**Interfaces:**
- `QString pixiu::normalizeVersion(const QString &tag)`（去掉 `v` 前缀，`v0.1.6`→`0.1.6`）
- `int pixiu::compareVersions(const QString &a, const QString &b)`（`-1/0/1`；按点分段数字比较，处理不等长 `0.1.6` vs `0.1.6.1`——按段数补零或先段数）
- `QByteArray pixiu::sha256(const QByteArray &data)`（QCryptographicHash::Sha256 hex）
- `bool pixiu::verifySha256(const QString &filePath, const QString &expectedHex)`（读文件重算比对，大小写不敏感）
- GitHub API/asset 解析辅助：`struct ReleaseInfo { QString tag; QString debUrl; QString shaUrl; }`、`bool pixiu::parseRelease(const QByteArray &json, ReleaseInfo &out)`（解析 `tag_name` + 找 `pixiu_*.deb`/`.sha256` 的 `browser_download_url`）

**Covers:** [S2.1, S2.2]

- [ ] Step 1 失败测试：compareVersions（等/大/小/前缀/不等长）、normalizeVersion、verifySha256（真/假/文件不存在）、parseRelease（合法 JSON/缺字段/未知 asset）
- [ ] Step 2 运行失败
- [ ] Step 3 实现（纯函数，Qt + std，无网络）
- [ ] Step 4 绿
- [ ] Step 5 提交 `feat(frontend): version and sha256 upgrade utils`

---

## Task U-2: UpgradeController（状态机 + 网络/下载/校验/安装）

**Files:** Create `frontend/src/app/UpgradeController.h/.cpp`；Modify `frontend/CMakeLists.txt`（主目标 + 编译 PixiuApp.cpp 的目标源列表）；Test `frontend/tests/t_upgrade_controller.cpp`

**Interfaces:**
- `UpgradeController(QObject* parent)` — `void checkForUpdate()`、`void downloadAndInstall()`、`void cancel()`；信号 `checkStateChanged(State)`、`remoteVersionFound(const QString &version)`、`progressChanged(int percent)`、`upgradeFinished(bool success, const QString &message)`；`enum class State { Idle, Checking, Updatable, UpToDate, Downloading, Verifying, Installing, Success, Cancelled, Failed }`
- 网络：`QNetworkAccessManager` 拉 `GET https://api.github.com/repos/PlutoKeating/Project.PIXIU/releases/latest`；`parseRelease` 解析；`compareVersions(remote, applicationVersion) > 0` → Updatable
- 下载：`GET debUrl`（`QNetworkReply` 流式，进度信号）→ 存 `QStandardPaths::writableLocation(TempLocation) + "/pixiu-update.deb"`；再 `GET shaUrl` 或直接 fetch `.sha256` 内容 → `verifySha256(deb, expected)` → 通过才 Verifying→Installing
- 安装：`QProcess::start("pkexec", {"dpkg", "-i", debPath})`（pkexec 弹 polkit 认证框）；退出 0 → Success；126/127（polkit 取消）→ Cancelled；其他 → Failed（附错误摘要）
- **不自动重启**：Success 后发 `upgradeFinished(true, tr("升级成功，请手动重启应用以生效"))`
- 每次操作可 cancel：下载/安装中 cancel → 清理临时 deb + 停止 reply/process
- 依赖：仅 Qt（QNetworkAccessManager/QNetworkReply/QProcess/QStandardPaths/QCryptographicHash）

**Covers:** [S2.1, S2.2, S2.3]

- [ ] Step 1 失败测试（FakeNetwork 注入或用真实 QNetworkAccessManager 打本地假 server——仓库有 TCP 桩先例 t_contract_fixtures；UpgradeController 可注入 QNetworkAccessManager 供测试 mock；State 转移/版本比较/校验失败/安装成功/取消路径）
- [ ] Step 2 运行失败
- [ ] Step 3 实现
- [ ] Step 4 绿
- [ ] Step 5 提交 `feat(frontend): upgrade controller with check download verify install`

---

## Task U-3: CheckUpdateDialog 一键升级 UI

**Files:** Modify `frontend/src/widgets/CheckUpdateDialog.h/.cpp`；Modify `frontend/src/app/PixiuApp.cpp`（接线 UpgradeController + dialog）；Modify `frontend/CMakeLists.txt`（若 source 变化）；Test `frontend/tests/t_check_update_dialog.cpp`（或并入 t_app_navigation）

**Interfaces:**
- CheckUpdateDialog 改造：当前版本行 + **远程版本行**（remoteVersionLabel）+ 状态区（updateStatusLabel）+ 「检查更新」按钮（checkAgainButton）+ 「一键升级」按钮（upgradeButton，仅 Updatable 时 enabled）+ 进度条（updateProgressBar）+ 「知道了」关闭
- PixiuApp：`openSettings` 懒创建块内 connect——CheckUpdateDialog 需访问 UpgradeController（构造注入或信号桥接）；打开对话框时触发一次 `checkForUpdate()`
- objectName：`remoteVersionLabel`/`upgradeButton`/`checkAgainButton`/`updateStatusLabel`/`updateProgressBar`
- 安全提示：升级需系统授权（pkexec），保留记忆与配置；校验失败的「校验失败，已中止」文案

**Covers:** [S2.4, S4]

- [ ] Step 1 失败测试（对话框显示当前版本/远程版本对比/一键升级按钮 enabled 变化/状态流转文案/进度条）
- [ ] Step 2 运行失败
- [ ] Step 3 实现（PixiuApp 接线 + dialog 状态机映射 + 进度）
- [ ] Step 4 绿（`QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend --output-on-failure` → 33+ 全绿）
- [ ] Step 5 提交 `feat(frontend): one-click upgrade in check update dialog`

---

## Task U-4: i18n + 安全加固 + 双路径回归

**Files:** Modify `frontend/resources/i18n/pixiu_en_US.ts/.qm`；Modify `build/release/debian/pixiu.env`（示例口令改占位符）；Test 回归

- [ ] Step 1 i18n：lupdate/lrelease 收编新增文案（「检测到新版本 %1」「正在下载…%2%」「校验下载包…」「正在申请安装权限…」「升级成功，请手动重启应用」「校验失败，已中止」「无法连接更新服务器」「已取消」「检测更新已完成，当前已是最新版本」等），0 unfinished
- [ ] Step 2 pixiu.env 安全加固：`PIXIU_SYNC_KEY_PASSPHRASE` 改 `change-me-before-production` 占位符（保留注释）
- [ ] Step 3 双路径回归：`bash frontend/scripts/regression.sh`（OFF/ON + deb 校验；ON 低内存可能 OOM 用增量目录 -j1）
- [ ] Step 4 提交（i18n `chore` + pixiu.env `chore` 分开）
- [ ] Step 5 （主代理）转 public repo + 打 tag 发布

---

## 执行顺序
U-1 → U-2（依赖 U-1）→ U-3（依赖 U-2）→ U-4 收尾。每任务两阶段审查。转公开与发布由主代理在 U-4 后执行。
