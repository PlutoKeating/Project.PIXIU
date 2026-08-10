# 模块 A · UKUI 桌面客户端 —— 开发任务书

> **模块**：A — UKUI 桌面客户端
> **目录**：`frontend/`
> **技术栈**：C++17 · Qt5 Widgets · KylinSDK
> **开发人员**：1人（Qt/C++ 桌面开发）
> **与后端契约**：`docs/API.md` 定义的 12 个端点

---

## 实现状态（2026-08-07）

- ❌ **尚未开始**：`frontend/` 目前仅有文档，尚无 `src/`、`CMakeLists.txt`、`resources/`。
- 后端可联调状态：`/memory/write`、`/preference/extract`、`/preference/{id}/history`、
  `/forget`、`/conflicts` 已实现真实逻辑；`/memory/query`、`/sync/*`、
  `/memory/flow/promote` 为占位（返回 `not_implemented`）。
- 开发基线：main（2026-08-07 已合入集成工作），契约以 `docs/API.md` 为准。

> 下文的文件清单为任务定义与优先级，全部为待实现项。

## 实现状态（2026-08-08 更新）

- 第一阶段~第三阶段及第四阶段的 i18n 已完成：全部用户可见文案经 Qt `tr()` 包装，
  `resources/i18n/pixiu_en_US.ts`/`.qm` 内嵌，应用入口按 `LANGUAGE`/系统语言加载英文翻译。
- 双路径（`PIXIU_HAVE_KYSDK=OFF/ON`）ctest 21/21 通过；自动化回归脚本
  `scripts/regression.sh`（OFF/ON 构建+测试、offscreen 冒烟、desktop 校验、`.deb` 校验）
  已纳入 Phase 8 本地基线。
- 查询失败提示行已带“重试”按钮（点击以原输入重新提交，输入保留），
  对应 `MessageList::appendQueryError`/`retryRequested` 与 `t_message_list` 用例。
- 键盘可达补强：ForgetDialog Esc/关闭触发取消（默认按钮为“取消”）、
  MemoryPanel Esc 隐藏、主要按钮/输入框 accessibleName，均已补测试。
- 空结果提示行已带“录入知识”引导按钮（点击打开录入对话框），
  对应 `MessageList::appendEmptyResult`/`importKnowledgeRequested` 与用例。
- 新增 `t_import_dialog`（按钮门控/确认载荷/取消/Esc/图片拖入预览），
  套件 21 例全绿。
- 悬浮球已带右键菜单（打开聊天框 / 记忆面板 / 退出），与托盘/聊天框
  入口统一接线。
- Phase 8 真实桌面收尾（2026-08-08）：第二实例激活通道、通知弹窗（测试
  专用 WS 桩驱动 `memory_ready` → KNotifier id 有效）、窗口阴影应用已在本机
  实时 UKUI 会话验证并截图留证；全局快捷键真实按键触发需在全新登录会话
  复测（当前运行会话未加载 grab，详见 `UKUI_ADAPTATION_REPORT.md` 第 5 节）。
- 新增测试专用 WS 事件桩 `scripts/ws_smoke_server.py`（仅用于前端 UI 事件
  冒烟，不参与生产路径；后端 `/events` 修复后以真实后端复测）。
- Phase 6 设备配对 UI 壳（非阻塞部分，2026-08-09）：新增 `PairDialog`
  （PIN/二维码方式切换、6 位 PIN 门控、Esc/取消语义、契约载荷
  `{"method","pin","token"}`）、记忆面板同步 Tab 配对入口与状态行，
  PixiuApp 已接线 `/sync/pair` 并如实呈现 `not_implemented`/网络错误/未知状态
  （仅契约 `paired` 判成功，不伪造成功）；窗口与托盘图标改用内嵌
  `pixiu.svg`；新增 `t_pair_dialog`/`t_app_icon`，套件由 21 增至 23 例全绿，
  双路径回归脚本（OFF/ON 构建 + ctest + offscreen 冒烟 + desktop 校验 + `.deb`）
  通过。真实配对闭环、节点列表/状态/解绑仍待 `foundation/sync` 契约落地。
- 进度与验证记录以 `frontend/docs/DEVELOPMENT_PLAN.md` 为准；真实桌面会话复测与
  x86/ARM 目标机验收仍需人工执行。

