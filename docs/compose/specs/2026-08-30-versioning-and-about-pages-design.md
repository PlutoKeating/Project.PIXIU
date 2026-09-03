# 版本管理宗旨落地 + 关于/更新/条款/隐私页面 Design Spec

> 日期：2026-08-30 · 状态：已实现并被在线一键升级方案扩展（2026-09-03 复核）
> 定位：落实用户定义的版本管理核心宗旨（严格版本增量 + 摘要校验一致 + 旧版可增量升级），并为应用补充更新入口与 About Us / Terms & Conditions / Privacy 页面。
>
> 本文保留最初设计过程。当前版本已统一为 0.1.7，关于/条款/隐私和在线升级均已
> 实现；在线流程以 `2026-09-01-in-app-upgrade-design.md` 为准，最终签名、回滚和
> 兼容门禁以 `docs/DELIVERY_PLAN.md` 为准。

## [S1] 背景与目标

- 用户核心宗旨：每次新发布必须**版本增量更新**（frontend/src/main.cpp 的 `setApplicationVersion`、frontend/CMakeLists.txt 的 `project VERSION`、build/release/scripts/functions.sh 的 `resolve_version` 三处同步，不得遗漏）；发布产物**摘要校验一致**（build-deb.sh 生成 `.deb.sha256` 随包携带；这不是独立数字签名）；任何旧版本/内测安装用户都能用新 `.deb` 直接**增量升级**（postinst 兼容升级路径——venv 复用 + conffile 幂等追加，T24 已建先例）。
- 实施前缺口（已关闭）：当时版本源不一致且 SettingsDialog 无更新/About/T&C/
  Privacy 入口；当前代码与发布默认值已统一到 0.1.7，并已提供对应页面。
- 产品定位：**参赛作品**（麒麟 OS Agent 记忆优化赛题），非商业上线产品——文案须符合赛题语境（麒麟适配、偏好/知识记忆优化、隐私承诺：敏感信息识别过滤、端侧处理、数据本地），少量即可。

## [S2] 版本管理一致性落地

### [S2.1] 三处版本源同步
- `frontend/src/main.cpp:24`：`setApplicationVersion` 硬编码 → 与 CMakeLists 一致的当前发布版本（本次 0.1.1）。
- `frontend/CMakeLists.txt:3`：`project(pixiu-frontend VERSION 0.1.1 ...)`。
- `build/release/scripts/functions.sh`：resolve_version 默认已 0.1.1（T24 bump）——核对一致。
- **机制**：在 build/release/scripts/build-deb.sh 增加**版本一致性预检**（发布时校验 main.cpp/CMakeLists/functions.sh 三处版本号一致，不一致即报错退出）——防止未来发布遗漏（用户宗旨①的可执行化）。

### [S2.2] 摘要校验一致
- 现状：build-deb.sh 已生成 `.deb.sha256`；publish.sh 随包拷贝。**保持**，文档注明校验方法（`sha256sum -c pixiu_*.deb.sha256`）。
- 增量升级兼容：postinst venv 复用 + conffile 幂等追加（T24 已落地并实测）——保持，文档注明「支持旧版/内测直接 dpkg -i 升级」。

## [S3] 应用内页面（SettingsDialog 扩展）

### [S3.1] SettingsDialog 新增「关于与法律」区
- 在 versionLabel 之后新增一行按钮（objectName 明确）：
  - **「检查更新…」**（objectName=checkUpdateButton）→ 打开更新对话框；
  - **「关于 PIXIU」**（objectName=aboutUsButton）→ 打开 About Us 页；
  - **「服务条款」**（objectName=termsButton）→ 打开 T&C 页；
  - **「隐私政策」**（objectName=privacyButton）→ 打开 Privacy 页。
- 布局：按钮行（QHBoxLayout 或 grid）置于 versionLabel 之后、buttonRow 之前；窄窗下允许换行（WordWrap 或 wrap 布局——以最小改动为准，按钮文案短不换行）。

