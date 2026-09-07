# 模块 A · UKUI 桌面客户端 —— 开发任务书

> **模块**：A — UKUI 桌面客户端
> **目录**：`frontend/`
> **技术栈**：C++17 · Qt5 Widgets · KylinSDK
> **开发人员**：1人（Qt/C++ 桌面开发）
> **与后端契约**：`docs/API.md` 定义的 32 个 REST 端点 + WS

> [!IMPORTANT]
> 2026-09-03 赛题复核后，Module A 已完成状态仅指 PIXIU 记忆控制台范围，
> 不代表完整 OS Agent 已实现。团队已批准复用 openKylin `kylin-agent` +
> `agent-runtime` 承担多轮会话、规划、工具/Shell/联网搜索和审批；这不是赛方
> 指定技术路线。本模块后续只承担记忆管理 UI 与必要集成，
> 不在 `frontend/` 内另造 Agent 循环。

---

## 实现状态（2026-09-03 · v0.1.7 发布）

- ✅ 前端 CMake、编译宏与独立 Debian control 均直接从仓库根 `VERSION` 派生，
  不再维护前端静态产品版本副本。
- ✅ 真实 GitHub live 升级用例不再写死远端 `0.1.6`，只要求 latest 高于 `0.1.5`。
- 🟡 一键升级已实现 Ed25519 固定公钥验签、包名/版本/架构校验及安装后的
  dpkg、后端、schema、Provider 健康判定，失败不会误报成功；双架构 CI 签名资产及
  Kylin V11 有效/篡改签名已验证；自动回滚已通过双架构 CI 与 Kylin V11 amd64
  跨 revision 健康失败注入，旧版本、配置、核心数据和服务均恢复。
  受控前端重启已实现 Success 门控、无特权等待 helper、失败重试提示和有序退出，并
  通过控制器/UI/打包脚本测试。密钥轮换演练已完成；最终发布门尚缺可重建 Agent
  宿主/离线 Runtime 供应链、完整模型运行兼容矩阵与 V11 图形升级/重启证据。
  helper 使用 `dpkg-repack` + SQLite backup 实现旧包/数据恢复，详见
  `docs/DELIVERY_PLAN.md`，不得将现状表述为完整版本管理验收通过。
- ✅ 2026-09-03 修复非交互升级配置冲突：运行配置改由 postinst 从只读模板首装
  创建并在升级时保留；Kylin V11 portable 已从 `0.1.7-3` 跨 revision 到测试包
  `0.1.7-4`，离线依赖安装、配置/核心逻辑计数保留、服务恢复和 helper 健康均通过。

## 实现状态（2026-09-02 · v0.1.6 本机验收）

- ✅ 本机 GitHub 应用内升级闭环：`CheckUpdateDialog` + `UpgradeController`
  拉 `releases/latest`，下载/校验公开发布的 `0.1.6` amd64 包，经与生产相同
  的 `/usr/lib/pixiu/install-update` 参数完成安装。因已装版本等于 latest，
  验收把 `applicationVersion` 压到 `0.1.5` 才会进入 Updatable。无人值守
  会话用 `sudo -n` 替代图形 `pkexec`。当前用户 XDG 配置与
  `sync_identity.device_id` 安装前后一致，后端保持 active。
- ✅ 本机 `PIXIU_HAVE_KYSDK=ON`：ctest 37/37；offscreen 冒烟确认 UKUI 主题
  跟随、窗口阴影、麒麟全局快捷键 `Ctrl+Alt+P`，并连上本机 `pixiu-backend`。
- ✅ 可选验收：`PIXIU_LIVE_UPGRADE=1 PIXIU_LIVE_UPGRADE_INSTALL=1`
  `frontend/scripts/live-upgrade-accept.sh`（默认 ctest 跳过真实下载）。

## 实现状态（2026-09-01 · 0.1.6 发布候选）

- ✅ 应用内一键升级已完成并加固：按本机 Debian 架构严格选择同版本
  `.deb`/`.sha256`，流式 SHA-256 校验，HTTPS + GitHub 重定向白名单，
  有界下载、唯一临时文件，以及 `pkexec` 特权 helper 的 root-only 副本
  二次校验、`dpkg` 安装与启动失败诊断。