## 实现状态（2026-08-09 更新）

- 同步管理客户端与 UI（Phase 6 非阻塞部分）已完成：新增 `SyncController`
  （`/sync/peers`、`/sync/status`、`/sync/peers/{id}/revoke` 的请求状态机：
  在途防重、`not_implemented`/未知响应如实上报、仅契约成功态放行）与
  `RevokeDialog`（解绑二次确认：默认聚焦取消、Esc 视为取消）；记忆面板同步
  Tab 新增节点列表（本机/在线/离线/上次同步/待同步条数）、同步摘要
  （共享域/在线数/待同步/上次对账/累计同步）、刷新按钮与非本机设备“解绑”
  入口。`BackendTransport::peersResult` 改为携带完整响应体，客户端可区分
  占位态 `{"status":"not_implemented"}` 与成功态 `{"peers":[...]}`，不伪造
  节点或成功状态。
- WS 业务事件路由已完成：新增 `EventRouter`，将 `conflict_detected`（通知 +
  悬浮球角标 + 冲突列表刷新 + 面板可见时切冲突 Tab）、`forget_confirmation`
  （弹出 ForgetDialog，确认后经 `ForgetController::confirmRemote` 直接执行
  第二阶段）、`sync_event`（通知 + 同步刷新）映射为应用行为；`memory_ready`
  行为迁入路由层且语义不变。真实端到端广播仍待后端事件接入后复测。
- 测试套件 26 例全绿（OFF 路径本机验证）：新增 `t_sync_controller`（9 例）、
  `t_revoke_dialog`（5 例）、`t_event_router`（7 例），扩展 `t_memory_panel`
  （同步 Tab 刷新/节点渲染/解绑流/摘要/冲突 Tab 切换）与 `t_forget_controller`
  （远端确认第二阶段）。i18n `.ts` 增至 127 条、0 未完成，`.qm` 已重新生成。
- 仍被后端契约阻塞（记录待 Module C）：偏好列表、证据详情、二维码配对令牌、
  `/memory/flow/promote` 的上下文来源、真实配对闭环/节点真实数据/真实事件
  广播（见 `frontend/docs/DEVELOPMENT_PLAN.md` §1.3 与 §4 风险表）。
- 设置入口与界面语言偏好已完成（2026-08-09）：新增 `SettingsDialog`
  （跟随系统/中文/English 三选、OK/取消/Esc/窗口关闭语义、关于与版本信息），
  聊天框顶栏新增 ⚙ 设置按钮、悬浮球右键菜单新增“设置”项，统一经
  `PixiuApp::openSettings` 打开；语言偏好持久化到 `AppSettings::keyLanguage`
  （仅 accepted 后写入），`main.cpp` 启动时按显式偏好选择翻译（`en_US`
  强制英文、`zh_CN` 强制中文、未设置时按 LANGUAGE/系统语言回退），切换在
  下次启动时生效（对话框内如实提示）。新增 `t_settings_dialog`（7 例），
  扩展 `t_chat_window`/`t_floating_ball`/`t_i18n`，套件增至 27 例全绿
  （OFF/ON 双路径）；i18n `.ts` 增至 142 条、0 未完成，`.qm` 已重新生成。
- 冲突/偏好历史“加载失败 vs 空结果”区分与重试已完成（2026-08-09）：
  `MemoryPanel` 冲突 Tab 与偏好历史 Tab 分别呈现失败原因与“重试”按钮，
  成功加载后自动隐藏错误行（不再把后端不可达误显示为“暂无记录”）；PixiuApp
  在 `ConflictController::failed`/`PreferenceController::failed` 时把错误
  上抛到对应 Tab，并记录最近一次偏好 ID 供重试重发。`t_memory_panel` 新增
  失败态/重试/成功恢复 4 例，`t_i18n` 扩展；套件 27 例全绿（OFF/ON 双路径），
  i18n `.ts` 增至 147 条、0 未完成。
