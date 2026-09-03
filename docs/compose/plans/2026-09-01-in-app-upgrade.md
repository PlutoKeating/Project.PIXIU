# 应用内一键升级 Implementation Plan

> 状态更新（2026-09-03）：U-1～U-4 与 U-5 已勾选项均已由当前代码/测试实现；
> 原计划未及时勾选的方框不是当前缺口。最终发布仍缺 U-5 真机门禁，以及
> `docs/DELIVERY_PLAN.md` 新增的签名、兼容矩阵、回滚、健康检查和受控重启。

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 「检查更新」对话框升级为真正的一键升级：检测公开 GitHub repo 最新版本 → 下载 deb + sha256 校验 → pkexec 特权安装 → 重启提示。

**Architecture:** 前端新增 `UpgradeController`（仿 SyncController/DeliveryController 状态机）；`CheckUpdateDialog` 全面改造（远程版本对比 + 状态机 + 一键升级按钮 + 进度）；网络用 `QNetworkAccessManager`；下载/校验/安装用 `QProcess` + `QCryptographicHash::Sha256`；安装经 `pkexec` 调用 root-only 副本二次校验 helper，再执行 `dpkg -i`。

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
- `QString ui::normalizeVersion(...)` / `int ui::compareVersions(...)`
- `QByteArray ui::sha256Hex(...)`
- `bool ui::verifySha256(...)`（1 MiB 分块重算，并绑定清单资产文件名）
- `QString ui::debianArchitecture()` + `parseRelease(..., architecture)`：严格选择
  tag 对应的 amd64/arm64 `.deb` 与同名 `.sha256`

**Covers:** [S2.1, S2.2]

- [x] Step 1 失败测试：compareVersions（等/大/小/前缀/不等长）、normalizeVersion、verifySha256（真/假/文件不存在）、parseRelease（合法 JSON/缺字段/未知 asset）
- [x] Step 2 运行失败
- [x] Step 3 实现（纯函数，Qt + std，无网络）
- [x] Step 4 绿
- [x] Step 5 提交 `feat(frontend): version and sha256 upgrade utils`

---

## Task U-2: UpgradeController（状态机 + 网络/下载/校验/安装）

**Files:** Create `frontend/src/app/UpgradeController.h/.cpp`；Modify `frontend/CMakeLists.txt`（主目标 + 编译 PixiuApp.cpp 的目标源列表）；Test `frontend/tests/t_upgrade_controller.cpp`

**Interfaces:**
- `UpgradeController(QObject* parent)` — `void checkForUpdate()`、`void downloadAndInstall()`、`void cancel()`；信号 `stateChanged(State)`、`remoteVersionFound(const QString &version)`、`progressChanged(int percent)`、`upgradeFinished(bool success, const QString &message)`；`enum class State { Idle, Checking, Updatable, UpToDate, Downloading, Verifying, Installing, Success, Cancelled, Failed }`
- 网络：`QNetworkAccessManager` 拉 `GET https://api.github.com/repos/PlutoKeating/Project.PIXIU/releases/latest`；`parseRelease` 解析；`compareVersions(remote, applicationVersion) > 0` → Updatable
- 下载：流式写入唯一 `pixiu-update-XXXXXX.deb`，下载和每次重定向均验证
  来源；再获取 `.sha256` 并流式校验
- 安装：`QProcess::start("/usr/bin/pkexec", {"/usr/lib/pixiu/install-update",
  debPath, expectedSha256})`；helper 复制为 root-only 临时文件并二次校验后才调用
  非交互执行 `dpkg --force-confdef --force-confold -i`；退出 0 → Success；
  126/127 → Cancelled；启动失败/其他退出 → Failed
- **不自动重启**：Success 后发 `upgradeFinished(true, tr("升级成功，请手动重启应用以生效"))`
- 仅下载/校验可 cancel；安装开始后禁止强制取消，避免中断 dpkg
- 依赖：仅 Qt（QNetworkAccessManager/QNetworkReply/QProcess/QStandardPaths/QCryptographicHash）

**Covers:** [S2.1, S2.2, S2.3]

