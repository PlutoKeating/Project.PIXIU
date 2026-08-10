# Module A 前端开发执行计划

> 模块：UKUI 桌面客户端（`frontend/`）
> 分支：`feature/frontend`
> 技术栈：C++17、Qt5 Widgets、KylinSDK
> 计划周期：2026-08-07 至 2026-09-15
> 对齐基线：2026-08-07，`feature/frontend` 已同步至 `cb8d20e`
> 当前状态：Phase 1A~1E、Phase 2、Phase 3、Phase 4 与 Phase 5.1~5.3 已完成并本地验收；
> Phase 7.1 麒麟全局快捷键、Phase 7.2 麒麟桌面通知与 Phase 7.3 UKUI 主题实时跟随
> 以及 Phase 7.4 UKUI 窗口装饰、Phase 7.5 高 DPI 与多屏、Phase 7.6 桌面入口
> 与 Phase 7.7 `.deb` 打包已在本机（Kylin V11）完成编译/测试/冒烟验收；
> Phase 7.3 追加修复：`themeMode()` 仅在启动时缓存，已改为读 QGSettings
> 实时 `styleName` 判定明暗，并在本机真实桌面会话验证 dark→light→dark
> 实时跟随（`fix(frontend): read live style name for UKUI theme following`）；
> Phase 8 本地验收基线已完成（双路径构建 + ctest 23/23 + offscreen 冒烟 +
> `.deb` 产物校验），已固化为 `frontend/scripts/regression.sh`；中/英文案
> i18n 已完成（`tr()` 包装 + `resources/i18n/pixiu_en_US.ts/.qm` 内嵌），
> 适配报告见 `frontend/docs/UKUI_ADAPTATION_REPORT.md`；
> Phase 6 设备配对 UI 壳（非阻塞部分，2026-08-09）已完成：`PairDialog`、
> 同步 Tab 配对入口与状态行、`/sync/pair` 接线（如实呈现占位/错误，仅
> `paired` 判成功）、窗口/托盘内嵌 `pixiu.svg` 图标；新增 `t_pair_dialog`/
> `t_app_icon`，套件增至 23 例全绿，双路径回归通过；真实配对闭环与
> 节点列表/状态/解绑仍待 `foundation/sync` 契约落地；
> Phase 6 同步管理 UI 与 WS 业务事件路由（2026-08-09）已完成：`SyncController`
> + 同步 Tab 节点列表/同步摘要/刷新/解绑二次确认（`RevokeDialog`），
> `BackendTransport::peersResult` 改为携带完整响应体以如实识别占位态；
> `EventRouter` 将 `conflict_detected`/`forget_confirmation`/`sync_event`
> 路由为通知、角标、面板刷新与远端遗忘确认（`ForgetController::confirmRemote`）；
> 新增 `t_sync_controller`/`t_revoke_dialog`/`t_event_router`，套件增至 26 例
> 全绿；真实节点/状态/解绑闭环仍待 `foundation/sync` 契约落地；
> WebSocketClient 真实环境验收依赖 Module C 修复 `/events` 注册与 WebSocket 导入问题
> （见 `frontend/docs/BACKEND_ISSUES.md`）；
> Phase 8 真实桌面收尾（2026-08-08）：第二实例激活通道、通知弹窗
> （测试专用 WS 桩驱动 `memory_ready` → KNotifier id 有效）、窗口阴影应用
> 均已在本机实时 UKUI 会话验证并截图留证；全局快捷键真实按键触发在当前
> 运行会话未复现（注册 API 与 dconf 配置正确，但 kylin-wlcom 运行期未加载
> grab），列为全新登录会话人工复测项（见 `UKUI_ADAPTATION_REPORT.md` 第 4/5 节）。
> 设置入口与界面语言偏好（2026-08-09）已完成：`SettingsDialog`（跟随系统/
> 中文/English、OK/取消/Esc/关闭语义、关于与版本）、聊天框顶栏 ⚙ 与悬浮球
> 右键菜单“设置”入口、`AppSettings::keyLanguage` 持久化与启动时按显式
> 偏好加载翻译（`en_US`/`zh_CN`/跟随系统）；新增 `t_settings_dialog` 并
> 扩展 chat_window/floating_ball/i18n 用例，套件增至 27 例全绿（OFF/ON
> 双路径），offscreen 冒烟通过。
> 加载失败态与重试（2026-08-09）已完成：`MemoryPanel` 冲突/偏好历史 Tab
> 区分“空结果”与“加载失败”（失败原因 + 重试按钮，成功加载后自动隐藏），
> PixiuApp 将 `ConflictController`/`PreferenceController` 失败上抛到面板
> 并记录最近偏好 ID 供重试重发；`t_memory_panel` 新增 4 例，套件 27 例
> 全绿（OFF/ON 双路径），i18n 147 条、0 未完成。
> 全局快捷键自定义（2026-08-09）已完成：`SettingsDialog` 增加
> `QKeySequenceEdit`（默认 Ctrl+Alt+P，需含 Ctrl/Alt/Meta 修饰键），
> `ShortcutManager` 支持自定义序列（空值回退默认），`keyToggleShortcut`
> 持久化，启动按已存序列注册、设置确认后即时重注册；`t_shortcut_manager`/
> `t_settings_dialog`/`t_app_settings`/`t_i18n` 扩展，套件 27 例全绿
> （OFF/ON 双路径），i18n 149 条、0 未完成。
> 管理面板加载态与写入防重（2026-08-09）已完成：冲突/偏好历史 Tab 增加
> “正在加载…”态（与空态/失败态互斥），`WriteController` 在途防重且
> `writeFailed` 仅在写入在途时上抛（修复通用错误串扰）；`t_memory_panel`/
> `t_write_controller`/`t_i18n` 扩展，套件 27 例全绿（OFF/ON 双路径），
> i18n 151 条、0 未完成。
> 管理控制器防重与离线引导（2026-08-09）已完成：`ConflictController`/
> `PreferenceController` 在途防重（避免重复请求与过期响应误配）；后端未
> 连接时聊天框引导启动 PIXIU 后端服务（每次断线提示一次）；套件 27 例
> 全绿（OFF/ON 双路径），i18n 152 条、0 未完成。
> 聊天框拖动与位置记忆（2026-08-09，ARCHITECTURE §5.2）已完成：无边框
> 聊天框按住空白区域拖动，位置经 `keyWindowGeometry` 持久化并在启动时
> 恢复（屏幕可用区域钳制）；`t_chat_window` 新增 1 例，套件 27 例全绿
> （OFF/ON 双路径）。
> 统一 UI/UX Polish 基线（2026-08-09）已完成：设计令牌（UiTokens：语义色/
> 14-11-9pt 字号/间距/圆角/统一危险按钮）、全局 QSS 控件状态、主题感知
> 图标（悬浮球网络标记/设置齿轮）、角标弹入呼吸与思考骨架屏、聊天框可
> 拉伸与记忆面板尺寸复核；OFF/ON 双路径回归通过，离屏渲染核对截图见
> `docs/screenshots/ui-polish-2026-08-09/`，逐项状态与剩余人工复测/后端
> 阻塞项见 `UI_UX_POLISH.md`。
> 周期健康探测（2026-08-09，健壮性收尾）已完成：`HttpBackendTransport`
> 独立静默周期探测（GET /conflicts，默认 10s），后端中途挂掉/事后启动时
> 顶栏状态与离线引导无需用户操作即自动刷新；新增 `t_http_backend`，
> 套件 28 例 OFF/ON 全绿，本机真实 UKUI 桌面验证通过（详见 §6.3）。

## 1. 当前进度摘要

### 1.1 已完成

- 已建立独立的 Qt5/CMake 应用骨架，提交为 `9cebaa8 chore(frontend): scaffold Qt5 application`。
- 已建立 `frontend/src/app`、`frontend/src/models`、`frontend/src/services`、
  `frontend/src/widgets` 和 `frontend/resources` 基础目录。
- 已建立 `frontend/src/main.cpp`，完成最小 `QApplication` 入口及应用元数据设置。
- 已建立 `frontend/CMakeLists.txt`，设置 C++17、Qt5 Widgets 和
  `PIXIU_HAVE_KYSDK` 构建选项。
- 已确认构建产物、缓存、`.env` 和 IDE 临时文件不得进入 Git。
- 已实现 `frontend/src/services/WebSocketClient.{h,cpp}` 并接入 `CMakeLists.txt`
  （新增 `Qt5::WebSockets` 组件与链接），本地编译/链接验收通过（2026-08-08，
  Qt 5.15.19）。
- 后端联调发现的 2 项问题（`/events` 未注册、`ws.py` WebSocket 导入缺失）已记录于
  `frontend/docs/BACKEND_ISSUES.md` 交接 Module C；WebSocketClient 的真实环境
  验收依赖其修复。
- 已实现 `memory_ready` 事件映射：WebSocketClient 接入应用生命周期，业务事件驱动
  悬浮球未读角标；新增 QtTest 测试基础设施（`tests/t_websocket_client`、
  `tests/t_floating_ball`）。
- 已实现桌面通知服务 `NotifyService`（托盘 `QSystemTrayIcon::showMessage`，无托盘
  降级为日志），`memory_ready` 已联动“记忆已沉淀”通知。
- 已实现 `/forget` 两段式确认：`ForgetController` 识别“忘记/遗忘/忘了”指令，
  `ForgetDialog` 展示影响范围，确认后才执行第二阶段。