- 全局唤起快捷键自定义已完成（2026-08-09，对应 ARCHITECTURE §9“快捷键可在
  设置中自定义”与“设置持久化：位置/快捷键/语言”）：`SettingsDialog` 新增
  `QKeySequenceEdit`（默认 `Ctrl+Alt+P`，要求包含 Ctrl/Alt/Meta 修饰键，
  无修饰键时禁用“确定”）；`ShortcutManager::registerToggleShortcut` 支持传入
  `QKeySequence`（空序列回退默认），`AppSettings::keyToggleShortcut` 持久化
  PortableText；`PixiuApp` 启动时按已存序列注册，设置页确认后若序列变化则
  释放旧注册并按新序列即时重注册。`t_shortcut_manager` 新增自定义序列/
  空值回退/旧序列不再触发 3 例，`t_settings_dialog` 新增默认/回退/门控 4 例，
  `t_app_settings`/`t_i18n` 扩展；i18n `.ts` 增至 149 条、0 未完成。
- 管理面板加载中状态与写入在途防重已完成（2026-08-09）：冲突 Tab 与偏好
  历史 Tab 增加“正在加载…”态（与空态/失败态互斥，成功/失败后自动切换，
  打开面板/刷新/重试/加载时进入）；`WriteController::submit` 在途防重
  （在途时返回 false 不再重复提交），`writeFailed` 仅在写入在途时上抛
  （修复其他端点错误串扰为“录入失败”的问题），PixiuApp 对重复提交给出
  明确提示。`t_memory_panel` 新增加载态 2 例，`t_write_controller` 新增
  在途防重/忙态清理/空闲错误隔离 4 例，`t_i18n` 扩展；i18n `.ts` 增至
  151 条、0 未完成。
- 管理控制器在途防重与后端离线引导已完成（2026-08-09）：
  `ConflictController::refresh` 与 `PreferenceController::loadHistory`
  增加在途防重（避免重复请求，也避免偏好历史过期响应被误配到新请求）；
  后端未连接（`Disconnected`/`Error`）时聊天框追加系统提示，引导启动
  PIXIU 后端服务（每次断线仅提示一次，恢复在线后复位，避免刷屏）。
  `t_conflict_controller`/`t_preference_controller` 各新增 1 例，
  `t_i18n` 扩展；i18n `.ts` 增至 152 条、0 未完成。
- 聊天框拖动与位置记忆已完成（2026-08-09，ARCHITECTURE §5.2“记忆上次
  位置”）：无边框聊天框支持按住空白区域拖动（子控件不干扰按钮/输入），
  拖动结束经 `moved` 信号由 PixiuApp 持久化到 `AppSettings::keyWindowGeometry`
  （原已定义未用），启动时恢复并按屏幕可用区域钳制（与悬浮球策略一致）。
  `t_chat_window` 新增拖动移动与信号 1 例；套件 27 例全绿（OFF/ON 双路径）。
- Module A 独立功能全部完成或明确阻塞（2026-08-09）：剩余实现项均依赖后端契约
  （偏好列表/证据详情/同步真实数据/二维码令牌/flow/WS 真实事件），不再扩需求；
  进入统一 UI/UX polish 阶段，待办见 `frontend/docs/UI_UX_POLISH.md`。
- 统一 UI/UX Polish 基线已完成（2026-08-09）：设计令牌与语义色迁移、全局
  QSS 控件状态、主题感知图标（悬浮球网络标记/设置齿轮）、角标弹入呼吸与
  思考骨架屏、聊天框可拉伸与面板尺寸复核；OFF/ON 双路径回归通过，离屏渲染
  核对截图见 `frontend/docs/screenshots/ui-polish-2026-08-09/`。剩余项仅为
  人工复测与后端契约阻塞，不新增业务功能（详见 `UI_UX_POLISH.md`）。
- 周期健康探测已完成（2026-08-09，健壮性）：`HttpBackendTransport` 增加
  独立、静默的周期健康探测（GET /conflicts，默认 10s，测试可注入短间隔），
  仅驱动连接状态（Connected/Error），不广播 `conflictsResult`/
  `errorOccurred`，避免干扰冲突/写入/配对等控制器；在途防重（慢响应/黑洞
  不叠加请求），显式断开后停止探测。效果：后端中途挂掉或事后启动时，顶栏
  “● 在线/服务异常”与离线引导无需等下一次用户操作即自动刷新。新增
  `t_http_backend`（3 例：初始连接、中途掉线→自动恢复、探测静默），
  套件增至 28 例，OFF/ON 双路径回归 + `.deb` 校验通过；本机真实 UKUI
  桌面验证：杀后端后约 10s 无交互自动转“服务异常”并出现离线引导，重启
  后端后约 10s 无交互自动转回“● 在线”。
