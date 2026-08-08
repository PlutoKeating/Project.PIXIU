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
| A-1 | 全局快捷键唤起 | `ShortcutManager`（kysdk-shortcut `Ctrl+Alt+P`） | 编译 + offscreen 冒烟（注册/残留更新/退出清理）；真实按键待人工 | ✅ 通过（人工复测项） |
| A-2 | 桌面通知 | `NotifyService`（kysdk-notification `KNotifier`） | 编译 + 无头冒烟（`notify()` 返回有效 id）；真实弹窗待人工 | ✅ 通过（人工复测项） |
| A-3 | 主题跟随 | `ThemeService`（kysdk-qtwidgets `ThemeController` + `QGSettings` 信号） | 编译 + offscreen 冒烟 + 本机真实桌面会话 dark→light→dark 实时跟随（2026-08-08，`dc7b0e3`） | ✅ 通过 |
| A-4 | 窗口装饰 | `UkuiWindow`（kysdk-qtwidgets `KShadowHelper` 圆角阴影） | 编译 + offscreen 冒烟（`UKUI window shadow applied`）；视觉效果待人工 | ✅ 通过（人工复测项） |
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

### 3.3 打包产物

```text
build/dist/pixiu-frontend_0.1.0-1_amd64.deb
  ├─ /usr/bin/pixiu-frontend
  ├─ /usr/share/applications/com.kylin.pixiu.desktop
  └─ DEBIAN/control + postinst
```

## 4. 人工复测清单（带显示会话 / 目标机型）

- 桌面会话中按下 `Ctrl+Alt+P` 唤起聊天框（含第二实例激活）。
- UKUI 系统通知弹窗展示与点击行为。
- 聊天框阴影/圆角视觉效果；悬浮球在桌面边缘的贴边行为。
- 高分屏（HiDPI）与多屏下悬浮球/聊天框位置与缩放。
- `.deb` 在干净麒麟环境（含 x86/ARM）安装与启动。

## 5. 已知限制

- 真实桌面会话冒烟已在本机完成（应用启动、窗口、主题实时跟随）；快捷键
  按键触发、通知弹窗展示、HiDPI/多屏与 x86/ARM 目标机仍需人工复测。
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
