# 麒麟桌面适配测试报告（D-08）

> 模块：Module A · UKUI 桌面客户端（`frontend/`）
> 分支：`feature/frontend`（提交基线见下文「验证记录」）
> 日期：2026-08-08
> 本报告对应验收规范 `docs/AcceptanceTestSpecification.md` 的 **D-08 银河麒麟桌面操作系统适配兼容**。

---

## 1. 测试环境

| 项目 | 值 |
|------|----|
| 操作系统 | 银河麒麟 V11（桌面环境 UKUI） |
| 架构 | x86_64（amd64） |
| 编译器 | g++（C++17） |
| Qt | Qt 5.15.19（Widgets / Network / WebSockets） |
| CMake | 3.28.3 |
| KylinSDK | kysdk-shortcut 3.0.1.0 · kysdk-notification 3.0.1.0 · kysdk-qtwidgets 2.3.1.0 |
| 构建开关 | `PIXIU_HAVE_KYSDK=ON`（麒麟路径）/ `OFF`（开发降级路径） |

## 2. 适配能力清单与结果

| 编号 | 适配能力 | 实现 | 验证方式 | 结果 |
|------|----------|------|----------|------|
| A-1 | 全局快捷键注册链路 | `ShortcutManager`（kysdk-shortcut `Ctrl+Alt+P`） | 编译 + offscreen 冒烟 + 本机真实会话：注册 API 成功、dconf 配置正确、残留 `EXISTED→set` 更新 | ✅ 通过 |
| A-1b | 全局快捷键真实按键触发 | 同上 | 本机 uinput 合成按键（合成器已挂载虚拟键盘）未触发；运行期 kglobalaccel 查询 `Ctrl+Alt+P` 返回 ENXIO（未加载 grab） | ⚠️ 需全新登录会话复测（第 4/5 节） |
| A-1c | 第二实例激活唤起 | `SingleInstanceGuard` 激活通道 | 本机真实会话：第二实例 exit=1，主实例日志 `activation requested by secondary instance`，聊天框窗口出现（截图留证） | ✅ 通过 |
| A-2 | 桌面通知 | `NotifyService`（kysdk-notification `KNotifier`） | 编译 + 无头冒烟 + 本机真实会话：WS 桩驱动 `memory_ready` → `kysdk notification sent, id: 5`（截图留证） | ✅ 通过 |
| A-3 | 主题跟随 | `ThemeService`（kysdk-qtwidgets `ThemeController` + `QGSettings` 信号） | 编译 + offscreen 冒烟 + 本机真实桌面会话 dark→light→dark 实时跟随（2026-08-08，`dc7b0e3`） | ✅ 通过 |
| A-4 | 窗口装饰 | `UkuiWindow`（kysdk-qtwidgets `KShadowHelper` 圆角阴影） | 编译 + offscreen 冒烟 + 本机真实会话日志 `UKUI window shadow applied, radius: 12`；截图供人工确认视觉效果 | ✅ 通过（视觉人工复核） |
| A-5 | 高 DPI / 多屏 | 入口 `AA_EnableHighDpiScaling` / `AA_UseHighDpiPixmaps`；定位按屏幕可用区域钳制 | 编译 + 代码审查；x86/ARM 目标机多屏待人工 | ✅ 通过（人工复测项） |
| A-6 | 桌面入口 | `com.kylin.pixiu.desktop` + CMake 安装规则 | `desktop-file-validate` 通过；`cmake --install` 路径校验 | ✅ 通过 |
| A-7 | `.deb` 打包 | `debian/`（control/rules/postinst）+ `scripts/build-deb.sh` | `dpkg-deb -I/-c` 校验产物结构与依赖声明 | ✅ 通过 |

## 3. 自动化回归（本机可复现）

### 3.1 测试套件

两个构建路径均执行 QtTest（`QT_QPA_PLATFORM=offscreen`）：

```text
websocket_client / floating_ball / notify_service / forget_controller /
forget_dialog / memory_panel / conflict_controller / preference_controller /
shortcut_manager / theme_service / ukui_window / memory_atom / query_controller /
write_controller / app_settings / chat_window / input_bar / message_list /
import_dialog / evidence_card / i18n
```

结果：**ctest 21/21 通过**（`PIXIU_HAVE_KYSDK=OFF` 与 `ON` 两路径一致）。

### 3.2 冒烟

```text
pixiu.app: PIXIU application starting
pixiu.single-instance: primary instance listening on ...
pixiu.theme: applied UKUI dark palette
pixiu.theme: UKUI theme following enabled
pixiu.ukui-window: UKUI window shadow applied, radius: 12
pixiu.shortcut: registered Kylin global shortcut Ctrl+Alt+P -> <binary>
pixiu.app: PIXIU application started
```

后台服务未启动时，HTTP/WS 连接按预期进入离线/退避重连，无崩溃。

2026-08-08 追加：本机实时 UKUI 桌面会话（XWayland `:0`）真实冒烟：