- [x] Step 1 失败测试（FakeNetwork 注入或用真实 QNetworkAccessManager 打本地假 server——仓库有 TCP 桩先例 t_contract_fixtures；UpgradeController 可注入 QNetworkAccessManager 供测试 mock；State 转移/版本比较/校验失败/安装成功/取消路径）
- [x] Step 2 运行失败
- [x] Step 3 实现
- [x] Step 4 绿
- [x] Step 5 提交 `feat(frontend): upgrade controller with check download verify install`

---

## Task U-3: CheckUpdateDialog 一键升级 UI

**Files:** Modify `frontend/src/widgets/CheckUpdateDialog.h/.cpp`；Modify `frontend/src/app/PixiuApp.cpp`（接线 UpgradeController + dialog）；Modify `frontend/CMakeLists.txt`（若 source 变化）；Test `frontend/tests/t_check_update_dialog.cpp`（或并入 t_app_navigation）

**Interfaces:**
- CheckUpdateDialog 改造：当前版本行 + **远程版本行**（remoteVersionLabel）+ 状态区（updateStatusLabel）+ 「检查更新」按钮（checkAgainButton）+ 「一键升级」按钮（upgradeButton，仅 Updatable 时 enabled）+ 进度条（updateProgressBar）+ 「知道了」关闭
- PixiuApp：`openSettings` 懒创建块内 connect——CheckUpdateDialog 需访问 UpgradeController（构造注入或信号桥接）；打开对话框时触发一次 `checkForUpdate()`
- objectName：`remoteVersionLabel`/`upgradeButton`/`checkAgainButton`/`updateStatusLabel`/`updateProgressBar`
- 安全提示：升级需系统授权（pkexec），保留记忆与配置；校验失败的「校验失败，已中止」文案

**Covers:** [S2.4, S4]

- [x] Step 1 失败测试（对话框显示当前版本/远程版本对比/一键升级按钮 enabled 变化/状态流转文案/进度条）
- [x] Step 2 运行失败
- [x] Step 3 实现（PixiuApp 接线 + dialog 状态机映射 + 进度）
- [x] Step 4 绿（`QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend --output-on-failure` → 33+ 全绿）
- [x] Step 5 提交 `feat(frontend): one-click upgrade in check update dialog`

---

## Task U-4: i18n + 安全加固 + 双路径回归

**Files:** Modify `frontend/resources/i18n/pixiu_en_US.ts/.qm`；Modify `build/release/debian/pixiu.env`（示例口令改占位符）；Test 回归

- [x] Step 1 i18n：lupdate/lrelease 收编新增文案（「检测到新版本 %1」「正在下载…%2%」「校验下载包…」「正在申请安装权限…」「升级成功，请手动重启应用」「校验失败，已中止」「无法连接更新服务器」「已取消」「检测更新已完成，当前已是最新版本」等），0 unfinished
- [x] Step 2 pixiu.env 安全加固：`PIXIU_SYNC_KEY_PASSPHRASE` 改 `change-me-before-production` 占位符（保留注释）
- [x] Step 3 双路径回归：`bash frontend/scripts/regression.sh`（OFF/ON + deb 校验；ON 低内存可能 OOM 用增量目录 -j1）
- [x] Step 4 提交（i18n `chore` + pixiu.env `chore` 分开）
- [x] Step 5 （主代理）转 public repo + 打 tag 发布

---

## Task U-5: 0.1.6 发布前加固

- [x] 公开占位口令不再阻断核心 API 启动；安装时生成每机随机口令
- [x] 旧默认口令对应的 Ed25519 私钥原地重加密，保留设备身份与配对关系
- [x] 配置权限收紧为 `root:pixiu 0640`，包声明 `pkexec` 运行依赖
- [x] SHA-256 改分块读取并绑定资产名；严格匹配 tag + Debian 架构
- [x] 30x 目标重新校验，唯一临时文件，安装启动失败显式处理
- [x] 元数据/校验/DEB 大小设限；特权边界复制并二次校验，消除 TOCTOU
- [x] 安装中禁用取消/关闭，避免破坏 dpkg 状态
- [x] Release 工作流原生构建 amd64 + arm64 资产
- [ ] Debian 通用画像完整门禁与麒麟 V11 真机增量升级验收

---

## 执行顺序
U-1 → U-2（依赖 U-1）→ U-3（依赖 U-2）→ U-4 → U-5 收尾。仓库公开由用户执行；tag、远端 Release 与真机验收在公开后执行。
