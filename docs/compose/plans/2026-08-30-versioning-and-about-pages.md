# 版本管理一致性 + 关于/更新/条款/隐私页面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落实版本管理核心宗旨（三处版本源一致 + 发布预检 + sha256 校验一致 + 旧版可增量升级），并为设置界面补齐「检查更新」「关于 PIXIU」「服务条款」「隐私政策」四入口与对应页面。

**Architecture:** 版本号由 CMake 注入（`PIXIU_VERSION` 编译宏）替代 main.cpp 硬编码根治漂移；build-deb.sh 发布预检三处版本一致；新建通用 InfoDialog（About/T&C/Privacy 三页复用）+ CheckUpdateDialog（当前版本 + 升级指引，不做在线检查）；SettingsDialog 四按钮 → 四信号 → PixiuApp 懒创建接线。

**Tech Stack:** C++17 · Qt5 Widgets · CMake | shell（发布脚本预检）

## Global Constraints

- **模块边界**：Plan-F 只改 `frontend/`；发布脚本预检改 `build/release/scripts/build-deb.sh`（版本一致性校验，属发布基础设施）。
- **版本管理宗旨（用户核心规则）**：①三处版本源（main.cpp/CMakeLists/functions.sh）同步增量；②发布产物 .deb + .sha256 一致；③旧版/内测用户可 dpkg -i 直接增量升级（postinst venv 复用 + conffile 幂等追加，T24 已落地——本批次不重复，文档注明）。
- **不做**：真实在线更新（OTA）、GPG 签名、后端改动、新第三方依赖。
- **文案语境**：参赛作品（麒麟 OS Agent 记忆优化赛题），参照 docs/OriginProblemDescription.md；少量（每页 3-6 句）；全部 tr() 中文源文本。
- 提交前缀 `feat(frontend)/fix(frontend)/chore(frontend)/test(frontend)`；禁止 push；offscreen 测试。

---

## Task V-1: 版本一致性（CMake 注入 + 三处同步 + 发布预检）

**Covers:** [S2.1, S2.2]

**Files:**
- Modify: `frontend/CMakeLists.txt`（project VERSION 0.1.1；target_compile_definitions 注入 `PIXIU_VERSION="0.1.1"`）
- Modify: `frontend/src/main.cpp:24`（`setApplicationVersion` 改用宏 `QStringLiteral(PIXIU_VERSION)`，删除硬编码）
- Modify: `build/release/scripts/build-deb.sh`（发布前预检：grep main.cpp/CMakeLists/functions.sh 三处版本号一致，不一致 exit 1 报错）
- Verify: `build/release/scripts/functions.sh` 确认 0.1.1（T24 已 bump）

- [ ] **Step 1: 写失败测试**（版本注入生效）
  构建后 `pixiu-frontend --version` 或现有 t_app 断言 `QCoreApplication::applicationVersion() == "0.1.1"`（grep 现有测试是否有版本断言；无则加 t_app_settings 或用 CMake configure 期断言）。
- [ ] **Step 2: 运行验证失败**（当前 main.cpp 硬编码 0.1.0 ≠ 0.1.1）
- [ ] **Step 3: 实现**（CMakeLists project VERSION + compile definition；main.cpp 用宏；build-deb.sh 预检函数）
- [ ] **Step 4: 运行验证通过**（构建 + ctest；预检脚本测三处一致通过/不一致报错——shell 单测或手动）
- [ ] **Step 5: 提交** `git commit -m "fix(frontend): inject version from cmake and guard release consistency"`

---

## Task V-2: InfoDialog + CheckUpdateDialog + SettingsDialog 四入口

**Covers:** [S3.1, S3.2, S3.3, S4]

**Files:**
- Create: `frontend/src/widgets/InfoDialog.h/.cpp`（通用只读文档对话框：title + QTextBrowser + 关闭按钮；objectName infoDialog/infoTextBrowser）
- Create: `frontend/src/widgets/CheckUpdateDialog.h/.cpp`（当前版本 + 升级指引文案；objectName checkUpdateDialog）
- Modify: `frontend/src/widgets/SettingsDialog.h/.cpp`（四按钮：checkUpdateButton/aboutUsButton/termsButton/privacyButton；四信号：checkUpdateRequested/aboutUsRequested/termsRequested/privacyRequested；布局：versionLabel 后新增按钮行）
- Modify: `frontend/src/app/PixiuApp.h/.cpp`（懒创建 InfoDialog/CheckUpdateDialog；connect 四信号 → 各自打开对应页面——About/T&C/Privacy 传不同文案）
- Modify: `frontend/CMakeLists.txt`（主目标 + t_app_navigation/t_window_restore 加两对新源文件——编译 PixiuApp.cpp 的目标三处同步，批次②教训）
- Test: `frontend/tests/t_settings_dialog.cpp`（若存在）或 t_memory_panel 扩展 + `frontend/tests/t_app_navigation.cpp`

**Interfaces:**
- Consumes: `QCoreApplication::applicationVersion()`、`ui::UiTokens`、既有 PixiuApp openSettings 懒创建接线模式
- Produces: `InfoDialog(title, body, parent)`（showAndFocus 或 show）；`CheckUpdateDialog(parent)`；SettingsDialog 四信号；PixiuApp `showAboutUs()/showTerms()/showPrivacy()/showCheckUpdate()`（懒创建各自实例或统一 InfoDialog 复用——实现时选一说明）

- [ ] **Step 1: 写失败测试**（四按钮存在且 emit 对应信号；InfoDialog 渲染标题与正文关键词；更新对话框显示版本；t_app_navigation 点按钮 → 对话框可见）
- [ ] **Step 2: 运行验证失败**（ctest 红）
- [ ] **Step 3: 实现**（InfoDialog/CheckUpdateDialog + SettingsDialog 四按钮四信号 + PixiuApp 接线 + CMake 三目标同步）
- [ ] **Step 4: 运行验证通过**（`QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend --output-on-failure` → 32+ 绿）
- [ ] **Step 5: 提交** `git commit -m "feat(frontend): add about, terms, privacy and update entries"`

---

## Task V-3: i18n 收编 + 双路径回归

**Covers:** [S5, S7]

**Files:**
- Modify: `frontend/resources/i18n/pixiu_en_US.ts/.qm`（lupdate/lrelease：四按钮 + 三页文案 + 更新对话框文案）
- Test: 回归

- [ ] **Step 1: lupdate/lrelease**（cd frontend/resources/i18n && lupdate ../../src ../../tests -no-obsolete -locations none -ts pixiu_en_US.ts；补英文译文至 0 unfinished；lrelease）
- [ ] **Step 2: 全量双路径回归**：`bash frontend/scripts/regression.sh`（OFF/ON + deb 校验——注意本机低内存 ON 构建若 OOM 用增量目录 -j1）
- [ ] **Step 3: 提交** `git commit -m "chore(frontend): regenerate i18n resources for about and update pages"`

---

## 执行顺序

V-1 → V-2（依赖版本宏）→ V-3 收尾。每任务独立提交供两阶段审查。