- 已实现 `MemoryPanel` 壳：偏好 / 冲突 / 同步 三个 Tab 及占位页，聊天框“记忆”
  入口已联动打开。
- 已实现冲突审计视图：`ConflictController` 拉取 `GET /conflicts`，面板冲突 Tab
  展示 old/new 对比与裁决结果；面板每次打开时刷新。
- 已实现偏好历史视图：面板偏好 Tab 支持输入偏好 ID 加载
  `GET /preference/{id}/history` 的版本历史（偏好列表接口落地后替换为选择入口）。
- 已实现 Phase 6 设备配对 UI 壳（非阻塞部分，2026-08-09）：`PairDialog`
  （PIN/二维码方式、6 位 PIN 门控、Esc/取消语义、契约载荷）、记忆面板同步
  Tab 配对入口与状态行；PixiuApp 经 `HttpBackendTransport::pairDevice` 发
  `POST /sync/pair`，`not_implemented`/网络错误/未知状态如实呈现，仅契约
  `paired` 判成功；窗口与托盘图标改用内嵌 `pixiu.svg`；新增
  `t_pair_dialog`/`t_app_icon`（套件由 21 增至 23 例），双路径回归
  （OFF/ON 构建 + ctest + offscreen 冒烟 + desktop 校验 + `.deb`）通过。
- 已实现 Phase 6 同步管理 UI（2026-08-09）：`SyncController` 封装
  `/sync/peers`、`/sync/status` 与 `/sync/peers/{id}/revoke`（在途防重、
  `not_implemented`/未知响应如实上报、仅契约成功态放行）；同步 Tab 新增
  节点列表（本机/在线/离线/上次同步/待同步条数）、同步摘要（共享域/在线数/
  待同步/上次对账/累计同步）、刷新按钮与非本机设备“解绑”入口；`RevokeDialog`
  危险操作二次确认（默认聚焦取消、Esc 视为取消）；`BackendTransport::peersResult`
  改携完整响应体，便于上层区分 `{"peers":[...]}` 与占位 `{"status":...}`。
- 已实现 WS 业务事件路由（2026-08-09）：`EventRouter` 将 `conflict_detected`
  （通知 + 角标 + 冲突列表刷新 + 面板可见时切冲突 Tab）、`forget_confirmation`
  （弹出 ForgetDialog，确认后经 `ForgetController::confirmRemote` 直接执行
  第二阶段）、`sync_event`（通知 + 同步刷新）路由为应用行为；`memory_ready`
  逻辑一并迁入路由层，原有角标/通知行为不变。
- 已实现设置入口与界面语言偏好（2026-08-09）：`SettingsDialog`
  （跟随系统/中文/English、OK/取消/Esc/关闭语义、关于与版本信息），聊天框
  顶栏 ⚙ 按钮与悬浮球右键菜单“设置”统一接入 `PixiuApp::openSettings`；
  语言偏好经 `AppSettings::keyLanguage` 持久化（仅 accepted 后写入），
  `main.cpp` 启动时按显式偏好加载翻译，切换在下次启动生效；新增
  `t_settings_dialog`（7 例），扩展 `t_chat_window`/`t_floating_ball`/
  `t_i18n`，套件增至 27 例全绿，OFF/ON 双路径构建 + ctest + offscreen
  冒烟通过。
- 已实现加载失败态与重试（2026-08-09）：`MemoryPanel` 冲突/偏好历史 Tab
  将“空结果”与“加载失败”分开呈现（失败原因 + “重试”按钮，成功加载后
  自动隐藏错误行）；PixiuApp 在 `ConflictController::failed` /
  `PreferenceController::failed` 时把错误上抛到对应 Tab，并记录最近一次
  偏好 ID 供重试重发；`t_memory_panel` 新增 4 例，`t_i18n` 扩展，套件
  27 例全绿（OFF/ON 双路径），i18n 147 条、0 未完成。
- 已实现全局快捷键自定义（2026-08-09，ARCHITECTURE §9）：`SettingsDialog`
  增加 `QKeySequenceEdit`（默认 `Ctrl+Alt+P`，要求包含 Ctrl/Alt/Meta 修饰键，
  否则禁用“确定”）；`ShortcutManager::registerToggleShortcut(sequence)` 支持
  自定义序列（空序列回退默认，KYSDK 与 Qt 降级路径一致）；
  `AppSettings::keyToggleShortcut` 持久化 PortableText；`PixiuApp` 启动时按
  已存序列注册，设置确认后序列变化则释放旧注册并即时重注册。
  `t_shortcut_manager` 新增 3 例、`t_settings_dialog` 新增 4 例，
  `t_app_settings`/`t_i18n` 扩展；套件 27 例全绿（OFF/ON 双路径），
  i18n 149 条、0 未完成。
- 已实现管理面板加载态与写入在途防重（2026-08-09）：冲突 Tab 与偏好历史
  Tab 增加“正在加载…”态（打开面板/刷新/重试时进入，与空态/失败态互斥）；
  `WriteController::submit` 在途防重（在途返回 false），`writeFailed` 仅在
  在途时上抛（修复其他端点错误串扰为“录入失败”），重复提交时应用层给出
  明确提示；`t_memory_panel` 新增 2 例、`t_write_controller` 新增 4 例、
  `t_i18n` 扩展；套件 27 例全绿（OFF/ON 双路径），i18n 151 条、0 未完成。
- 已实现管理控制器在途防重与后端离线引导（2026-08-09）：
  `ConflictController::refresh`/`PreferenceController::loadHistory` 在途
  防重（避免重复请求与偏好历史过期响应误配）；后端未连接
  （`Disconnected`/`Error`）时聊天框追加系统提示引导启动 PIXIU 后端服务
  （每次断线仅提示一次，恢复在线后复位）；`t_conflict_controller`/
  `t_preference_controller` 各新增 1 例，`t_i18n` 扩展；套件 27 例全绿
  （OFF/ON 双路径），i18n 152 条、0 未完成。
- 已实现聊天框拖动与位置记忆（2026-08-09，ARCHITECTURE §5.2）：无边框
  聊天框支持按住空白区域拖动（子控件自行消费事件），拖动经 `moved` 信号
  持久化到 `AppSettings::keyWindowGeometry`，启动时恢复并按屏幕可用区域
  钳制（与悬浮球策略一致）；`t_chat_window` 新增拖动用例 1 例；套件 27 例
  全绿（OFF/ON 双路径）。
- 已实现周期健康探测（2026-08-09，健壮性收尾）：`HttpBackendTransport`
  增加独立、静默的周期健康探测（GET /conflicts，默认 10s，测试可注入短
  间隔）：仅驱动连接状态（Connected/Error），不广播 `conflictsResult`/
  `errorOccurred`，在途防重、显式断开停止；后端中途挂掉/事后启动时顶栏
  “● 在线/服务异常”与离线引导自动刷新，无需等下一次用户操作。新增
  `t_http_backend`（3 例），套件 28 例 OFF/ON 双路径全绿，`.deb` 校验
  通过；本机真实 UKUI 桌面验证通过（见 §6.3）。
- 已实现麒麟全局快捷键：`ShortcutManager` 在 `PIXIU_HAVE_KYSDK=ON` 下通过
  kysdk-shortcut 注册系统级 `Ctrl+Alt+P`（绑定本应用可执行程序，重复实例经
  SingleInstanceGuard 转发激活给主实例）；注册失败时降级 Qt `ApplicationShortcut`。
- 已实现麒麟桌面通知：`NotifyService` 在 `PIXIU_HAVE_KYSDK=ON` 下通过
  kysdk-notification `KNotifier` 弹系统通知（不依赖托盘）；无 KYSDK 时保持
  托盘 `showMessage` / 日志降级。
- 已实现 UKUI 主题实时跟随：`ThemeService` 在 `PIXIU_HAVE_KYSDK=ON` 下通过
  kysdk-qtwidgets `ThemeController` 监听 UKUI 明暗主题变化，深色主题应用 UKUI
  深色近似 Palette，浅色主题恢复启动时捕获的系统 Palette；无 KYSDK 时保持
  Qt Palette 静态降级（不触碰应用调色板）。
- 已实现 UKUI 窗口装饰：`UkuiWindow` 适配层在 `PIXIU_HAVE_KYSDK=ON` 下通过
  kysdk-qtwidgets `KShadowHelper` 给聊天框应用 UKUI 风格圆角阴影；无 KYSDK 时
  空操作，保持现有 Qt Widgets 表现。
- 已实现高 DPI 与多屏适配：应用入口在 `QApplication` 构造前启用
  `AA_EnableHighDpiScaling` / `AA_UseHighDpiPixmaps`；悬浮球位置恢复按所在
  屏幕 `availableGeometry` 钳制并回退主屏，聊天框/悬浮球默认定位基于主屏
  可用区域。
- 已实现桌面入口：`resources/com.kylin.pixiu.desktop`（名称/注释/Exec/图标），
  CMake 增加 `GNUInstallDirs` 安装规则（二进制 → `bin/`，desktop → 
  `share/applications/`），`desktop-file-validate` 校验通过。
- 已实现 `.deb` 打包：`debian/`（control/rules/postinst）+ `scripts/build-deb.sh`
  基于 `dpkg-deb --build` 产出 `pixiu-frontend_<version>_<arch>.deb`，包含
  `/usr/bin/pixiu-frontend` 与桌面入口；`dpkg-buildpackage` 的 rules 委托同一脚本。