- ✅ 安装安全语义已收口：下载/校验阶段允许取消；进入 `dpkg` 后禁用取消和
  关闭，应用退出不杀死安装进程；界面明确提示系统授权及记忆、配置、同步身份
  保留策略。
- ✅ 发布流水线准备同时生成 amd64 与 arm64 资产；amd64 使用已验证的麒麟
  V11 依赖画像，arm64 暂用 Debian 通用画像，仍须在对应麒麟硬件上完成
  KYSDK 与安装升级验收。
- ✅ 版本已统一到 0.1.6；新增升级安全文案已纳入英文 i18n。

## 实现状态（2026-08-11）

- ✅ **独立功能与 UI/UX polish 全部完成**：悬浮球/侧边聊天窗/记忆面板/遗忘/
  录入/设置/配对/解绑/同步管理/WS 事件路由/偏好提取；i18n 180 条 0 未完成；
  双路径（KYSDK OFF/ON）ctest 31/31 全绿（含契约一致性测试
  `t_contract_fixtures`）；`.deb` 打包产物已在麒麟 V11 真机安装验证。
- 后端契约历史基线（2026-08-10 合入 main）：当时 12 个 REST 端点已实现，当前
  为 32 个（以 `docs/API.md` 为准），前端
  传输层与解析已按真实响应形状对齐；2026-08-11 起后端经 request_id 中间件统一
  返回 `{error, message, request_id}`，前端两种形状（`error`/`detail`）均兼容。
- 上述历史后端契约缺口均已关闭；剩余为最终 Kylin V11 图形会话、双架构、完整
  Agent、双 SDK 与多设备端到端人工验收。

> 下文的文件清单为任务定义与优先级；已实现项以"实现状态"与
> `frontend/docs/DEVELOPMENT_PLAN.md` 为准。

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
- Phase 6 设备配对前端切片（2026-08-09；后端闭环状态见本段末尾更新）：新增 `PairDialog`
  （PIN/二维码方式切换、6 位 PIN 门控、Esc/取消语义、契约载荷
  `{"method","pin","token"}`）、记忆面板同步 Tab 配对入口与状态行，
  PixiuApp 已接线 `/sync/pair` 并如实呈现 `not_implemented`/网络错误/未知状态
  （仅契约 `paired` 判成功，不伪造成功）；窗口与托盘图标改用内嵌
  `pixiu.svg`；新增 `t_pair_dialog`/`t_app_icon`，套件由 21 增至 23 例全绿，
  双路径回归脚本（OFF/ON 构建 + ctest + offscreen 冒烟 + desktop 校验 + `.deb`）
  通过。该历史切片当时等待 `foundation/sync`；相关契约已于 2026-08-29 全部落地。
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
- 本阶段曾等待 Module C 的偏好列表、证据详情、二维码配对令牌、
  `/memory/flow/promote` 上下文来源、真实配对/节点数据和事件广播；这些历史阻塞均已
  解除，当前状态见下方 2026-08-29 更新。

> 更新（2026-08-29）：上述后端契约阻塞已全部解除——偏好列表/证据详情/二维码
> 配对令牌于 2026-08-24 落地（`GET /preferences`、`GET /evidence/{id}`、
> `POST /sync/token`）；WS 事件广播 2026-08-20 修复（六类事件真实广播）；
> 真实配对闭环/节点真实数据随同步网络批次（2026-08-29）闭环（确认式配对 +
> 同步 Tab 全量管理）。
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
- 视觉验收以唯一宿主为对象；旧小窗口图库已撤下，不再作为已完成基线。
  当前主题、输入焦点、图标和全部控件仍须原生复验，范围见 `UI_UX_POLISH.md`。
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

本节按现行唯一宿主更新，不再保留旧小窗口截图、演示数据与视觉完成声明。