- 录入按钮 tooltip 文案修正（2026-08-09）：`InputBar` 📎 按钮 tooltip 由
  “录入图片/文件（后续 feature）”改为“录入图片/文件”——录入对话框（图片
  拖入预览 + MANUAL_CONFIG 载荷）早已实现，旧文案会误导用户；i18n
  `pixiu_en_US.ts` 同步更新（152 条、0 未完成），`.qm` 重新生成，
  OFF/ON 双路径回归通过。

---

## 实现状态（2026-08-10 更新）

- 快捷入口首击回归修复（2026-08-10）：修复聊天窗「未激活/刚唤起」时第一次
  直接点击 记忆/设置/录入/同步 chip 可能被当作“仅激活窗口”而失效的问题。
  `ChatWindow::showAndFocus` 唤起后在同步 `QApplication::setActiveWindow` 的
  基础上，于窗口映射完成后延迟 60ms 再 raise/activate 一次，保证首击直达
  控件；同时修复上次窗口位置整体位于屏外时恢复窗口不可见、导致快捷入口
  无法点击的问题（恢复位置统一按全部屏幕可用区域并集钳制）。新增
  `t_app_navigation`（含“窗口未激活时首击即可响应”回归）与
  `t_window_restore`（屏外几何恢复回归）两个端到端测试；真实桌面手动复验
  步骤固化为 `scripts/desktop_first_click_check.sh`（唤起聊天窗 → 焦点让给
  其他窗口 → 逐个 chip 首击并判定目标窗口出现）。OFF/ON 双路径构建 + ctest
  30/30 全绿 + offscreen 冒烟 + desktop-file-validate + `.deb` 打包与内容
  校验全部通过（2026-08-10 补充复跑，补齐提交时仅记录的 OFF 路径验证）；
  真实桌面首击复验脚本需在真实 UKUI 会话执行（本开发环境无 DISPLAY，
  维持 §6 人工复测记录）。
- 第一批主窗口细节补齐（2026-08-10 Round 6，详见 `UI_UX_POLISH.md`）：顶栏
  改为 Logo/应用入口 + 置顶/更多/关闭三个主题感知图标（`UiIcons` 新增
  pin/more/close/memory/sync/import/chat 图标），状态胶囊移入输入区左下角
  badge；欢迎页新增「您可以问我：」+ 4 张建议卡片（点击填入输入框），整体
  放入无边框滚动区；输入区改为多行输入（Enter 发送 / Shift+Enter 换行）+
  chip 快捷行（记忆/设置/录入/同步/更多，空间不足自动收缩进更多）+ 圆角
  输入卡片；修复运行时明暗换肤后 QSS `palette(role)` 不重新解析的问题
  （`ThemeService` 换肤后重设全局 stylesheet）。真实 UKUI 桌面截图：
  `docs/screenshots/ui-sidebar-real-2026-08-10/`（浅/深欢迎页、浅/深对话页、
  悬浮球+主窗口同屏）。OFF/ON 双路径回归 + ctest 28/28 全绿，i18n 180 条
  0 未完成。
- UI/UX Polish Round 2（2026-08-10）已完成：按钮/Tab 统一指针光标与焦点
  高亮描边（`styles.qss`）；聊天框顶栏状态文案固定最小宽度防止切换抖动，
  顶栏按钮补 tooltip/accessibleName；`ForgetDialog`/`RevokeDialog` 打开
  默认聚焦“取消”（回车即取消，Esc/关闭语义不变）；`ImportDialog` 占位文案
  改为“粘贴文本内容；也可拖入图片作为附件预览…”，i18n 同步。OFF/ON 双路径
  ctest 28/28 全绿，offscreen 冒烟无回归；离屏核对截图见
  `docs/screenshots/ui-polish-round2-2026-08-10/`。剩余项仍为人工复测与
  后端契约阻塞（见 `UI_UX_POLISH.md` §4-§6）。