- 已实现 i18n：全部用户可见文案经 `tr()` 包装（提交
  `7a3eb07`/`33967de`），`resources/i18n/pixiu_en_US.ts`/`.qm` 内嵌进 qrc，
  入口按 `LANGUAGE`/系统语言加载英文翻译，其余环境保持中文源码文本；新增
  `t_i18n` 测试校验内嵌翻译加载与生效。
- 已实现 WebSocket 断线重连回归测试与自动化回归基线：`t_websocket_client` 新增
  重连回归用例（`1d9dd4b`），`scripts/regression.sh` 一键执行 OFF/ON 双路径
  构建 + ctest 20/20 + offscreen 冒烟 + desktop 校验 + `.deb` 校验。
- 已实现查询失败重试 UI：失败提示行（红字详情）带“重试”按钮，点击后以原始
  查询文本重新提交（`MessageList::appendQueryError` + `retryRequested`，
  PixiuApp 接线到 `QueryController::submit`），输入同时保留；新增
  `t_message_list` 用例与 `MessageList` 英文翻译。
- 已实现键盘可达补强（Phase 8 键盘可达条目）：ForgetDialog 的 Esc/窗口关闭
  统一触发 `cancelled()`（控制器不再残留待确认指令），危险操作默认聚焦
  “取消”；MemoryPanel Esc 隐藏；聊天框顶栏、输入栏按钮与输入框补充
  accessibleName（无障碍读屏）。对应 `t_forget_dialog`/`t_memory_panel`/
  `t_chat_window`/`t_input_bar`/`t_i18n` 用例。
- 已实现空结果引导（关键状态表“空结果”条目）：空结果提示行附“录入知识”
  按钮，点击直接打开录入对话框（`MessageList::appendEmptyResult` +
  `importKnowledgeRequested` → `ImportDialog`）；`t_message_list` 用例与
  “录入知识”英文翻译已补。
- 已补 ImportDialog 专属测试（`t_import_dialog`：按钮门控、确认载荷与清空、
  取消/Esc 隐藏、图片拖入预览与载荷路径），套件由 20 增至 21。
- 已产出 Phase 8 演示说明与已知问题清单（`frontend/docs/DEMO_GUIDE.md`：
  演示前置条件、按场景串场步骤、依赖标注、演示口径建议）。
- 已实现悬浮球右键菜单（IA 第 4/5.1 节“右键菜单”条目）：打开聊天框 /
  记忆面板 / 退出，动作经 `clicked`/`openPanelRequested`/`quitRequested`
  与既有入口统一接线（记忆面板复用聊天框顶栏入口逻辑，退出复用托盘
  退出逻辑）；`t_floating_ball` 覆盖动作触发。

### 1.2 尚未完成

- WebSocketClient 的真实环境冒烟（连接 `/events`、`connected`/`ping`/`memory_ready`）
  未完成：后端两项问题阻塞（见 `frontend/docs/BACKEND_ISSUES.md`）。
- Phase 5.4 偏好列表、Phase 5.5 证据原文：等待后端列表/详情契约落地后实现。
- Phase 6 设备同步管理真实闭环：节点列表/同步状态/解绑的 UI 与客户端已
  完成（见 1.1），但 `foundation/sync` 与 `/sync/*` 仍为占位，真实联调阻塞；
  二维码配对展示等待令牌生成契约（Phase 6 第 5 项）。
- `conflict_detected`/`forget_confirmation`/`sync_event` 的客户端路由已完成
  （见 1.1），真实端到端广播验证等待后端事件接入（`docs/API.md` §4 占位项）。
- Phase 8 验收发布：本地自动化回归基线已完成（`scripts/regression.sh`，
  ctest 26/26）；本机实时 UKUI 会话已完成真实桌面冒烟与收尾验证（应用
  启动、窗口、托盘、UKUI 阴影、全局快捷键注册、主题 dark→light→dark
  实时跟随、第二实例激活通道、WS 桩驱动通知弹窗）。剩余项：全局快捷键
  真实按键触发需在全新登录会话复测（当前运行会话未加载 grab，见
  `UKUI_ADAPTATION_REPORT.md` 第 5 节）、通知弹窗点击行为、HiDPI/多屏
  与 x86/ARM 目标机验收、配对对话框真实桌面视觉验收依赖人工复测
  （清单见该报告第 4 节）。

### 1.3 下一项最小独立 feature

**Phase 8 收尾（本机可完成部分）已完成**：第二实例激活通道、通知弹窗
（WS 桩驱动 `memory_ready` → `kysdk notification sent, id: 5`）、窗口阴影
应用均已在本机实时 UKUI 会话验证并截图留证；全局快捷键真实按键触发经
运行时探针确认当前会话未加载 grab（注册 API 与 dconf 配置正确），需在
全新登录会话/合成器重启后人工复测，并已记录复测步骤与失败时的备选方案
（见 `UKUI_ADAPTATION_REPORT.md` 第 4/5 节）。

2026-08-09 追加：设置入口与界面语言偏好（不依赖后端）已作为下一项独立
feature 完成（`feat(frontend): add settings dialog and language preference`）：
顶栏 ⚙ / 悬浮球菜单“设置” → `SettingsDialog`，语言三选持久化并在下次启动
时生效；套件 27 例全绿（OFF/ON 双路径），offscreen 冒烟通过。

2026-08-09 追加：冲突/偏好历史“加载失败 vs 空结果”区分与重试（不依赖后端）
已完成（`feat(frontend): distinguish load failure from empty state with
retry`）：MemoryPanel 两个 Tab 显示失败原因 + 重试按钮，成功加载后自动
恢复；套件 27 例全绿（OFF/ON 双路径）。

2026-08-09 追加：全局快捷键自定义（不依赖后端，对应 ARCHITECTURE §9）已完成
（`feat(frontend): make toggle shortcut customizable in settings`）：设置页
`QKeySequenceEdit` 门控（需含修饰键），`ShortcutManager` 自定义序列 + 空值
回退，`keyToggleShortcut` 持久化，启动读取/确认后即时重注册；套件 27 例
全绿（OFF/ON 双路径），i18n 149 条、0 未完成。

2026-08-09 追加：管理面板加载态与写入在途防重（不依赖后端）已完成
（`feat(frontend): add management loading states and write in-flight guard`）：
冲突/偏好历史 Tab “正在加载…”态；`WriteController` 在途防重 +
`writeFailed` 仅在有写入在途时上抛（修复通用错误串扰）；套件 27 例全绿
（OFF/ON 双路径），i18n 151 条、0 未完成。

2026-08-09 追加：管理控制器在途防重与后端离线引导（不依赖后端）已完成
（`feat(frontend): guard management controllers against duplicate in-flight
requests` + `feat(frontend): guide user when backend service is offline`）：
`ConflictController`/`PreferenceController` 在途防重；后端未连接时聊天框
引导启动服务（断线仅提示一次）；套件 27 例全绿（OFF/ON 双路径），
i18n 152 条、0 未完成。

2026-08-09 追加：聊天框拖动与位置记忆（不依赖后端，ARCHITECTURE §5.2）
已完成（`feat(frontend): make chat window draggable and remember position`）：
空白区域按住拖动 + `keyWindowGeometry` 持久化 + 启动恢复与屏幕钳制；
套件 27 例全绿（OFF/ON 双路径）。

2026-08-09 追加：周期健康探测（健壮性收尾，不依赖后端）已完成
（`feat(frontend): probe backend health periodically`）：后端中途挂掉/
事后启动时，顶栏状态与离线引导无需用户操作即自动刷新；新增
`t_http_backend`，套件 28 例 OFF/ON 全绿，真实 UKUI 桌面验证通过。

其余 Module A 可执行项仍被后端契约阻塞：Phase 5.4/5.5 等待偏好列表与证据详情契约、
Phase 6 真实配对闭环/节点状态真实数据/二维码令牌等待 `foundation/sync`、
WS 真实事件联调等待 Module C 修复 `/events` 注册与 WebSocket 导入
（见 `BACKEND_ISSUES.md`）；`/memory/flow/promote` 等待 flow 契约与上下文
来源端点。阻塞期间 Module A 以测试专用 WS 桩
（`frontend/scripts/ws_smoke_server.py`）维持事件 UI 链路冒烟，不修改
`backend/`。

## 2. 职责边界与 SDK 策略

### 2.1 前端职责

前端为 PIXIU 提供银河麒麟 UKUI 原生交互入口，形成“悬浮球唤起—记忆问答—证据追溯—
记忆管理—设备配对”的用户链路。前端只修改 `frontend/`，通过 `docs/API.md` 约定的
HTTP REST、WebSocket 和可选 D-Bus 与 `backend/foundation` 异步通信。

前端不直接引用 `backend/` 的 Python/C++ 实现，不修改根 API 契约，也不实现：

- 文本向量化、向量数据库客户端或相关 SDK 绑定；
- SQLite、FTS5、ANN、知识图谱、融合和重排；
- 数据清洗、知识结构化、偏好提取、冲突仲裁或遗忘执行；
- CRDT、Gossip、反熵、TLS、同步日志或墓碑回收。

### 2.2 官方 third_party submodule

项目已通过根目录 `.gitmodules` 正式引入并 checkout 两个官方 SDK：