- 会话、记忆、设备、设置已经嵌入同一宿主；独立悬浮球不属于产品方向。
- 管理区具备文本录入/更新、证据读取、偏好审计、遗忘、设备管理、采集隐私、
  洞察简报及服务诊断入口；各项完整验收状态见根 `UNIFIED_FRONTEND_PLAN.md`。
- 图标、主题、焦点和桌面导航仍有待验收项。V11 菜单启动曾出现容器背景与文字
  冲突，修复已经补入宿主导出树，不能仅凭离屏回归宣称原生桌面全部通过。
- 本目录旧图库 77 张 PNG 已删除，子目录保留空占位。完整新图库必须基于真实
  安装包、实际公共接口及明确的数据状态重拍，不以演示桩替代。

## 实现状态（2026-08-10 契约对齐更新）

在 `feat/foundation` 分支后端已真实实现全部 REST 端点（2026-08-10）的前提下，
Module A 完成了第一轮"端口与用例对齐"工作（全程未修改 backend/）：

- **错误解析对齐 FastAPI 形状**：`parseBackendError` 兼容 `{"detail":"..."}`
  （HTTPException 404/422 等）与 `{"detail":[...]}`（Pydantic 校验）两种真实
  后端形状，错误码正确映射为 NOT_FOUND / INVALID_REQUEST 等，不再显示空白
  "HTTP_4xx"；`t_http_backend` 新增 detail/校验/旧契约三种错误用例。
  （2026-08-11：后端已统一为 `error` 契约，兼容逻辑保留并继续生效。）
- **契约级一致性测试**：新增 `tests/t_contract_fixtures.cpp`（ctest 第 31 项），
  以本地 TCP 桩模拟后端真实响应形状（取自 `backend/foundation/tests/test_api.py`
  与 `api/http_app.py`），覆盖 write/query/forget 两段式/conflicts/preference
  history/sync peers+status/pair+revoke/flow promote 共 8 组契约断言。
- **偏好提取接线**：`BackendTransport::extractPreferences`（默认空实现，测试桩
  无需改动）+ `HttpBackendTransport` POST `/preference/extract` +
  `PreferenceController::extract`（在途防重、空 evidence 忽略）+
  MemoryPanel 偏好 Tab“提取偏好”按钮（以最近一次成功写入的 evidence_id 为输入，
  成功/失败就地反馈）；`t_preference_controller` 新增 5 例，`t_memory_panel`
  新增 2 例。
- **配对 PIN 对齐后端契约**：`/sync/pair` 的 `token` 后端必填（min_length=1），
  PairDialog 新增“配对令牌”输入（与 6 位 PIN 双条件门控，缺令牌时禁用确认），
  载荷携带 token；`t_pair_dialog` 同步更新（令牌门控/载荷断言）。
- i18n 新增 7 条（偏好提取/配对令牌相关），`.ts` 180 条 0 未完成，`.qm` 已
  重新生成；`t_i18n` 增加“提取偏好”抽查。
- 本地验收：OFF 路径构建通过，ctest 31/31 全绿；offscreen 冒烟（演示桩 +
  真前端二进制）通过（WS 连接、memory_ready → 角标/通知链路）。

> 仍被后端契约阻塞、前端未推进：conflict_detected 与 forget_confirmation 真实
> 广播、配对令牌生成端点（QR/PIN 完整闭环）、偏好
> 列表/证据详情/flow 上下文来源端点。以上均需 Module C 侧落地（见
> `frontend/docs/BACKEND_ISSUES.md` 与 `DEMO_GUIDE.md` §3）。

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

当前执行 ADR-0006 的唯一前端迁移：`management/` 为嵌入 Agent 的自有 Qt 模块，
检索与证据正文查看已接线，范围切换会清除旧结果并忽略旧查询响应。已有控制台描述
属于待退役实现，不再是目标产品形态；设备、设置、写入、升级等仍须逐项迁移验证。
独立模块回归：`cmake -S frontend/management -B <build> -DPIXIU_MANAGEMENT_TESTS=ON`，
然后构建并运行 `ctest --test-dir <build> --output-on-failure`。

PIXIU 前端是运行在银河麒麟桌面（UKUI）上的原生交互入口。核心交互形态：