- UI/UX Polish Round 3（2026-08-10）已完成：系统提示与证据卡长文案换行
  （`systemHint` wordWrap + 300px 上限、证据卡与气泡同宽），修复英文路径
  文案被列表视口硬裁剪；移除 QSS 中不生效的 `cursor: pointer`（当前 Qt 版本
  不支持且启动刷警告），全部交互按钮显式指针光标；扁平按钮焦点加主题高亮
  描边；`SettingsDialog` 固定尺寸改默认+最小（英文长提示可随内容增高）、
  `PairDialog` 最小宽 280；同步 Tab 长设备名 220px 行内省略。OFF/ON 双路径
  ctest 28/28 全绿，offscreen 冒烟无回归、cursor QSS 警告清零；离屏核对截图见
  `docs/screenshots/ui-polish-round3-2026-08-10/`；本机实时 UKUI 会话复验
  无回归。
- 真实 UKUI 桌面 UI 演示（2026-08-10）已完成：未改代码，用隔离演示桩
  （`frontend/scripts/demo_stub_server.py`）在真实桌面会话中打开全部主要界面并
  截图，覆盖悬浮球/角标/右键菜单、系统通知（冲突检测/记忆已沉淀）、聊天
  （空/思考/答案+证据/失败重试）、MemoryPanel（偏好/冲突/同步 的加载/已加载/
  空/失败重试）、配对/解绑/遗忘/录入/设置对话框，浅色与深色主题；真实桌面截图见
  `docs/screenshots/ui-demo-2026-08-10/`（36 张）。托盘图标在 Wayland 面板不
  渲染，以悬浮球右键菜单等价展示；程序保持运行待人工查看。
- 悬浮球自由拖拽与右下角初始位置（2026-08-10）：左键按住可拖拽到桌面任意
  位置，释放后停留在放置处（移除“贴边自动收起/悬停展开”行为，避免拖到边缘
  后小球自动缩成 1/3）；无保存位置时默认位于屏幕可用区域右下角（距边缘
  24px），拖拽后位置照常持久化并在下次启动恢复。`t_floating_ball` 新增
  单击唤起/拖拽移动/贴边不收起 3 例，套件 28 例全绿（OFF 路径本机验证；
  ON 路径待回归脚本复跑）。
- 侧边浮窗主视觉统一（2026-08-10）：聊天主窗口改为「窄而高的桌面侧边 AI
  助手」形态（默认 380×640、最小 320×480），顶栏加 PIXIU Logo 与状态胶囊，
  消息区新增欢迎空态（Logo + 问候 + 开始提问/录入知识/记忆面板 三个快捷
  动作，消息到达自动切换、清空后回到欢迎页），输入区改为圆角浅灰卡片 +
  主题高亮色胶囊发送按钮；`ThemeService` 在浅/深两套都应用 PIXIU 设计系统
  调色（浅色白/极浅灰、深色深灰蓝，Highlight 仍跟随 UKUI 系统主题），
  `styles.qss` 全面弱边框化（按钮/输入/列表/Tab/滚动条/菜单/工具提示），
  圆角令牌更新为窗口 16 / 卡片 10 / 气泡 12；记忆面板留白提升至 12px。
  新增 `t_chat_window` 欢迎空态/窄高形态/动作转发 3 例并更新记忆面板留白
  断言，套件 28 例全绿（OFF/ON 双路径构建 + ctest + offscreen 冒烟）；
  i18n `.ts` 增至 162 条、0 未完成，`.qm` 已重新生成；离屏渲染核对截图见
  `docs/screenshots/ui-sidebar-2026-08-10/`（浅/深主题欢迎页、消息流、
  记忆面板）。参考截图不在工作区，视觉方向按需求文字执行（弱边框、圆角、
  卡片感、留白），待参考图补充后可再做逐项微调。

## 开工要求（本地环境准备）

开始开发前，**必须先补齐仓库内的官方麒麟 SDK submodule**：

```bash
git submodule update --init --recursive
```

- `third_party/kylin-coreai-embedding` —— 文本向量化 SDK（C API）
- `third_party/libkysdk-vector-engine-client` —— 向量数据库客户端（C++/gRPC）

前端联调依赖后端 API，而后端 embedding 走真实麒麟 SDK，请先确保本地 submodule
齐全、并按 `backend/engine/kylin/cpp/README.md` 完成 SDK 绑定构建。