| Submodule | 当前 gitlink | 项目用途 | 前端边界 |
|---|---|---|---|
| `third_party/kylin-coreai-embedding` | `63aed6f3e947926f5def476997ee1baa6735dd8f` | 后端文本向量化、知识 embedding | 不 include、不 link、不封装、不修改源码 |
| `third_party/libkysdk-vector-engine-client` | `bed675f418d32c052a6ab4c5c49bae148d90f678` | 后端向量存储/检索接入 | 不 include、不 link、不封装、不修改源码 |

两者都跟踪 `openkylin/nile-sp2` 上游分支，由仓库根目录以 submodule 管理。全员开工前仍需执行：

```bash
git submodule update --init --recursive
```

这只是完整仓库环境要求，不代表它们是 `frontend` 的构建依赖。不得在 `frontend/` 下重复
添加 submodule，也不得把 `third_party` 源码耦合进前端。

### 2.3 前端直接使用的麒麟桌面能力

| 能力 | 前端用途 | 普通开发环境策略 |
|---|---|---|
| `kysdk-shortcut` | 全局快捷键唤起 | 独立适配接口；开发态使用 Qt 可用能力 |
| `kysdk-notification` | 记忆、冲突、同步通知 | `QSystemTrayIcon::showMessage` 降级 |
| Theme / `UkuiStyleHelper` | 明暗主题和系统配色 | Qt Palette / QSS 降级 |
| UKUI 扩展控件 | 悬浮、拖动、窗口管理 | Qt Widgets 实现基础行为 |
| 统一配置 | 位置、快捷键、语言持久化 | `QSettings` 降级 |

`PIXIU_HAVE_KYSDK` 只控制这些桌面能力，不得用于切换 embedding/vector 后端。麒麟专有代码
必须位于适配层之后，避免在 UI 组件中散落条件编译。

## 3. 最新 backend/foundation 接口基线

### 3.1 REST 实现状态

路径和主要契约与 `docs/API.md` 保持一致，但最新仓库已经从纯规划进入部分真实实现：

| 接口 | 当前状态 | 前端计划影响 |
|---|---|---|
| `POST /memory/write` | 已接入真实 ingest → knowledge → preference → conflict，并广播 `memory_ready` | 可在写入 UI 完成后真实联调；不得依赖未声明的处理时序 |
| `POST /memory/query` | 占位，返回 `{"status":"not_implemented"}` | 查询 MVP 的真实端到端验收被 retrieval 阻塞 |
| `POST /preference/extract` | 已实现 | 可按契约解析提取结果 |
| `GET /preference/{id}/history` | 已实现 | 可实现单项历史；偏好列表接口仍缺失 |
| `POST /forget` | 已实现 `confirm=false/true` 两段式流程 | 前端必须二次确认，取消时不得发确认请求 |
| `GET /conflicts` | 已实现 | 可展示现有冲突审计列表 |
| `POST /memory/flow/promote` | 占位 | 流转 UI 真实联调被 flow 阻塞 |
| `POST /sync/pair` | 占位 | 配对真实联调被 sync 阻塞 |
| `GET /sync/peers` | 占位 | 节点列表真实联调被 sync 阻塞 |
| `GET /sync/status` | 占位 | 同步状态真实联调被 sync 阻塞 |
| `POST /sync/peers/{id}/revoke` | 占位 | 解绑真实联调被 sync 阻塞 |

客户端解析必须只要求契约中的必需字段，并容忍新增 JSON 字段。例如当前写入实现还返回
`preference_count` 和 `conflict_detected`，前端不能因为出现额外字段而失败。任何契约字段变更
仍须由 Module A 与 Module C 双方确认，前端不得单方面修改 `docs/API.md`。

### 3.2 WebSocket 状态与兼容规则

`WS /events` 的连接管理、心跳和广播代码已进入仓库；`memory_ready` 已接入写入链路。
其余业务事件仍为占位：

| 事件 | 当前状态 |
|---|---|
| `connected` | 连接建立后由当前实现发送；属于协议控制事件 |
| `ping` | 当前实现每 30 秒发送；属于心跳控制事件 |
| `memory_ready` | 已从 `/memory/write` 链路广播 |
| `conflict_detected` | 契约已定义，尚未广播 |
| `forget_confirmation` | 契约已定义，尚未广播 |
| `sync_event` | 契约已定义，待 sync 阶段 |

WebSocket 客户端必须：

- 将 `connected`、`ping` 与业务事件分开处理；控制事件不得触发 UI 通知。
- 依据顶层 `event` 分发，`data` 缺失或类型错误时记录可脱敏诊断并安全忽略。
- 对未知事件保持前向兼容：不得崩溃、断开连接或弹出错误，只记录并忽略。
- 实现退避重连，避免断线后高频重试；心跳/ACK 语义在后端确认前不自行发明。
- WebSocketClient 已实现并完成本地编译/链接验收；但真实连接冒烟验证
  （`connected`/`ping`/`memory_ready`）仍未完成——后端存在两项阻塞问题：
  `/events` 未被实际启动入口注册、`ws.py` 的 `WebSocket` 标注缺少导入，
  详见 `frontend/docs/BACKEND_ISSUES.md`，修复后由 Module C 负责人确认并复测。

### 3.3 D-Bus 状态

`backend/foundation/api/dbus_service.py` 当前只有占位类：

- Bus name：`com.kylin.pixiu.Memory`
- Object path：`/com/kylin/pixiu/Memory`
- 方法和信号尚未实现

因此 D-Bus 暂不能作为首个可用传输。前端优先设计可替换的 transport 边界并使用
HTTP/WS 联调；D-Bus 只在后端接口真实落地并确认契约后实现，不得根据占位类猜测方法。

### 3.4 当前接口阻塞与待确认项

1. retrieval 尚未实现，`/memory/query` 不能返回 `MemoryAtom`，阻塞真实查询演示。
2. flow 和 sync 尚未实现，阻塞记忆流转、配对、节点状态和解绑的真实联调。
3. D-Bus 尚未实现，阻塞 D-Bus transport；HTTP/WS 仍是当前联调路径。
4. `source_evidence` 只有 ID，尚无证据详情/原文读取端点。
5. 尚无偏好列表端点，当前只有提取和指定 ID 的历史。
6. `GET /conflicts` 的分页、排序、状态筛选和单条详情仍未定义。
7. 配对令牌生成、二维码内容、有效期和过期错误语义仍未定义。
8. WebSocket 代码虽已进入仓库，仍需后端启动级冒烟验证后再作为稳定依赖。

## 4. 实施原则

1. 一个可独立验收的 feature 或组件对应一个 commit，不跨组件堆积提交。
2. UI 线程不得执行阻塞网络、进程等待或 SDK 调用。
3. UI 只依赖服务接口和前端模型，不在 Widget 内直接拼 URL 或 JSON。
4. 危险操作（遗忘、设备解绑）必须二次确认。
5. 后端不可用时展示明确离线态；请求失败后保留用户输入并允许重试。
6. 生产运行路径不得内置“假成功”或自动 mock 后端。UI 单元测试可使用显式 fake transport/
   JSON fixture，但测试替身不得进入生产配置。
7. JSON 解析对未知字段和未知 WebSocket 事件保持兼容。
8. 颜色、字体、图标和 DPI 尽量跟随 UKUI，不硬编码单一主题值。
9. 每个提交前检查 `git diff` 和 `git status`，只精确暂存本 feature 文件。

## 5. 分阶段、按 feature 的实施计划

日期仅为目标窗口；完成状态以独立 commit、验证记录和依赖门禁为准。

### Phase 0：同步、契约和环境基线（已完成本轮对齐）

- [x] 同步 `feature/frontend`，确认工作区基线。
- [x] 初始化两个官方 SDK submodule，并核对 gitlink。
- [x] 重读根规范、项目计划/API、全部前端文档及 foundation 最新文档/实现。
- [x] 记录 REST、WebSocket、D-Bus 当前实现状态与职责边界。
- [x] 在具备目标工具链的环境补齐 Qt5/CMake/C++ 版本与构建记录。

### Phase 1：应用基础

#### Phase 1A — Qt5/CMake scaffold（已完成，未完成真实编译验证）

- Commit：`9cebaa8 chore(frontend): scaffold Qt5 application`
- 内容：目录、`CMakeLists.txt`、`main.cpp`、资源占位、`PIXIU_HAVE_KYSDK` 选项。
- 验证记录：OFF 路径 configure/build/ctest 已通过（2026-08-08，Linux + Qt 5.15）；
  ON 路径自 Phase 7.1 起接入 kysdk-shortcut，并在本机（Kylin V11）验证通过。

#### Phase 1B — PixiuApp application lifecycle（下一 feature）

- 新建 `src/app/PixiuApp.{h,cpp}`，由其拥有后续顶层服务和窗口。
- 将启动与退出流程从 `main.cpp` 收敛到应用生命周期对象。
- 验证正常启动、事件循环和干净退出。
- Commit：`feat(frontend): add application lifecycle`

#### Phase 1C — 单实例守护

- 独立实现重复启动检测和已有实例激活通道。
- 覆盖正常启动、重复启动、异常退出后再次启动。
- Commit：`feat(frontend): add single-instance guard`

#### Phase 1D — 系统托盘与退出入口

- 添加托盘显示/隐藏、打开主入口和显式退出动作。
- 不在本提交实现悬浮球或桌面通知服务。
- Commit：`feat(frontend): add system tray integration`