- **悬浮球（FloatingBall）**：常驻桌面，左键拖拽可移动到任意位置并停留在
  放置处，默认初始位于桌面右下角
- **聊天框（ChatWindow）**：全局快捷键唤起，提问→答案→证据卡完整流程
- **记忆管理面板（MemoryPanel）**：偏好/冲突/同步 三个管理 Tab
- **设备配对对话框（PairDialog）**：扫码/PIN 配对新设备

前端**不存储记忆、不做检索计算**，所有数据能力通过后端 API 获取。

---

## 2. 源文件清单与实现优先级

> ✅ 第一阶段~第四阶段均已实现（2026-08-11，ctest 31/31）。实际实现的文件
> 结构以 `src/` 为准：早期规划中的 `MemoryClient`/`SyncClient` 已由
> `services/BackendTransport`（抽象）+ `services/HttpBackendTransport` +
> `services/WebSocketClient` 取代，业务逻辑收敛到 `src/app/*Controller`。

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
| `src/services/BackendTransport.h`、`HttpBackendTransport.*` | ★★★ | 当前 HTTP/WS 通信；无前端 D-Bus 实现 |

### 第三阶段：管理面板

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `src/widgets/MemoryPanel.{h,cpp}` | ★★ | 记忆管理面板（偏好/冲突/同步三 Tab） |
| `src/widgets/ForgetDialog.{h,cpp}` | ★★ | 遗忘二次确认对话框 |
| `src/widgets/PairDialog.{h,cpp}` | ★★ | 设备配对对话框（二维码/PIN 输入） |
| `src/app/SyncController.{h,cpp}` | ★★ | 通过 BackendTransport 管理配对/节点/状态/解绑 |

### 第四阶段：完善

| 文件/资源 | 优先级 | 说明 |
|-----------|--------|------|
| `src/models/` | ★★ | 消息、记忆、偏好数据模型（QObject 派生） |
| `resources/icons/` | ★ | 图标资源（明/暗两套，跟随 UKUI 系统图标） |
| `resources/styles.qss` | ★ | QSS 样式（圆角、阴影、配色跟随主题） |
| `resources/i18n/` | ★ | 中/英文翻译（Qt .ts 文件）——已实现（2026-08-08） |

---

## 3. 与后端的接口契约

> 下方 `MemoryClient`/`SyncClient` 接口为早期规划示意；实际实现见
> `src/services/BackendTransport.h`（抽象 + HTTP/WS 实现）与
> `src/app/*Controller.h`（Query/Write/Forget/Conflict/Preference/Sync）。

前端通过 **BackendTransport** 抽象封装所有后端通信。

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

宿主显示名称与主窗口标题由 0016 导出补丁保持 PIXIU 产品身份，去掉启动入口的
旧标题覆盖；内部应用和组织身份不变。`0018` 将 desktop 身份修正为已安装启动项
`com.kylin.pixiu`；导出回归同时核对标识、启动项源文件与打包路径。该关联修复不修改
单实例或历史存储身份，也不作为导航异常的根因结论。导出回归校验各类名称各自用途，
不为修复显示名称迁移或删除用户配置。真实新包的窗口、对话框后缀与任务栏仍待验证。

设置页增加「服务与能力」只读诊断，串行读取健康、版本和能力公共接口；专用传输
避免错误信号串扰，任一步失败不返回成功快照。组件测试覆盖版本差异、可移植/原生
报告、未知 API、矛盾字段、错误信息脱敏、重复操作门控、关闭保护和旧结果清除；
HTTP 测试核对三条实际请求路径及中间失败后不继续读取。源码已加入管理 CMake、
宿主导出和供应链清单；未新增系统依赖，真实新包界面和完整状态订阅仍待验收。

共用 HTTP 健康探测改为 `/health` 的组件/就绪/数据库校验；五类畸形或未就绪响应
不会判在线，业务 HTTP 500 不覆盖健康失败。显式断开取消探测，旧业务回包不改变
新连接状态，重连仍可恢复。原 `t_http_backend` 已纳入管理模块 CMake 回归，覆盖
迟到响应和既有周期恢复/静默行为；测试服务器按连接只处理一次请求，避免把分段
请求数据误计为新请求。尚未实现唯一宿主的共用状态展示、版本与能力握手。