---

## 1. 模块概述

PIXIU 前端是运行在银河麒麟桌面（UKUI）上的原生交互入口。核心交互形态：

- **悬浮球（FloatingBall）**：常驻桌面，左键拖拽可移动到任意位置并停留在
  放置处，默认初始位于桌面右下角
- **聊天框（ChatWindow）**：全局快捷键唤起，提问→答案→证据卡完整流程
- **记忆管理面板（MemoryPanel）**：偏好/冲突/同步 三个管理 Tab
- **设备配对对话框（PairDialog）**：扫码/PIN 配对新设备

前端**不存储记忆、不做检索计算**，所有数据能力通过后端 API 获取。

---

## 2. 源文件清单与实现优先级

### 第一阶段：基础骨架

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `src/main.cpp` | ★★★ | 应用入口，注册全局快捷键，常驻托盘 |
| `CMakeLists.txt` | ★★★ | 构建文件，find_package Qt5 + pkg_check_modules KYSDK |
| `src/app/PixiuApp.{h,cpp}` | ★★★ | 应用生命周期管理、单例守护 |
| `src/app/ShortcutManager.{h,cpp}` | ★★★ | kysdk-shortcut 封装（全局快捷键唤起聊天框） |
| `src/services/ThemeService.{h,cpp}` | ★★ | UKUI 主题跟随（明/暗主题实时换肤） |
| `src/services/NotifyService.{h,cpp}` | ★★ | kysdk-notification 封装（事件通知弹窗） |

### 第二阶段：核心交互

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `src/widgets/FloatingBall.{h,cpp}` | ★★★ | 桌面悬浮球（KTranslucentFloor + KDragWidget），角标、左键自由拖拽 |
| `src/widgets/ChatWindow.{h,cpp}` | ★★★ | 聊天主窗口（无边框圆角浮层），顶栏（同步状态+设置+关闭） |
| `src/widgets/MessageList.{h,cpp}` | ★★★ | 对话气泡列表（用户气泡右对齐、答案气泡左对齐+证据卡） |
| `src/widgets/InputBar.{h,cpp}` | ★★★ | 输入框 + 发送按钮 + 图片拖入 |
| `src/widgets/EvidenceCard.{h,cpp}` | ★★★ | 检索结果证据卡（置信度+延迟+查看原文） |
| `src/services/MemoryClient.{h,cpp}` | ★★★ | 后端 IPC 通信（优先 D-Bus，回退 HTTP/WS） |

### 第三阶段：管理面板

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `src/widgets/MemoryPanel.{h,cpp}` | ★★ | 记忆管理面板（偏好/冲突/同步三 Tab） |
| `src/widgets/ForgetDialog.{h,cpp}` | ★★ | 遗忘二次确认对话框 |
| `src/widgets/PairDialog.{h,cpp}` | ★★ | 设备配对对话框（二维码/PIN 输入） |
| `src/services/SyncClient.{h,cpp}` | ★★ | 同步管理客户端（配对/节点/状态/解绑） |

### 第四阶段：完善

| 文件/资源 | 优先级 | 说明 |
|-----------|--------|------|
| `src/models/` | ★★ | 消息、记忆、偏好数据模型（QObject 派生） |
| `resources/icons/` | ★ | 图标资源（明/暗两套，跟随 UKUI 系统图标） |
| `resources/styles.qss` | ★ | QSS 样式（圆角、阴影、配色跟随主题） |
| `resources/i18n/` | ★ | 中/英文翻译（Qt .ts 文件）——已实现（2026-08-08） |

---

## 3. 与后端的接口契约

前端通过 **MemoryClient** 和 **SyncClient** 两个类封装所有后端通信。

### MemoryClient 接口

```cpp
class MemoryClient : public QObject {
    Q_OBJECT
public:
    // 构造函数：指定后端地址（自动探测 D-Bus 或 HTTP）
    MemoryClient(QObject *parent = nullptr);

    // 写入记忆
    void write(const QJsonObject &payload);           // → /memory/write
    // 混合检索
    void query(const QString &text,                     // → /memory/query
               const QJsonObject &contextHint);
    // 遗忘
    void forget(const QString &nlCommand,               // → /forget
                bool confirm = false);
    // 记忆流转
    void promote(const QString &source,                 // → /memory/flow/promote
                 const QStringList &contextIds);

signals:
    void answerReady(const QJsonObject &atom);      // 含 answer/source_evidence/confidence/latency_ms
    void writeAcknowledged(const QString &evidenceId, double qualityScore);
    void forgetReady(const QJsonObject &confirmation);  // 待确认或已执行
    void errorOccurred(const QString &code, const QString &message);
};
```

