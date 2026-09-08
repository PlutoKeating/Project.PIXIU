# 版本管理宗旨落地 + 关于/更新/条款/隐私页面 Design Spec

本文按实际唯一宿主实现维护，保留既有章节编号与标题用于引用。
旧 SettingsDialog、PixiuApp 及其接线已删除；不保留旧版本号、旧截图状态或失效承诺。
安装发布约束见 docs/DELIVERY_PLAN.md，完整待办见 docs/UNIFIED_FRONTEND_PLAN.md。

## [S1] 背景与目标

- 根 VERSION 是唯一产品版本输入；前端、整包、运行时注入及 Provider 由它派生。
- 新发布需版本递增、摘要与独立签名验证、安装后健康检查和升级兼容验证。
- 正式宿主提供更新、关于、数据联网说明与许可证页面；不恢复独立小窗口。
- 页面说明必须区分本地管理、模型联网、共享同步、采集授权与遗忘实际边界。

## [S2] 版本管理一致性落地

### [S2.1] 单一版本源（已取代最初三处同步方案）

- 正式管理 CMake 与宿主导出从根 VERSION 注入产品版本。
- Debian 整包 control、release-manifest.json 和 Module E 模板由构建生成。
- frontend/CMakeLists.txt 仅构建回归，不提供独立产品或独立 Debian 包。
- 发布预检检查版本与派生关系；前端版本测试还禁止已退役源码和构建目标回归。

### [S2.2] 摘要校验一致

- build-deb.sh 生成包及 .deb.sha256；发布链另提供独立签名。
- 在线升级校验摘要、获取签名并通过授权安装验证链；不能把下载成功当作安装成功。
- postinst 的配置保留、用户服务与健康检查属于整包流程。
- 真实旧版升级、失败与回滚仍需完整验证，不承诺所有历史安装状态均已实测。

## [S3] 应用内页面（SettingsDialog 扩展）

### [S3.1] SettingsDialog 新增「关于与法律」区

章节名保留，实际实现已替换为 SettingsWorkspace 的“应用与升级”。

- productUpdates：检查更新。
- productAbout：关于 PIXIU。
- productDataUse：数据与联网说明。
- productLicenses：许可证与第三方组件。
- 页面还包含模型与 Agent 配置、唤起快捷键和版本信息；采集、服务诊断在独立页签。
- 不沿用旧窗口尺寸、旧按钮信号或旧条款/隐私承诺。

### [S3.2] InfoDialog 通用文档对话框（新建）

- 现有 InfoDialog(title, body, parent) 使用只读 QTextBrowser::setPlainText；
  HTML 字面量和段落原样呈现，不是富文本契约。
- 三个说明实例由 SettingsWorkspace 持有，重复点击复用；关闭只隐藏所属说明页。
- ProductInformation::about 描述唯一 Agent 宿主与直接访问记忆服务的管理功能。
- dataUse 明确模型可能接收输入、召回上下文及工具结果；默认本地服务不等于永不联网。
- 关闭采集不删除已有记忆，敏感识别不保证完整，逻辑遗忘不等于所有副本物理擦除。
- licenses 指向包内 NOTICE、组件清单和实际许可证，不授予新许可。

### [S3.3] 更新对话框（历史最小范围，已被在线升级实现取代）

- CheckUpdateDialog 配合 UpgradeController 执行实际检查、下载、验证、授权安装。
- 展示当前版本、远程版本、进度与错误；没有控制器时禁用升级。
- 成功后由用户选择重启；SettingsWorkspace 先经 HostCloseGuard 检查在途请求和草稿，
  拒绝时不调用重启 helper。
- 当前实现不是仅展示下载指引的静态弹窗；也不能据此宣称所有原生升级状态已验收。

## [S4] 契约与接线

- SettingsWorkspace 直接持有三个 InfoDialog 和一个受控升级对话框。
- 模型配置通过 agentSettingsRequested 交还原宿主；不创建另一套模型设置生命周期。
- 信息正文由 ProductInformation 统一提供；版本来自编译注入与宿主应用版本。
- 旧 SettingsDialog 四信号与 PixiuApp 懒创建接口不再存在。
- 正式管理模块完整英文资源与语言切换未完成，不能以旧资源测试代替。

## [S5] 测试策略

- product_dialogs 在根回归与正式管理库两处构建：纯文本/只读、关闭不影响宿主、
  当前版本显示、无控制器禁用升级。
- t_memory_workspace 验证正式信息入口、实例复用及退出保护。
- t_check_update_dialog 与 t_upgrade_controller 验证本地假服务驱动的状态、失败和重启行为。
- test-version-source.sh 只证明其覆盖的回归版本关系和退役检查；整包派生另需发布预检。
- offscreen、SDK 替身、V11 原生分别报告；升级测试在 Qt 初始化前自动隔离临时目录，
  temp_isolation 哨兵回归验证不会删除外层其他进程安装包。
- 完整安装、升级、权限拒绝、签名失败和数据保留需真实环境证据。

## [S6] 范围边界（不做）

- 不恢复旧应用、独立包、旧配置层或旧语言选择空壳。
- 不把摘要当作签名，不把组件测试当作生产安装验收。
- 不修改后端私有实现，不引入新的页面框架或系统依赖。
- 不删除用户配置、会话、记忆或同步身份。

## [S7] 风险与开放点

- 派生版本仍需持续门禁，最终标签和产物必须对应经过验证的提交。
- 完整语言、布局、可访问性与原生升级矩阵仍在统一计划中。
- 升级测试的进程私有临时目录及哨兵回归必须保留；同一个 CTest 的资源锁
  不能替代跨进程文件归属隔离。
- 文案必须随实际模型、同步、采集与遗忘能力变化而更新，不承诺不存在的隐私保证。