嵌入证据阅读默认展示文本正文及其余结构化字段，不再要求非文本证据先打开 JSON。
组件回归覆盖正文与附加字段共存、数组/布尔/空值、字面 HTML、原始数据往返及
来源/范围切换清空。大列表、深层对象和长文本在普通展示中有界展开并明确提示，
高级视图仍可读到完整末尾字段。实现复用既有 Qt Core/Widgets 与宿主导出文件，
没有新增系统依赖或独立窗口；真实安装后的长文、主题与来源跳转仍须验收。

管理范围选项统一使用 `MemoryScopes.h`，从正式入口传入的 Agent scope 增加明确
选项；录入只自动采用私有 Agent 域，不自动共享。组件测试覆盖本机域保留、同域
去重、非法范围忽略，以及查询、录入、偏好和遗忘预览实际发送自定义 Agent 范围。
随包配置引导器使用已有 Runtime 的 python-dotenv 依赖，只读解析 profile，不执行
shell、不传出 profile 凭证；配置冲突与读取失败拒绝启动。引导器及 Qt 测试不代替
真实安装、运行中 profile 切换与旧自定义范围数据可达性验收。

唯一宿主当前没有创建托盘，导出适配设置关闭最后一个可见窗口时退出，而不是
无托盘常驻。新增 `HostCloseGuard` 统一检查所属对话框、在途管理请求及采集/同步
配置编辑；默认取消退出，放弃不发写请求。组件回归覆盖取消、明确放弃、请求失败
保留、保存成功清除修改、嵌套关闭事件与所属对话框保护。隐藏后的 `--quit` 先恢复
主窗口再经过检查，导出断言保证接线。Agent 状态从宿主只读回调取得，回归覆盖
请求未结束时阻止关闭、草稿默认取消、明确放弃不改输入与确认期间请求状态变化。
记忆检索、来源证据、洞察和简报读取也纳入关闭检查；回归覆盖在途拒绝、无关查询
回包不能解锁、成功或失败后放行，以及升级放弃编辑确认期间新请求启动后的再次拒绝。
升级重启在调度 helper 之前复用检查，回归验证拒绝时无 helper/重启信号，通过后才
调度；仅排除发起重启的对话框，不跳过其他对话框。真实模型会话、托盘和图形升级
退出矩阵仍未完成，不能套用旧 PixiuApp 的验收结果。

嵌入升级入口复用现有升级状态机和对话框；管理模块构建同时运行原有升级工具、
控制器与对话框测试。唯一宿主使用产品版本比较 Release，成功后用户选择重启才退出
整个应用。此接线不替代新宿主的真实图形授权、安装升级和回滚验收。

嵌入隐私页新增加载前禁止保存、配置字段形状检查、绝对路径与目录去重、失败编辑
保留、未保存提示及日志分页。测试验证不可用来源的原配置值不会因保存其他选项而
被覆盖。真实采集运行与桌面能力降级仍须单独验证，不能仅依据配置响应标通过。

内嵌洞察/简报页覆盖请求互斥、空候选说明、标题检索信号、网络失败、非法简报日期
与有效摘要显示。日期选择器支持历史日（含闰日），按后端本地时区读取；切换日期/
重读清除旧摘要，在途禁用日期编辑，拒绝日期不匹配及失败后的迟到响应。
HTTP 回归检查显式日期、无参数默认路径和查询值编码。洞察依赖后端固定个人域和推荐抑制规则，简报仅聚合采集日志；
不得用这两个入口证明完整记忆数量或模型推理能力。真实桌面与数据联调仍需验收。
日期控件复用现有 Qt Widgets 依赖和管理库编译入口，无新增系统包或源文件；
管理/升级/HTTP 六组回归及正式宿主源码导出检查通过，不等同于真实桌面验收。