### SyncClient 接口

```cpp
class SyncClient : public QObject {
    Q_OBJECT
public:
    SyncClient(QObject *parent = nullptr);

    void pair(const QString &method, const QString &token);  // → /sync/pair
    void listPeers();                                         // → GET /sync/peers
    void syncStatus();                                        // → GET /sync/status
    void revokePeer(const QString &peerId);                   // → /sync/peers/{id}/revoke

signals:
    void peersUpdated(const QJsonArray &peers);    // 节点列表 + 在线状态
    void syncStatusChanged(const QJsonObject &st); // 待同步条数/上次对账
    void peerEvent(const QJsonObject &evt);        // 节点上下线事件
};
```

### WebSocket 事件订阅

`MemoryClient` 内部维护 WS 连接 `/events`，收到事件后发射信号供 UI 层响应：

| 后端事件 | 前端响应 |
|----------|----------|
| `memory_ready` | 悬浮球角标 +1 → 通知"记忆已沉淀" |
| `conflict_detected` | 通知 → 点击打开记忆面板冲突 Tab |
| `forget_confirmation` | 弹出 ForgetDialog（影响范围 + 确认/取消） |
| `sync_event` | 通知 → 同步 Tab 刷新 |

---

## 4. 关键状态与边界情况处理

| 场景 | UI 表现 |
|------|---------|
| 检索加载中 | 答案区骨架屏 + 顶栏细进度条 |
| 检索超时/失败 | 气泡红字提示 + "重试"按钮，输入不丢失 |
| 后端未连接 | 顶栏 "●离线" 标记，输入禁用，引导启动服务 |
| 空结果 | 友好空态文案 + "录入知识"引导按钮 |
| 敏感内容 | 录入预览标记 "含敏感信息，默认不同步" |
| 长答案 | 气泡可滚动，证据卡折叠默认收起 |
| 多设备同步中 | 同步 Tab 显示待同步条数和节点状态 |
| 遗忘操作 | 弹出 ForgetDialog 展示级联影响范围 → 确认后才执行 |

---

## 5. 开发降级方案

非麒麟开发机上：

1. **编译开关**：`cmake -DPIXIU_HAVE_KYSDK=OFF`
2. 降级表现：`FloatingBall` 用普通 `QWidget` + `QShortcut` 替代 kysdk 组件；`NotifyService` 用 `QSystemTrayIcon::showMessage` 替代 kysdk-notification
3. 后端：生产代码无 mock 降级，需要麒麟 SDK 绑定（见 `backend/engine/kylin/cpp/README.md`）；
   无 SDK 环境可先用后端测试桩数据联调 UI 布局
4. API 层自动回退：`MemoryClient` 检测无 D-Bus 时自动使用 `http://127.0.0.1:8765`

---

## 6. 参考文档

| 内容 | 路径 |
|------|------|
| 前端架构设计（完整 UI 线框、交互流程） | `frontend/docs/ARCHITECTURE.md` |
| API 端点契约（全部请求/响应结构） | `docs/API.md` |
| KylinSDK 全局快捷键 | `docs/kylin_sdk_docs/8_Desktop_Environment_SDK/8.3_Hotkey_Module.md` |
| KylinSDK 桌面通知 | `docs/kylin_sdk_docs/8_Desktop_Environment_SDK/8.2_Notification_Module.md` |
| KylinSDK 主题模块 | `docs/kylin_sdk_docs/8_Desktop_Environment_SDK/8.5_Theme_Module.md` |
| KylinSDK 悬浮/拖拽控件 | `docs/kylin_sdk_docs/4_Application_Support_SDK/4.1.13_KTranslucentFloor.md` 和 `4.1.14_KDragWidget.md` |
| 赛题附录 A（家庭支出场景） | `docs/OriginProblemDescription.md#附录-a典型应用场景家庭支出全局模糊检索` |