#### Phase 1E — 基础配置持久化

- 用 `QSettings` 保存必要的应用级设置，不提前写入窗口业务配置。
- 不提交本机生成的配置文件。
- Commit：`feat(frontend): add application settings`

### Phase 2：静态交互入口

每一项单独实现、验证和提交：

1. `FloatingBall` 基础显示与拖动：`feat(frontend): add draggable floating ball`
2. 悬浮球贴边和位置恢复：`feat(frontend): persist floating ball position`
3. `ChatWindow` 显示/隐藏及焦点：`feat(frontend): add chat window shell`
4. `InputBar`：`feat(frontend): add chat input bar`
5. `MessageList` 与消息模型：`feat(frontend): add chat message list`
6. 开发态快捷键适配：`feat(frontend): add shortcut manager`

本阶段不接后端，不生成自动“假答案”。可用显式测试数据做 Widget 测试。

### Phase 3：HTTP 查询客户端与证据展示

1. 建立传输接口、错误类型和连接状态模型：
   `feat(frontend): add backend transport interface`
2. 实现 HTTP transport：`feat(frontend): add HTTP backend transport`
3. 定义并测试 `MemoryAtom` JSON 解析，容忍未知字段：
   `feat(frontend): add memory response models`
4. 实现查询加载/离线/超时/取消/重试 UI：
   `feat(frontend): add memory query states`
   - 追加（2026-08-08）：失败提示行增加“重试”按钮
     （`feat(frontend): add retry button for failed queries`），点击以原输入
     重新提交，输入不丢失；OFF/ON 两路径 ctest 20/20 通过，真实桌面启动冒烟正常。
5. 实现 `EvidenceCard`：`feat(frontend): add evidence card`
6. retrieval 落地后接通真实 `/memory/query`：
   `feat(frontend): connect memory query flow`

真实端到端验收受 `/memory/query` 占位阻塞。阻塞期间只允许测试专用 fake transport，生产
程序必须呈现明确的 `not_implemented`/不可用状态。

### Phase 4：写入、WebSocket、通知和遗忘

1. 对接已实现的 `/memory/write` 文本写入：`feat(frontend): add memory write flow`
2. 增加图片拖入与录入预览：`feat(frontend): add memory import preview`
3. [x] 实现 WS 连接、控制事件、未知事件兼容和退避重连：
   `feat(frontend): add websocket event client`
   - 本地验收通过（2026-08-08：CMake configure/build 成功，Qt5WebSockets 已链接）。
   - 真实环境验收阻塞：Module C 需修复 `/events` 注册与 WebSocket 导入问题
     （见 `frontend/docs/BACKEND_ISSUES.md`），修复后再做连接/心跳/`memory_ready`
     冒烟验证。
4. 将已接入的 `memory_ready` 映射到应用状态：
   `feat(frontend): handle memory ready events`
   - [x] 本地验收通过（2026-08-08：编译通过；ctest 2/2 通过；offscreen 冒烟启动
     正常，WS 连接状态与退避重连日志符合预期）。
   - 真实环境端到端（连接 `/events` 收到真实 `memory_ready`）仍依赖 Module C 修复
     `/events` 注册与 WebSocket 导入问题（见 `BACKEND_ISSUES.md`）。
5. [x] 实现桌面通知抽象及普通 Qt 降级：
   `feat(frontend): add desktop notification service`
   - 本地验收通过（2026-08-08：编译通过；ctest 3/3 通过；offscreen 冒烟无托盘
     降级路径正常，不崩溃）。Phase 7 再接入 kysdk-notification。
6. [x] 实现 `/forget` 两段式确认：`feat(frontend): add forget confirmation flow`
   - 本地验收通过（2026-08-08：编译通过；ctest 5/5 通过；offscreen 冒烟正常）。
   - 真实联调需后端 `/forget` 可用（已实现），无 Module C 阻塞项。

`conflict_detected`、`forget_confirmation` 和 `sync_event` 只有在后端开始真实广播后才做
端到端验收；客户端事件分发可以先具备未知事件兼容能力。

### Phase 5：记忆管理

1. `MemoryPanel` 壳和 Tab 状态：`feat(frontend): add memory management panel`
   - [x] 本地验收通过（2026-08-08：编译通过；ctest 6/6 通过；offscreen 冒烟正常）。
2. [x] 偏好历史：`feat(frontend): add preference history view`
   - 本地验收通过（2026-08-08：编译通过；ctest 8/8 通过；offscreen 冒烟正常）。
   - 当前入口为偏好 ID 输入框；偏好列表接口落地后（Phase 5.4）改为列表选择。
3. [x] 冲突审计：`feat(frontend): add conflict audit view`
   - 本地验收通过（2026-08-08：编译通过；ctest 7/7 通过；offscreen 冒烟正常；
     后端不可达时降级为日志，不崩溃）。
4. 偏好列表：等待列表契约后独立实现。
5. 证据原文：等待详情契约后独立实现。

### Phase 6：设备同步管理

该阶段受 `foundation/sync` 和 `/sync/*` 占位阻塞。客户端侧非阻塞部分已完成
（2026-08-09），后端契约落地后按以下独立 feature 闭环：

1. [x] `SyncClient` 数据模型和 transport：`feat(frontend): add sync client`
   - transport 端点（pair/peers/status/revoke）已就绪，见
     `HttpBackendTransport`；客户端状态机见 `SyncController`（2026-08-09）。
2. [x] 节点列表：`feat(frontend): add peer list`
   - 同步 Tab 渲染节点（本机/在线/离线/上次同步/待同步），`not_implemented`
     如实呈现；真实数据等待 `/sync/peers` 落地（2026-08-09）。
3. [x] 同步状态：`feat(frontend): add sync status view`
   - 同步摘要行渲染共享域/在线数/待同步/对账时间/累计同步（2026-08-09）。
4. [x] PIN 配对：`feat(frontend): add device PIN pairing`
   - `PairDialog` 契约载荷与结果反馈已完成；真实闭环等待 `/sync/pair` 落地。
5. 二维码展示：等待令牌生成契约后 `feat(frontend): add device QR pairing`
6. [x] 解绑确认：`feat(frontend): add peer revoke flow`
   - `RevokeDialog` 二次确认 + `SyncController::revokePeer` 已就绪；真实闭环
     等待 `/sync/peers/{id}/revoke` 落地（2026-08-09）。

前端只管理配对和展示状态，不参与 CRDT 或传输实现。

### Phase 7：UKUI/KylinSDK 桌面集成

1. [x] Kylin 全局快捷键适配：`feat(frontend): integrate Kylin global shortcut`
   - 本地验收通过（2026-08-08，Kylin V11 本机，`PIXIU_HAVE_KYSDK=ON`）：
     编译通过；ctest 9/9 通过；offscreen 冒烟确认系统级全局快捷键注册、
     残留注册更新（异常退出后 `EXISTED`→`set`）与第二实例激活通道正常；
     退出清理与残留删除验证完成。
   - 真实按键触发（桌面会话中按下 `Ctrl+Alt+P` 拉起应用并唤起主窗口）
     仍需在带显示的麒麟桌面会话中人工复测。
2. [x] Kylin 通知适配：`feat(frontend): integrate Kylin notifications`
   - 本地验收通过（2026-08-08，Kylin V11 本机，`PIXIU_HAVE_KYSDK=ON`）：
     编译通过；ctest 9/9 通过；无头冒烟 `KNotifier::notify()` 返回有效 id、
     无崩溃（`isAvailable()=true`）；应用 offscreen 启动无回归。
   - 真实弹窗展示仍需在带显示的麒麟桌面会话中人工复测。
3. UKUI 主题实时跟随：`feat(frontend): follow UKUI theme changes`
   - [x] 本地验收通过（2026-08-08，Kylin V11 本机，`PIXIU_HAVE_KYSDK=ON`）：
     编译通过；OFF/ON 两路径 ctest 10/10 通过（新增 theme_service，固定测试
     无 KYSDK 降级路径）；offscreen 冒烟 `themeMode()` 返回深色时应用 UKUI
     深色 Palette、`UKUI theme following enabled`，应用无回归。
   - 后续修复：该库版本 `initThemeStyle()` 不自动连接主题变化信号，已直连
     `ThemeController::m_gsetting` 的 `changed` 信号并过滤 `styleName` 键后触发
     `changeTheme()`；KYSDK 链接显式补齐 `gsettings-qt`
     （`fix(frontend): connect UKUI theme switch signal`）。
   - 追加修复（2026-08-08）：运行时探针确认 kysdk-qtwidgets 2.3.1.0 的
     `themeMode()`/`widgetTheme()` 只在 `initThemeStyle()` 时缓存一次，
     运行期切换主题不刷新（ukui-dark→ukui-light 后 `themeMode()` 仍为
     DarkTheme）；`applyTheme()` 改读 QGSettings 实时 `styleName` 判定明暗
     （含 dark/black/night 匹配，缺失时回退 `themeMode()`）
     （`fix(frontend): read live style name for UKUI theme following`）。
   - 真实桌面验证（2026-08-08，本机 Kylin V11 实时 UKUI 会话，XWayland）：
     应用启动后 `gsettings set org.ukui.style style-name ukui-light` 触发
     `restored system palette (light theme)`，切回 `ukui-dark` 再次应用
     深色 Palette；日志与截图证据留存。
