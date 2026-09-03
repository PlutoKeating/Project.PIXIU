# 版本管理宗旨落地 + 关于/更新/条款/隐私页面 Design Spec

> 日期：2026-08-30 · 状态：已实现并被在线一键升级方案扩展（2026-09-03 复核）
> 定位：落实用户定义的版本管理核心宗旨（严格版本增量 + 摘要校验一致 + 旧版可增量升级），并为应用补充更新入口与 About Us / Terms & Conditions / Privacy 页面。
>
> 本文保留最初设计过程。当前版本已统一为 0.1.7，关于/条款/隐私和在线升级均已
> 实现；原“三处静态版本同步”已被根 `VERSION` 唯一输入和派生生成取代。在线流程
> 以 `2026-09-01-in-app-upgrade-design.md` 为准，最终签名、回滚和兼容门禁以
> `docs/DELIVERY_PLAN.md` 为准。

## [S1] 背景与目标

- 用户核心宗旨：每次新发布必须**版本增量更新**；当前只修改根 `VERSION`，应用、
  Debian 包、后端注入和 Provider manifest 全部派生。发布产物须**摘要校验一致**
  （`.deb.sha256` 不是独立数字签名）；任何旧版本/内测安装用户都能用新 `.deb`
  直接**增量升级**（当前机制为 venv 复用 + postinst 管理非 conffile 运行配置）。
- 实施前缺口（已关闭）：当时版本源不一致且 SettingsDialog 无更新/About/T&C/
  Privacy 入口；当前代码与发布默认值已统一到 0.1.7，并已提供对应页面。
- 产品定位：**参赛作品**（麒麟 OS Agent 记忆优化赛题），非商业上线产品——文案须符合赛题语境（麒麟适配、偏好/知识记忆优化、隐私承诺：敏感信息识别过滤、端侧处理、数据本地），少量即可。

## [S2] 版本管理一致性落地

### [S2.1] 单一版本源（已取代最初三处同步方案）

- 根 `VERSION` 是唯一产品版本输入。
- 前端 CMake/编译宏、前端独立 control、全量 Debian 包、后端运行时注入和 Module E
  `plugin.yaml` 均从该文件派生。
- 发布预检拒绝环境断言、tag 或派生关系不一致，防止未来发布遗漏。

### [S2.2] 摘要校验一致
- 现状：build-deb.sh 已生成 `.deb.sha256`；publish.sh 随包拷贝。**保持**，文档注明校验方法（`sha256sum -c pixiu_*.deb.sha256`）。
- 增量升级兼容：postinst 复用 venv；运行配置由 `/usr/share` 默认模板首装创建，升级
  保留并幂等补字段，不再作为 dpkg conffile（2026-09-03 修复非交互升级冲突）。

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
- 版本一致性：`test-version-source.sh` 验证唯一输入及全部派生关系；显式版本漂移必须失败。

## [S6] 范围边界（不做）
- 原“不做真实在线更新”已由 2026-09-01 方案取代。
- 原“不做独立签名”不再适用于最终交付；SHA-256 已实现，独立签名仍是发布阻断项。
- 不改后端（纯前端 + 发布脚本预检）；
- 不引入新第三方依赖。

## [S7] 风险与开放点
- 版本号人工同步风险已由根 `VERSION` 唯一输入关闭；发布预检仍作为回归防线（S2.1）。
- InfoDialog 文案语言（中文源 + 英文译文）——保持与既有 i18n 一致；
- 更新对话框文案避免承诺不存在的在线更新能力（参赛语境如实）。
