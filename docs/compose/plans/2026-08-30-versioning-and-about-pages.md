# 版本管理一致性 + 关于/更新/条款/隐私页面 Implementation Plan

本文按当前代码维护；既有章节名称保留用于引用，不代表旧窗口或旧方案仍在使用。
唯一桌面入口为 openKylin Agent 宿主，设置管理由 SettingsWorkspace 提供。
完整交付与未完成验收以 docs/UNIFIED_FRONTEND_PLAN.md 和 docs/DELIVERY_PLAN.md 为准。

**Goal:** 根 VERSION 单一输入、受验证的整包升级，以及正式宿主的信息与更新入口。

**Architecture:** SettingsWorkspace 直接持有 InfoDialog、CheckUpdateDialog 和
UpgradeController。ProductInformation 提供关于、数据联网、许可证正文。
不存在旧 SettingsDialog → PixiuApp 接线；禁止恢复第二个应用装配层。

**Tech Stack:** C++17、Qt5 Widgets/Network、CMake，以及既有整包发布脚本。

## Global Constraints

- 前端实现限定 frontend/，发布清单和脚本属于整包交付层；不修改上游原件。
- 产品版本从根 VERSION 派生，不能在文档或另一份 control 中维持平行版本源。
- .deb.sha256 是摘要，不等于签名；在线安装需沿用当前独立签名验证链。
- 用户数据、配置与同步身份不属于旧界面清理范围。
- 页面只描述实际能力：模型调用可能联网，关闭采集不删除记忆，逻辑遗忘不等于所有副本物理擦除。
- 推送与发布遵循当前 AGENTS.md 及用户当次授权，不沿用旧计划中的绝对禁止或默认授权。
- 通用 offscreen 测试、SDK 替身测试和 V11 真机结果分别报告。

---

## Task V-1: 版本一致性（CMake 注入 + 三处同步 + 发布预检）

原“三处同步”已由唯一输入与派生校验替代，保留标题但不执行旧流程。

**Files:**

- VERSION：产品版本输入。
- frontend/management/CMakeLists.txt：正式管理库版本宏。
- frontend/CMakeLists.txt：仅保留回归目标，无独立产品 main 或安装目标。
- build/release/scripts/build-deb.sh：派生关系预检与整包构建。
- build/release/scripts/generate-release-manifest.py：包内发布清单生成。
- frontend/tests/test-version-source.sh：根回归版本、退役源码和旧目标检查。

**验证与剩余工作：**

- 已实现单源派生及漂移拒绝；不得把单个前端测试描述为完整发布门。
- 版本递增后需重新通过整包发布预检、通用 CI、V11 原生门，并由标签自动发布。
- 安装后的版本展示、签名失败、升级失败、回滚及用户数据保留仍须完整 GUI 实证。

---

## Task V-2: InfoDialog + CheckUpdateDialog + SettingsDialog 四入口

旧 SettingsDialog 已删除，以下为正式替代关系。

**Files:**

- frontend/management/SettingsWorkspace.cpp：应用与升级、采集与隐私、服务与能力三个页签。
- frontend/src/widgets/InfoDialog.h/.cpp：只读纯文本说明页。
- frontend/src/widgets/CheckUpdateDialog.h/.cpp：实际升级状态与操作。
- frontend/src/app/ProductInformation.h：事实性正文。
- frontend/src/app/UpgradeController.h/.cpp：检查、下载、验证、授权安装及受控重启。
- frontend/tests/t_product_dialogs.cpp：保留组件基础行为，根回归和正式管理测试均编译。
- frontend/management/tests/t_memory_workspace.cpp：正式信息页入口和宿主归属检查。
- frontend/tests/t_check_update_dialog.cpp：更新状态与受控重启回归。

**Interfaces:**

- productUpdates → CheckUpdateDialog::showAndCheck。
- productAbout / productDataUse / productLicenses → 各自宿主所属 InfoDialog。
- InfoDialog(title, body, parent) 使用 setPlainText，不解释 HTML。
- 更新成功后的重启先调用 HostCloseGuard；拒绝退出时不调度重启。
- 无 UpgradeController 的独立对话框禁用升级，不伪造已安装或可升级状态。

**验证与剩余工作：**

- product_dialogs 检查纯文本/只读、关闭不影响宿主、版本显示和无控制器禁用升级。
- 快捷键已在正式设置中编辑和持久化，验证见统一计划 U02。
- 完整原生升级、无障碍和布局矩阵仍须验收，不能用组件测试替代。

---

## Task V-3: i18n 收编 + 双路径回归

**Files:**

- frontend/resources/i18n/pixiu_en_US.ts/.qm：保留组件资源；退役 SettingsDialog 上下文已移除。
- frontend/tests/t_i18n.cpp：保留资源的加载及译文检查。
- frontend/management/CMakeLists.txt：正式组件回归入口。

**验证与剩余工作：**

- 修改 TS 后以 lrelease 同步 QM，检查实际保留文案，不以译文数量声明语言全覆盖。
- 正式管理模块完整英文资源与语言切换尚未完成，不能迁入无实际资源支持的选择框。
- frontend/scripts/regression.sh 按所选画像运行，不把单次执行描述为同时完成 OFF/ON。
- V11 SDK=ON 产品验证与通用 SDK=OFF 检查分开，真实安装升级不由 offscreen 自动证明。
- 升级测试启动器已在 Qt 初始化前自动建立进程私有临时目录；两项哨兵回归
  验证不会删除外层其他进程安装包，跨套件执行不再依赖手工分配 TMPDIR。

---

## 执行顺序

确认版本派生与正式页面归属 → 维护当前组件及有效测试 → 补齐语言与原生状态矩阵
→ 整包安装升级验收 → 自动化发布。旧窗口删除与有效组件测试保留同步进行。