4. UKUI 悬浮/拖动/窗口能力：`feat(frontend): integrate UKUI window helpers`
   - [x] 本地验收通过（2026-08-08，Kylin V11 本机，`PIXIU_HAVE_KYSDK=ON`）：
     编译通过；OFF/ON 两路径 ctest 11/11 通过（新增 ukui_window）；offscreen
     冒烟 `UKUI window shadow applied, radius: 12`，应用无回归。
   - 悬浮球保持自绘圆形实现（拖动/贴边依赖精确 56px 几何；`KDragWidget` 为
     文件拖拽控件，不适用于窗口拖动），UKUI 窗口装饰收敛在 `UkuiWindow` 适配层。
5. 高 DPI 与多屏：`fix(frontend): support high DPI and multiple screens`
   - [x] 本地验收通过（2026-08-08，Kylin V11 本机）：
     编译通过；OFF/ON 两路径 ctest 11/11 通过；offscreen 冒烟启动无回归；
     悬浮球/聊天框定位按屏幕可用区域钳制（代码审查确认）。
6. `.desktop`：`feat(frontend): add desktop entry`
   - [x] 本地验收通过（2026-08-08，Kylin V11 本机）：
     `desktop-file-validate` 无错误/提示；`cmake --install` 安装到临时前缀
     验证 `bin/pixiu-frontend` 与 `share/applications/com.kylin.pixiu.desktop`
     路径正确；OFF 路径 ctest 11/11 通过。
7. `.deb` 打包：`build(frontend): add Debian packaging`
   - [x] 本地验收通过（2026-08-08，Kylin V11 本机）：
     `scripts/build-deb.sh`（KYSDK=ON Release）产出
     `build/dist/pixiu-frontend_0.1.0-1_amd64.deb`；`dpkg-deb -I/-c` 校验
     control、postinst、`/usr/bin/pixiu-frontend` 与 desktop 路径正确；
     `debian/rules binary` 委托路径可用。

每项需在目标银河麒麟/UKUI 环境验证；不得以 Windows 降级路径代替适配结论。

### Phase 8：验收与发布候选

- 查询、写入、遗忘、冲突、同步的正常/空/离线/超时路径回归。
- WebSocket 断线、重连、心跳、未知事件和重复事件回归。
- 键盘可达、明暗主题、高 DPI、多屏和 x86/ARM 目标机验证。
- 形成 D-08 麒麟适配记录、演示说明和已知问题清单。
- 每类修复仍按一个可复现问题一个 commit，避免发布前大包提交。

已完成的本地自动化基线：

- `scripts/regression.sh`：OFF/ON 双路径 configure + build + ctest（offscreen）
  + ON 路径冒烟 + `desktop-file-validate` + `.deb` 打包与 `dpkg-deb` 内容校验。
- i18n 回归：`t_i18n` 校验内嵌 `pixiu_en_US.qm` 可从 qrc 加载并对
  `ChatWindow`/`InputBar`/`ForgetDialog`/`MessageList` 等上下文生效。
- WebSocket 重连回归：`t_websocket_client` 覆盖断线后按退避策略重连、心跳
  与未知事件兼容（不崩溃）。

## 6. 构建与验证门禁

### 6.1 当前真实验证结果

2026-08-07 在当前 Windows 环境探测：

```text
cmake=MISSING
qmake=MISSING
g++=MISSING
clang++=MISSING
cl=MISSING
```

因此目前只有目录、源码和 CMake 文件的静态检查；没有成功的 configure/build/run 结果。

### 6.2 工具链补齐后的最小验证

在仓库根目录执行：

```bash
cmake -S frontend -B frontend/build -DPIXIU_HAVE_KYSDK=OFF
cmake --build frontend/build --parallel
```

随后启动构建产物，检查应用事件循环和退出码。目标麒麟环境还需分别验证
`PIXIU_HAVE_KYSDK=OFF` 与 `ON`。`frontend/build`、CMake 缓存和可执行文件不得提交。

每个 feature 至少完成：

- configure/build；若因环境缺失无法执行，明确写出命令、缺失依赖和未验证项；
- 正常路径与至少一个错误/边界路径；
- QObject 所有权、信号槽、异步取消和退出流程检查；
- `git diff --check`、`git diff`、`git status`；
- 确认只修改 `frontend/` 且没有生成物、缓存、`.env` 或绝对路径。

### 6.3 本地验证记录（2026-08-08，Linux + Qt 5.15）

```text
cmake --version       3.28.3
Qt5WebSockets_DIR     /usr/lib/x86_64-linux-gnu/cmake/Qt5WebSockets
链接库                libQt5WebSockets.so.5.15.19
构建产物              frontend/build/pixiu-frontend（含 WebSocketClient.cpp.o）
测试                  ctest 8/8 通过（websocket / floating_ball / notify /
                     forget_controller / forget_dialog / memory_panel /
                     conflict_controller / preference_controller）
```

2026-08-08 追加（Phase 7.1，本机银河麒麟 V11）：

```text
PIXIU_HAVE_KYSDK=ON  configure 通过（pkg-config kysdk-shortcut 3.0.1.0）
构建产物              frontend/build/kysdk/pixiu-frontend（链接 libkysdk-shortcut）
测试                  ctest 9/9 通过（新增 shortcut_manager）
冒烟                  offscreen 启动：registered/updated Kylin global shortcut
                     Ctrl+Alt+P -> <binary>；第二实例 exit=1 并触发主实例激活；
                     SIGTERM 残留后再次启动走 EXISTED→set 更新路径；
                     退出后 kdk_shortcut_delete_global_shortcut 清理成功
```

2026-08-08 追加（Phase 7.2，本机银河麒麟 V11）：

```text
KYSDK 通知               kysdk-notification KNotifier（libkysdk-notification 3.0.1.0）
无头冒烟                 NotifyService(KYSDK) notify() 返回有效 id、无崩溃；
                         isAvailable()=true
应用冒烟                 offscreen 启动无回归（快捷键注册 + 通知服务挂载正常）
```

2026-08-08 追加（Phase 7.3，本机银河麒麟 V11）：

```text
KYSDK 主题               kysdk-qtwidgets ThemeController（libkysdk-qtwidgets 2.3.1.0）
OFF 路径                 configure/build 通过；ctest 10/10 通过（新增 theme_service）
ON 路径                  configure/build 通过（链接 kysdk-qtwidgets）；ctest 10/10 通过
无头冒烟                 offscreen 启动：themeMode() 返回深色时应用 UKUI 深色 Palette；
                         pixiu.theme: UKUI theme following enabled；无回归
```

2026-08-08 追加（Phase 7.4，本机银河麒麟 V11）：

```text
KYSDK 窗口辅助           kysdk-qtwidgets KShadowHelper（libkysdk-qtwidgets 2.3.1.0）
链接修复                 KYSDK 链接显式补齐 gsettings-qt（themeController 依赖）
OFF 路径                 configure/build 通过；ctest 11/11 通过（新增 ukui_window）
ON 路径                  configure/build 通过；ctest 11/11 通过
无头冒烟                 offscreen 启动：UKUI window shadow applied（radius 12）；
                         主题信号连接正常；无回归
```

2026-08-08 追加（Phase 7.5，本机银河麒麟 V11）：

```text
高 DPI                   入口启用 AA_EnableHighDpiScaling / AA_UseHighDpiPixmaps
OFF 路径                 configure/build 通过；ctest 11/11 通过
ON 路径                  configure/build 通过；ctest 11/11 通过
无头冒烟                 offscreen 启动无回归；定位逻辑按屏幕可用区域钳制
```

2026-08-08 追加（Phase 7.6，本机银河麒麟 V11）：

```text
桌面入口                 resources/com.kylin.pixiu.desktop（desktop-file-validate 通过）
安装规则                 GNUInstallDirs：bin/ + share/applications/
安装验证                 cmake --install --prefix <temp> 产出两文件路径正确
测试                     ctest 11/11 通过
```

2026-08-08 追加（Phase 7.7，本机银河麒麟 V11）：

```text
打包方式                 dpkg-deb --build（本机无 debhelper）；rules 委托脚本
产物                     build/dist/pixiu-frontend_0.1.0-1_amd64.deb（88 KB）
内容校验                 dpkg-deb -I/-c：control/postinst/usr/bin/desktop 正确
依赖声明                 libqt5widgets5t64/libqt5network5t64/libqt5websockets5/
                         libkysdk-shortcut/libkysdk-notification/libkysdk-qtwidgets/
                         libgsettings-qt1
```

2026-08-08 追加（i18n + Phase 8 本地自动化基线，本机银河麒麟 V11）：

```text
i18n                     全部用户可见文案 tr() 包装；en_US.ts/.qm 内嵌 qrc；
                         LANGUAGE/LANG/系统语言检测（main.cpp）
翻译内容                 pixiu_en_US.ts：12 个上下文、0 个未完成条目
回归脚本                 scripts/regression.sh（OFF/ON 构建+ctest+冒烟+deb 校验）
OFF 路径                 configure/build 通过；ctest 20/20 通过（含新增 i18n）
ON 路径                  configure/build 通过；ctest 20/20 通过
ON 冒烟                  offscreen 启动：PIXIU application started；
                         theme/ukui-window/shortcut 日志正常
打包                     build/dist/pixiu-frontend_0.1.0-1_amd64.deb（93 KB）
                         dpkg-deb -I/-c 校验通过
```