### [S3.2] InfoDialog 通用文档对话框（新建）
- 新建 `frontend/src/widgets/InfoDialog.{h,cpp}`：`InfoDialog(title, bodyHtml, parent)`——只读 QTextBrowser 或 QLabel(Qt::RichText) + 关闭按钮；objectName=`infoDialog`/`infoTextBrowser`。
- 三种页面复用同一对话框，内容由调用方传入（服务条款/隐私政策/关于各一份文案）：
  - **About Us**：产品一句话（参赛定位）+ 核心能力（记忆优化：偏好捕捉/知识整合/高效检索）+ 麒麟适配 + 版本号；
  - **Terms & Conditions**（服务条款）：参赛作品声明 + 使用约定（数据本地存储、功能按现状提供）+ 简短；
  - **Privacy**（隐私政策）：数据隐私承诺（敏感信息识别过滤、端侧处理不上传、监控可随时关闭、记忆可遗忘）。
- 文案**参照 docs/OriginProblemDescription.md 语境**编写，**少量即可**（每页 3-6 句），全部 tr() 中文源文本 + 英文译文（i18n 收编）。

### [S3.3] 更新对话框（历史最小范围，已被在线升级实现取代）
- 简单实现（不引入 OTA 服务——参赛语境）：显示**当前版本**（applicationVersion）与**提示文案**「请从官方渠道获取最新版本，通过安装包直接升级；升级将保留您的记忆与配置。」；
- objectName=`checkUpdateDialog`；按钮「知道了」关闭；
- 后续已经实现在线检查、下载、校验和授权安装；本条“不做网络请求”的旧边界失效。

## [S4] 契约与接线
- SettingsDialog 新增信号：`checkUpdateRequested()` / `aboutUsRequested()` / `termsRequested()` / `privacyRequested()`（四个按钮各自信号）；
- PixiuApp openSettings 懒创建块内一次性 connect 四信号 → 各自 showInfoDialog（懒创建 InfoDialog/CheckUpdateDialog 实例）——仿 monitorCenterRequested 既有接线模式；
- i18n：新文案 tr() 中文源文本；B4-4 后 i18n 基线 279 条，本次预计 +~15-20 条（按钮+三页文案+更新对话框），Task 收尾 lupdate/lrelease 至 0 unfinished。

## [S5] 测试策略
- 前端 ctest（offscreen）：
  - SettingsDialog 四按钮存在且 emit 对应信号（t_memory_panel 或新建 t_settings_dialog——若存在沿用）；
  - InfoDialog 渲染标题与正文（三页内容可断言非空/含关键词）；
  - 更新对话框显示当前版本；
  - PixiuApp 接线（t_app_navigation：点按钮 → 对应对话框可见）；
- 全量回归：前端 OFF/ON ctest + regression.sh；后端零改动（纯前端）。
- 版本一致性：build-deb.sh 预检脚本单测（三处一致通过 / 一处不一致报错退出——shell 测试或在发布脚本内以 echo 断言）。

## [S6] 范围边界（不做）
- 原“不做真实在线更新”已由 2026-09-01 方案取代。
- 原“不做独立签名”不再适用于最终交付；SHA-256 已实现，独立签名仍是发布阻断项。
- 不改后端（纯前端 + 发布脚本预检）；
- 不引入新第三方依赖。

## [S7] 风险与开放点
- 版本号三处同步是人工风险——预检脚本是主要防线（S2.1）；main.cpp 硬编码 vs CMake 传参（可用 CMake 宏定义注入避免漂移——评估：CMake `target_compile_definitions` 传 `PIXIU_VERSION` 替代硬编码，改动小且根治漂移；倾向做）；
- InfoDialog 文案语言（中文源 + 英文译文）——保持与既有 i18n 一致；
- 更新对话框文案避免承诺不存在的在线更新能力（参赛语境如实）。