顶级导航已收拢为会话/记忆/设备/设置；设置页负责隐私、升级与原宿主配置入口。
测试断言记忆页不再拥有设备、隐私、升级控件，设置页保持嵌入式 QWidget 并发出
宿主配置请求信号。真实缩放、长文案和桌面导航操作仍待验证。
V11 严格 ON 安装版本 `8a7772b` 已经由产品入口重新启动，运行文件哈希与安装文件
一致；定向 X11 键盘操作进入服务诊断页后，实际读取显示后端就绪、产品版本一致、
API 0.5.0 / Agent API 1 / schema 12 与双麒麟运行适配器。此项不包含后续日期控件。
QMP 点击/普通键盘切页仍出现失败，X11 与截图指针坐标不一致，原因待查；
不能以定向键盘操作成功替代鼠标导航验收，图标与重复品牌标题仍需统一。
实际开始菜单启动同一安装包后可鼠标进入记忆页，但出现黑底深色文字；桌面进程
具有 Wayland 会话环境，不能由 SSH/tty 启动的外观代替。导出补丁 `0017` 为普通
容器补齐主题背景，渲染回归先复现冲突背景失败，修复后浅/深/浅和输入框背景通过。
回归编译实际导出的 ThemeManager，使用已有 Qt Widgets/moc/c++ 依赖和隔离配置；
接入桌面适配 CI 入口及整包测试入口。`50b9a58` 原生安装包的真实菜单启动已确认
普通背景恢复、鼠标可进入记忆/简报页；历史与当天简报均返回匹配日期，切换日期会
清空旧正文。仅覆盖无当日新记忆的响应，不代表有采集数据的完整矩阵通过。
仍发现选中标签、聚焦日期框及日历月份标题对比不足。`0019` 补齐这些控件状态样式，
回归增加冲突原生绘制与日历 palette，在浅/深/浅模式检查；新补丁仍须原生安装复验。
`971df1f` 的 V11 自动安装复验确认浅色控件恢复可读，但设置切换深色时发生 SIGSEGV。
延迟主题重绘持有控件裸指针，本地销毁临时控件再处理事件的回归以 139 复现。
`0020` 改为 QPointer 快照后相同回归通过。原生门 34154933057 已自动安装
`18d12c6`；真实菜单启动后深→浅→深→浅切换、关闭设置及鼠标返回记忆页通过，
进程未更换、文件哈希与安装文件一致、无新增崩溃。深色标签、聚焦日期框和日历月份
标题可读；仅覆盖该路径，不将此证据扩大为所有主题/生命周期验收通过。
显示身份补丁 `0021` 复用现有 PIXIU SVG，导出时嵌入宿主资源并设为应用图标；
主窗口标题改为 PIXIU，KylinAgent 来源说明仍在界面副标题中。回归先复现旧图标引用，
再核对启动代码、标题、资源注册及与打包图标的字节一致性。未重新设计图标、未变更
配置/会话身份，仍须后续原生包验证标题和各尺寸图标渲染。

会话证据解析模块 `management/AgentEvidence` 已加入管理库、导出及供应链清单。
以测试先复现缺失实现，再覆盖匹配工具开始/完成、当前会话/范围、重复记录、非法 ID、
分支/其他工具忽略、损坏日志及 2 MiB/256 条上限；不将模型文字当作真实引用。
管理、HTTP、升级及解析七组回归通过。`AgentEvidenceClient` 已补齐限量异步读取，
测试涵盖取消旧会话、超时、主动取消、声明/流式超大响应、HTTP 错误和拒绝重定向；
不保存认证配置或输出原始错误正文。阅读器已提供接收会话来源的公共入口，覆盖
去重、在途拒绝、空态及当前证据范围/敏感级别变化的测试；不新建第二套正文界面。
宿主已加入本会话来源按钮，成功后导航到统一阅读器；失败显示提示而不展示无效引用。
会话/后端/页签切换与主动取消均结束请求，来源读取纳入退出保护及组件测试。
真实安装包和实际会话来源尚待联调，不代表完整链路验收通过。沿用 Qt Network，
无新增系统依赖；`0022` 接线补丁已加入导出脚本和供应链输入，阅读器文件仍复用现有清单。