2026-08-08 追加（Phase 7.3 真实桌面验证 + Phase 8 真实桌面冒烟）：

```text
修复                      ThemeService::applyTheme() 改读 QGSettings 实时
                          styleName 判定明暗（themeMode() 仅缓存启动值，
                          运行期不刷新——运行时探针确认）
真实桌面启动              DISPLAY=:0 QT_QPA_PLATFORM=xcb 启动成功：
                          wmctrl -l 可见 "PIXIU" 窗口；托盘图标、UKUI 阴影
                          （radius 12）、全局快捷键注册/更新日志正常
主题实时跟随              ukui-dark -> ukui-light：restored system palette
                          (light theme)；切回 ukui-dark：applied UKUI dark
                          palette；桌面截图留存（/tmp/pixiu-verified-*.png）
回归确认                  OFF/ON 双路径 configure/build 通过；ctest 20/20
```

2026-08-08 追加（ImportDialog 测试补强）：

```text
t_import_dialog           新增 5 例：OK 按钮门控、确认载荷与清空、取消/Esc
                          隐藏、图片拖入预览与载荷；OFF/ON ctest 21/21
```

2026-08-08 追加（Phase 8 真实桌面收尾，本机 Kylin V11 实时 UKUI 会话）：

```text
第二实例激活              第二实例 exit=1；主实例日志 "activation requested
                          by secondary instance"；wmctrl 出现两个 PIXIU
                          窗口（悬浮球 + 聊天框）
                          （截图 /tmp/pixiu-phase8-04-second-activation.png）
通知弹窗                  测试专用 WS 桩（scripts/ws_smoke_server.py）驱动
                          memory_ready："memory ready: knw_smoke_001" +
                          "kysdk notification sent, id: 5"
                          （截图 /tmp/pixiu-phase8-05-notification.png）
窗口阴影                  "UKUI window shadow applied, radius: 12" +
                          聊天框截图供人工确认视觉效果
快捷键按键触发            注册 API 成功、dconf 配置正确（custom0 的
                          name/binding/action），但运行期 kglobalaccel
                          查询 Ctrl+Alt+P 返回 ENXIO（未加载 grab）；
                          uinput 合成按键（合成器已挂载虚拟键盘）未触发；
                          判定需全新登录会话/合成器重启后人工复测
```

WebSocketClient 的 configure/build 已通过；启动与真实 WS 连接验收仍受 Module C
两项后端问题阻塞（`/events` 注册、`ws.py` WebSocket 导入），详见
`frontend/docs/BACKEND_ISSUES.md`。`memory_ready` 事件映射与角标联动已通过本地
测试与冒烟验证，端到端真实事件仍待 Module C 修复后复测；Module A 侧已用
测试专用 WS 桩完成 UI 链路冒烟（见上文记录）。

2026-08-09 追加（同步管理 UI + WS 业务事件路由，OFF 路径本机验证）：

```text
同步管理                SyncController（peers/status/revoke 在途防重、占位/未知
                        响应如实上报）；MemoryPanel 同步 Tab 节点列表/摘要/刷新/
                        解绑入口；RevokeDialog 二次确认（默认取消、Esc 取消）
事件路由                EventRouter：conflict_detected/forget_confirmation/
                        sync_event → 通知/角标/面板刷新/远端遗忘确认；
                        memory_ready 行为迁移至路由层且语义不变
传输契约                BackendTransport::peersResult 携完整响应体，占位态
                        {"status":"not_implemented"} 与成功态 {"peers":[...]}
                        可在客户端正确区分（不伪造成功）
i18n                    pixiu_en_US.ts 增补同步/解绑/事件路由文案（127 条，0 未完成）
测试                    OFF 路径 ctest 26/26 通过（新增 t_sync_controller /
                        t_revoke_dialog / t_event_router；扩展 t_memory_panel /
                        t_forget_controller）
冒烟                    offscreen 启动 "PIXIU application started" 无回归
提交                    a330a6d feat(frontend): add sync peer list, status and
                        revoke flow
                        3fda460 feat(frontend): route websocket business events
                        to UI actions
```

2026-08-09 追加（设置入口与界面语言偏好，OFF/ON 本机验证）：

```text
设置对话框             SettingsDialog：跟随系统/中文/English、OK/取消/
                       Esc/关闭语义、关于与版本信息
入口接入               聊天框顶栏 ⚙（settingsButton）与悬浮球右键菜单
                       “设置”（settingsAction）→ PixiuApp::openSettings
持久化                 AppSettings::keyLanguage 仅 accepted 后写入；
                       main.cpp 启动时按 en_US / zh_CN / 跟随系统 选择翻译
i18n                   pixiu_en_US.ts 增补 SettingsDialog/ChatWindow/
                       FloatingBall 条目（142 条，0 未完成），.qm 重新生成
测试                   OFF/ON 双路径 ctest 27/27 通过（新增
                       t_settings_dialog 7 例；扩展 t_chat_window /
                       t_floating_ball / t_i18n）
冒烟                   offscreen 启动 "PIXIU application started" 无回归
提交                   feat(frontend): add settings dialog and language
                       preference（文档随 feature 提交一并更新）
```

2026-08-09 追加（加载失败态与重试，OFF/ON 本机验证）：

```text
失败态区分             MemoryPanel 冲突/偏好历史 Tab：空结果与加载失败
                       分开呈现；失败原因 + “重试”按钮；成功加载自动隐藏
应用层                  ConflictController::failed / PreferenceController::
                       failed → setConflictsError / setPreferenceHistoryError；
                       preferenceRetryRequested 以最近一次 ID 重发
i18n                   pixiu_en_US.ts 增补 MemoryPanel/PixiuApp 条目
                       （147 条，0 未完成），.qm 重新生成
测试                   OFF/ON 双路径 ctest 27/27 通过（t_memory_panel
                       新增失败态/重试/恢复 4 例；t_i18n 扩展）
冒烟                   offscreen 启动 "PIXIU application started" 无回归
提交                   feat(frontend): distinguish load failure from empty
                       state with retry（文档随 feature 提交一并更新）
```

2026-08-09 追加（全局快捷键自定义，OFF/ON 本机验证）：

```text
设置页                 SettingsDialog 新增 QKeySequenceEdit（默认 Ctrl+Alt+P，
                       需含 Ctrl/Alt/Meta 修饰键，否则“确定”禁用）
注册                  ShortcutManager::registerToggleShortcut(sequence)：
                       空序列回退默认；KYSDK 与 Qt 降级路径统一使用自定义序列
持久化                 AppSettings::keyToggleShortcut（PortableText）
应用时                 PixiuApp 启动按已存序列注册；设置确认后序列变化时
                       释放旧注册并即时重注册
i18n                   pixiu_en_US.ts 增补 SettingsDialog 条目
                       （149 条，0 未完成），.qm 重新生成
测试                   OFF/ON 双路径 ctest 27/27 通过（t_shortcut_manager
                       新增自定义/回退/旧序列失效 3 例；t_settings_dialog
                       新增默认/回退/门控 4 例；t_app_settings / t_i18n 扩展）
冒烟                   offscreen 启动 "PIXIU application started" 无回归
                       （offscreen 下 KYSDK 注册失败按设计降级 Qt）
提交                   feat(frontend): make toggle shortcut customizable
                       in settings（文档随 feature 提交一并更新）
```

2026-08-09 追加（管理面板加载态与写入在途防重，OFF/ON 本机验证）：

```text
加载态                 MemoryPanel 冲突/偏好历史 Tab：“正在加载…”与空态/
                       失败态互斥；打开面板/刷新/重试/加载时进入，成功或
                       失败后自动切换回空态/列表/错误行
写入防重               WriteController::submit 在途返回 false；writeAccepted/
                       errorOccurred（仅写入在途）后清空忙态；空闲时通用
                       错误不再误报“录入失败”
应用层                 重复提交时聊天框提示“上一条记忆仍在写入…已跳过”
i18n                   pixiu_en_US.ts 增补 MemoryPanel/PixiuApp 条目
                       （151 条，0 未完成），.qm 重新生成
测试                   OFF/ON 双路径 ctest 27/27 通过（t_memory_panel
                       新增加载态 2 例；t_write_controller 新增防重/忙态
                       清理/空闲错误隔离 4 例；t_i18n 扩展）
冒烟                   offscreen 启动 "PIXIU application started" 无回归
提交                   feat(frontend): add management loading states and
                       write in-flight guard（文档随 feature 提交一并更新）
```

2026-08-09 追加（管理控制器防重 + 后端离线引导，OFF/ON 本机验证）：

```text
控制器防重             ConflictController::refresh / PreferenceController::
                       loadHistory 在途防重：重复调用被忽略；在途响应返回后
                       放行下一次；偏好历史过期响应不再误配到新请求
离线引导               后端 Disconnected/Error 时聊天框追加系统提示
                       “后端服务未连接，请先启动 PIXIU 后端服务后重试。”；
                       每次断线仅提示一次，恢复 Connected 后复位
i18n                   pixiu_en_US.ts 增补 PixiuApp 条目
                       （152 条，0 未完成），.qm 重新生成
测试                   OFF/ON 双路径 ctest 27/27 通过（t_conflict_controller /
                       t_preference_controller 各新增在途防重 1 例；
                       t_i18n 扩展）
冒烟                   offscreen 启动：连接探测失败 → connection state:
                       error → "offline guidance shown"；应用无回归
提交                   feat(frontend): guard management controllers against
                       duplicate in-flight requests
                       feat(frontend): guide user when backend service is
                       offline
                       docs(frontend): record management guards and offline
                       guidance（文档独立提交）
```