```text
启动                      DISPLAY=:0 QT_QPA_PLATFORM=xcb 启动成功；
                          wmctrl -l 可见 "PIXIU" 窗口
主题实时跟随              ukui-dark -> ukui-light：
                          "restored system palette (light theme)"
                          ukui-light -> ukui-dark：
                          "applied UKUI dark palette"
桌面截图                  /tmp/pixiu-verified-dark.png / -light.png
```

说明：本机 kysdk-qtwidgets 2.3.1.0 的 `themeMode()` 仅在启动时缓存一次，
运行期不刷新（运行时探针确认），`ThemeService::applyTheme()` 已改读
QGSettings 实时 `styleName` 判定明暗（`dc7b0e3`）。

2026-08-08 追加（Phase 8 真实桌面收尾，本机 Kylin V11 实时 UKUI 会话）：

```text
第二实例激活             启动第二实例 exit=1；主实例日志
                         "activation requested by secondary instance"；
                         wmctrl 出现两个 PIXIU 窗口（悬浮球 + 聊天框）
                         （截图 /tmp/pixiu-phase8-04-second-activation.png）
通知弹窗                 测试专用 WS 桩（frontend/scripts/ws_smoke_server.py）
                         驱动 memory_ready：
                         "memory ready: knw_smoke_001 Phase 8 冒烟记忆"
                         "kysdk notification sent, id: 5"
                         （截图 /tmp/pixiu-phase8-05-notification.png）
窗口阴影                 启动日志 "UKUI window shadow applied, radius: 12"；
                         聊天框截图供人工确认圆角阴影视觉效果
全局快捷键真实按键       注册 API 成功且 dconf
                         /com/kylin/kysdk/keybindings/custom0 配置正确
                         （name/binding/action）；但当前运行会话中
                         kylin-wlcom 的 kglobalaccel 查询 Ctrl+Alt+P 返回
                         ENXIO（无活动 grab），uinput 合成按键未触发；
                         判定为运行期未加载 kysdk 快捷键，需全新登录
                         会话/合成器重启后复测（见第 5 节）
```

### 3.3 打包产物

```text
build/dist/pixiu-frontend_0.1.0-1_amd64.deb
  ├─ /usr/bin/pixiu-frontend
  ├─ /usr/share/applications/com.kylin.pixiu.desktop
  └─ DEBIAN/control + postinst
```

## 4. 人工复测清单（带显示会话 / 目标机型）

- 全新登录会话/合成器重启后，按下 `Ctrl+Alt+P` 唤起聊天框
  （当前运行会话未加载 grab，见第 5 节；第二实例激活已在本机验证）。
- UKUI 系统通知弹窗的展示时长、点击行为与后端真实 `memory_ready`
  事件联调（弹窗已用测试专用 WS 桩截图留证）。
- 聊天框阴影/圆角视觉效果（截图已留证）与悬浮球桌面边缘贴边行为。
- 高分屏（HiDPI）与多屏下悬浮球/聊天框位置与缩放。
- `.deb` 在干净麒麟环境（含 x86/ARM）安装与启动。

## 5. 已知限制

- 真实桌面会话冒烟已在本机完成（应用启动、窗口、主题实时跟随）；快捷键
  按键触发在当前运行会话未复现、通知弹窗点击行为、HiDPI/多屏与 x86/ARM
  目标机仍需人工复测。
- 全局快捷键注册与触发链路（2026-08-08 运行时探针）：
  `kdk_shortcut_create/set_global_shortcut` API 返回成功并写入 dconf
  （`/com/kylin/kysdk/keybindings/custom0`），
  但运行中的 kylin-wlcom 会话未加载该键的 grab（`globalShortcutsByKey`
  返回 ENXIO，kglobalaccel 组件列表无 pixiu）。可能原因：合成器在启动时
  读取 kysdk 快捷键配置，运行期注册不热生效。复测步骤：注销并重新登录
  桌面会话后再次按下 `Ctrl+Alt+P`；若仍无效，Module A 需评估改用
  kglobalaccel 标准组件注册或 ukui 自定义快捷键机制，并在此报告更新结论。
- 本机会话经 XWayland 运行，日志出现 `MESA: error: ZINK: failed to choose
  pdev` / `glx: failed to create drisw screen`（软件 GL 降级提示），不影响
  应用启动与功能，真机硬件 GL 环境应无此提示。
- `resources/` 尚无自定义图标资源，desktop 入口暂用系统主题图标。
- `WebSocketClient` 真实事件联调依赖 Module C 修复 `/events` 注册与
  WebSocket 导入（见 `frontend/docs/BACKEND_ISSUES.md`）。

## 6. 验证记录（提交基线）

```text
cdc9edb feat(frontend): follow UKUI theme changes
f418491 fix(frontend): connect UKUI theme switch signal
d02ad64 feat(frontend): integrate UKUI window helpers
248d985 fix(frontend): support high DPI and multiple screens
45ed0ec feat(frontend): add desktop entry
9e79f64 build(frontend): add Debian packaging
dc7b0e3 fix(frontend): read live style name for UKUI theme following
```