升级辅助脚本已迁入 `build/release/debian/usr/lib/pixiu/`，旧源码位置移除。
整包引用该唯一来源，安装后的路径及协议不变；独立前端包脚本及 Debian 元数据已删除。
`scripts/regression.sh` 的打包步骤委托根 `build/release`，版本测试检查旧包目标不可重现。
升级辅助与 Agent 安装集成测试验证新路径；此迁移不是新版 GUI 升级矩阵验收。

`memory_update_transport` 使用本地 TCP HTTP 服务验证版本召回与更新端点、完整载荷、
嵌套正文保留、更新结果及 VERSION_CONFLICT 不触发成功信号或自动重试。
管理测试现为六组；HTTP 详情测试补齐路径、范围编码与嵌套正文读取。
编辑组件测试覆盖加载前门控、无修改禁用、标题单独提交、版本传递、在途防关闭与防重、
超时原样幂等重试、冲突保留输入并阻止覆盖、错误目标响应、非法 JSON 和成功结果核对。
文本记忆默认直接编辑，新增测试验证非文本字段保留、模式切换不产生修改、高级模式
修改回到文本模式后仍保留、非法结构切换拒绝、关闭默认取消和保存后正常关闭。
这些测试不替代真实后端与桌面联调；缩放及复杂业务字段编辑仍需完善。

实际后端联调命令（先构建 `PIXIU_MANAGEMENT_TESTS=ON` 的管理测试目标，并在 Python
环境安装 backend 两份既有 requirements）：

```bash
python frontend/management/tests/run-memory-edit-live.py <管理构建目录>/t_memory_edit_live
```

脚本启动真实 portable 后端，使用自己持有的动态监听端口、临时数据库和独立 XDG
目录，关闭采集与同步网络。Qt 对话框完成读取、修改和冲突拒绝，另一路 HTTP 读取
核对持久化内容、版本及附加字段。退出清理测试进程与临时数据，失败输出后端日志。
通用 CI 已接入；不注入 embedding 测试桩，但仍不代表麒麟 SDK、真实桌面或安装包验收。

安全遗忘页接入一次性凭证协议，测试覆盖显式 scope、预览后编辑失效、到期失效、
取消无确认请求、确认携带凭证、防重复提交及失败后必须重新预览。旧独立窗口的
遗忘调用仍待移除；不得以新页单元测试替代所有入口和真实删除链验收。

嵌入设备页已接线状态/节点读取、设备广播、启用/暂停设置和单节点本地信任解除。
管理测试覆盖配置未加载及畸形响应门控、本机不可解绑、默认取消、解除响应 ID
核对、保存超时后刷新门控及发现空态与错误区分。配对页新增 PIN/QR 格式文本交换，
方法匹配、本机令牌过期清除、关闭清除、失败输入保留和成功响应形状核对均有测试。
全部退出新增读取后确认、串行解除、关闭网络及再次核对节点；测试覆盖取消无写入、
中途失败停止与最终响应核对。双端配对、全部退出和实际网络传输尚未完成真实桌面验收，不能把本地记录更新视为
远端确认或同步完成；文本令牌交换不等同于摄像头扫码功能。

嵌入 `MemoryAudit` 已接线偏好列表、历史、提取与冲突审计：历史由列表选择触发；
提取仅使用现有证据 ID；请求中禁用重复操作，错误不会显示成“暂无记录”。历史响应
核对所选 ID，失败可重新选择记录；冲突仅展示实际后端仲裁结果。

唯一前端迁移新增录入表单：提交时禁用重复保存和编辑，失败保留输入与幂等请求标识；
合法 accepted 响应才清空输入，不把接收成功表述成跨设备送达。仅提供实际文本录入，
不继承旧附件预览的隐含 OCR 承诺。相关测试位于 `management/tests/t_memory_workspace.cpp`。

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
4. API 层：当前 `HttpBackendTransport` 使用 `http://127.0.0.1:8765`；尚无 D-Bus transport，不存在 D-Bus 自动回退链。

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