2026-08-09 追加（聊天框拖动与位置记忆，OFF/ON 本机验证）：

```text
拖动                    无边框聊天框 mousePress/mouseMove/mouseRelease：
                       按住空白区域拖动，子控件（顶栏按钮/输入栏）不干扰；
                       leaveEvent 清除拖动状态防残留
持久化                 拖动发射 moved(topLeft) → PixiuApp 写入
                       AppSettings::keyWindowGeometry（QRect）
恢复                    启动时读取并钳制到屏幕 availableGeometry
                       （同悬浮球策略），无记录时保持右下默认位
测试                   OFF/ON 双路径 ctest 27/27 通过（t_chat_window
                       新增拖动移动与信号 1 例；offscreen 平台改用合成
                       QMouseEvent 验证）
冒烟                   offscreen 启动 "PIXIU application started" 无回归
提交                   feat(frontend): make chat window draggable and
                       remember position（文档随 feature 提交一并更新）
```

2026-08-09 追加（周期健康探测 + 断点恢复后真实桌面复验，OFF/ON 本机验证）：

```text
健康探测               HttpBackendTransport 独立静默周期探测：GET /conflicts
                       （默认 10s，测试可注入短间隔）；仅 setConnectionState，
                       不广播 conflictsResult/errorOccurred；在途防重；显式
                       断开停止、连接恢复重启
效果                   后端中途挂掉：无需用户操作，数个探测间隔内顶栏转
                       “● 服务异常”并出现离线引导；后端事后启动：自动转回
                       “● 在线”（此前两种状态都需等下一次用户请求）
测试                   t_http_backend 新增 3 例（初始连接 / 掉线→自动恢复 /
                       探测静默不干扰控制器）；OFF/ON 双路径 ctest 28/28
冒烟                   offscreen 启动 "PIXIU application started" 无回归
桌面验证               本机实时 UKUI 会话：后端在线→杀后端→约 10s 无交互
                       自动转“服务异常”（OCR 与日志一致）→重启后端→约
                       10s 无交互自动转回“● 在线”
提交                   feat(frontend): probe backend health periodically
                       （文档随 feature 提交一并更新）
```

2026-08-09 追加（断点恢复会话真实桌面复验：英文路径 + WS 通知链路）：

```text
英文路径               本机实时 UKUI 会话 LANGUAGE=en_US 启动：translation
                       loaded for en_US；聊天框顶栏/状态/按钮/离线引导/
                       输入占位均为英文（Service error / Memory /
                       Backend service is offline… / Ask a question…），
                       与中文字体同渲染正常
WS 通知链路             scripts/ws_smoke_server.py 桩驱动 memory_ready：
                       connected → ping → business event memory_ready →
                       "memory ready: knw_smoke_reconn" →
                       "kysdk notification sent, id: 3"；悬浮球角标出现
                       （红点像素核对），与断线前验收行为一致，无回归
```

## 7. Git 工作流

所有工作遵循根目录 `AGENTS.md` 和 `HUMANS.md`：

1. 开工前确认分支必须是 `feature/frontend`，否则停止。
2. 同步前确认工作区干净；只使用不会产生额外 merge commit 的安全同步方式。
3. 一个 feature 对应一个逻辑 commit，只精确暂存该 feature 的文件。
4. commit 前后都检查 diff/status，禁止提交 build、缓存、密钥、`.env` 和 IDE 文件。
5. 使用 `feat(frontend):`、`fix(frontend):`、`docs(frontend):`、
   `build(frontend):` 等清晰前缀。
6. Agent 只完成本地 commit；`push`、PR、合并、发布由 Human 执行。
7. 不修改 `backend/`、`third_party` submodule 源码或根 API 契约。

## 8. 当前风险与依赖

| 风险/依赖 | 当前影响 | 处理方式 |
|---|---|---|
| Windows 缺少 Qt5/CMake/C++ 工具链 | scaffold 和后续 feature 无真实编译证据 | 尽快准备 Qt5.9+ 与 CMake，或在目标麒麟环境验证 |
| `/memory/query` 仍占位 | 查询 MVP 无真实结果 | 客户端与 UI 可用测试 fixture 验证；不在生产路径假成功 |
| `/sync/*` 和 flow 仍占位 | 同步/流转 UI 无法真实联调 | 延后真实集成，不猜测实现 |
| D-Bus 只有占位 | 暂不可作为主 transport | 先抽象接口并走 HTTP/WS，等待后端契约 |
| WS 启动级可用性未冒烟确认（`/events` 未注册 + `ws.py` WebSocket 导入缺失） | 实时事件联调有风险 | 已记录于 `BACKEND_ISSUES.md`，待 Module C 修复后共同复测 |
| 证据详情、偏好列表接口缺失 | 对应页面无法闭环 | 提交接口需求，由双方确认后再实现 |
| SDK/UKUI 版本与目标机差异 | Kylin 集成可能编译或行为不一致 | 使用适配层，并在真实 x86/ARM UKUI 环境留证 |
| 根/模块部分状态文档仍可能写“前端未开始” | 进度认知不一致 | 本文件以提交 `9cebaa8` 为事实基线；其他文档由对应负责人另行对齐 |

2026-08-09 断点恢复结论：Module A 可独立完成的功能已全部完成（最后一项为聊天框
拖动与位置记忆，提交 `4eb8377`）；剩余实现项全部被后端契约阻塞（偏好列表、证据
详情、同步真实数据、二维码配对令牌、`/memory/flow/promote` 上下文、WS 真实事件，
见 §1.2 与 `BACKEND_ISSUES.md`），不再为制造进度扩需求。下一阶段进入统一
UI/UX polish，待办已全部登记于 `frontend/docs/UI_UX_POLISH.md`（颜色语义化、
字号间距、图标、动效、布局），其后转人工验收项（全局快捷键新会话复测、
HiDPI/多屏与 x86/ARM 目标机、通知点击行为、配对对话框视觉）。

2026-08-10 追加（UI/UX Polish Round 2，OFF/ON 本机验证）：

```text
指针/焦点态             按钮与 Tab 统一 cursor:pointer；QPushButton:focus
                        描边取主题高亮色（styles.qss），键盘焦点可见且
                        明暗主题一致
顶栏稳定                ChatWindow 状态文案按最宽项设最小宽度，在线/连接中/
                        服务异常/离线切换不再引起右侧按钮抖动；设置/记忆/
                        关闭补 tooltip 与 accessibleName
危险对话框               ForgetDialog/RevokeDialog 打开默认聚焦“取消”，
                        回车即取消（Esc/关闭语义不变），防误触不可逆操作
导入提示                ImportDialog 占位文案改为“粘贴文本内容；也可拖入
                        图片作为附件预览…”，i18n 同步（152 条，0 未完成）
测试                    OFF/ON 双路径 ctest 28/28 通过（t_chat_window /
                        t_memory_panel / t_forget_dialog / t_revoke_dialog
                        扩展）；offscreen 冒烟无回归
截图                    离屏核对截图 frontend/docs/screenshots/
                        ui-polish-round2-2026-08-10/（12 张，offscreen）
提交                    feat(frontend): unify pointer/focus states and
                        stabilize chat top bar
                        feat(frontend): focus cancel on danger dialogs and
                        refresh import hint
                        docs(frontend): record UI/UX polish round 2
                        completion and screenshots
```

2026-08-10 追加（UI/UX Polish Round 3：长文案布局 + 指针/焦点收尾）：

```text
长文案换行                systemHint（离线引导/写入回执等）wordWrap + 300px
                         上限，与答案气泡同宽；证据卡同宽，长证据 ID 元信息
                         卡内换行——英文路径不再硬裁剪
指针光标                  QSS cursor:pointer 在当前 Qt 不支持（启动刷警告且
                         不生效），已移除；全部交互按钮显式 PointingHandCursor
焦点可见性                QPushButton:flat:focus 主题高亮描边，扁平按钮键盘
                         焦点不再丢失
对话框尺寸                SettingsDialog 固定尺寸改默认+最小（英文需要时随
                         sizeHint 增高，实测 en_US sizeHint 282 仍 400x330）；
                         PairDialog 最小宽 280
设备名省略                同步 Tab peerNameLabel 220px ElideRight，在线状态
                         不被长名挤出
测试                    OFF/ON 双路径 ctest 28/28 通过（t_message_list 新增
                        长系统提示换行/证据卡同宽 2 例；t_memory_panel 长设备
                        名省略 1 例；t_settings_dialog / t_pair_dialog /
                        t_forget_dialog / t_revoke_dialog 指针光标断言）；
                        offscreen 冒烟无回归，cursor QSS 警告清零
截图                    离屏核对截图 frontend/docs/screenshots/
                        ui-polish-round3-2026-08-10/（4 张，offscreen）
桌面复验                 本机实时 UKUI 会话 xcb 启动：主题/托盘/阴影/英文
                        i18n/离线引导/健康探测无回归；会话为 Wayland 合成器，
                        wmctrl 不可枚举窗口（真实桌面截图按 offscreen 记录）
提交                    feat(frontend): wrap long UI texts and complete
                        pointer focus polish
                        docs(frontend): record UI/UX polish round 3
                        completion and screenshots
```
