# PIXIU 前端架构设计（UKUI 桌面组件 / 聊天框）

> **角色**：运行于银河麒麟桌面环境（UKUI）的原生交互入口——桌面悬浮组件 + 聊天框。
> **技术栈**：C++17 + Qt5 + KylinSDK（kysdk）。
> **后端**：通过本地 IPC 调用 Memory Daemon（详见 `backend/docs/ARCHITECTURE.md`）。
> **总体架构见**：`docs/ARCHITECTURE.md`。

---

## 1. 为什么是 UKUI 原生（而非 Web）

- 赛题要求**适配银河麒麟桌面操作系统**并提供适配测试报告（D-08）。
- 桌面级能力（全局快捷键唤起、系统通知、主题跟随、悬浮窗）必须依赖 `kysdk` 桌面环境 SDK（第 8 章），Web 方案无法原生调用。
- 与 OS Agent 同处桌面生态，交互延迟低、体验一致。

> 采用 **Qt5 Widgets + UKUI 风格**，使用应用支撑 SDK 的 Qt 扩展控件（4.1.x）保证视觉与系统一致。

---

## 2. 技术选型

| 层面 | 选型 | 对应 SDK |
|------|------|----------|
| 语言/框架 | C++17 + Qt5 Widgets | — |
| 构建 | CMake + pkg-config | 见各模块构建示例 |
| 全局唤起 | `libkysdk-shortcut` | 8.3 快捷键模块 |
| 桌面通知 | `libkysdk-notification` | 8.2 通知模块 |
| 主题跟随 | Theme 模块 + `UkuiStyleHelper` | 8.5 / 4.2.3 |
| UI 控件 | Qt 扩展控件 | 4.1.x（KListView/输入框/按钮/气泡等）|
| 悬浮/拖拽 | `KTranslucentFloor` / `KDragWidget` | 4.1.13 / 4.1.14 |
| 窗口管理 | WindowManager | 4.2.1 |
| 配置持久化 | 统一配置 | 5.7 |
| 后端通信 | QtDBus / QNetworkAccessManager + QWebSocket | — |

---

## 3. 组件结构

```
frontend/
├── src/
│   ├── main.cpp                 # 应用入口，注册全局快捷键，常驻托盘
│   ├── app/
│   │   ├── PixiuApp.{h,cpp}     # 应用生命周期、主题监听、单例守护
│   │   └── ShortcutManager.*    # kysdk-shortcut 唤起聊天框
│   ├── widgets/
│   │   ├── FloatingBall.*       # 桌面悬浮球（KTranslucentFloor + KDragWidget）
│   │   ├── ChatWindow.*         # 聊天主窗口（无边框、圆角、UKUI 风格）
│   │   ├── MessageList.*        # 对话气泡列表（KListView 派生）
│   │   ├── InputBar.*           # 输入框 + 发送（4.1.3 输入框模块）
│   │   ├── EvidenceCard.*       # 检索结果证据卡（可追溯 source_evidence）
│   │   ├── MemoryPanel.*        # 记忆/偏好/冲突管理面板
│   │   └── ForgetDialog.*       # 遗忘确认对话框（4.1.2 Dialog）
│   ├── services/
│   │   ├── MemoryClient.*       # 后端 IPC 客户端（DBus/HTTP/WS）
│   │   ├── NotifyService.*      # kysdk-notification 封装
│   │   └── ThemeService.*       # 8.5 主题跟随 + UkuiStyleHelper
│   └── models/                  # 消息/记忆/偏好数据模型
├── resources/                   # 图标、qss 样式、i18n
├── CMakeLists.txt
└── docs/
```

---

## 4. 交互形态

### 4.1 桌面悬浮组件（FloatingBall）
- 半透明悬浮球，常驻桌面边缘，可拖拽（`KDragWidget`）、贴边收起。
- 有新记忆事件/冲突时，悬浮球角标提示 + `kysdk-notification` 弹窗。

### 4.2 聊天框（ChatWindow）
- 全局快捷键（如 `Ctrl+Alt+P`）唤起 / 隐藏（`kdk_shortcut_create_global_shortcut`）。
- 消息气泡区 + 输入区；支持：
  - **提问检索**：调用 `/memory/query`，展示答案 + `EvidenceCard`（可点击追溯原始 evidence，对应 SC-05）。
  - **录入知识**：粘贴文本/拖入图片（OCR）→ `/memory/write`。
  - **自然语言遗忘**：输入"忘记那张4月支出清单"→ `/forget` → `ForgetDialog` 二次确认（F5-03/F5-04）。
- 结果卡片显示置信度、延迟（呼应 ≤500ms 指标）。

### 4.3 记忆管理面板（MemoryPanel）
- 偏好列表 + 版本历史回溯（F2-07）。
- 冲突记录审计视图（F3-01），展示 old/new 与裁决结果。
- 多设备同步状态（去中心化网络节点在线情况）。

---

## 5. 与后端通信

```cpp
// MemoryClient：优先 DBus，回退 localhost HTTP+WS
class MemoryClient : public QObject {
public:
    void query(const QString &text, const QJsonObject &contextHint);  // -> /memory/query
    void write(const QJsonObject &payload);                            // -> /memory/write
    void forget(const QString &nlCommand);                            // -> /forget
signals:
    void answerReady(const MemoryAtom &atom);   // 含 answer/source_evidence/confidence
    void memoryEvent(const QJsonObject &evt);   // WS/DBus 推送 -> 触发通知
};
```

- **首选 D-Bus**：`com.kylin.pixiu.Memory`，贴合桌面生态、随会话总线生命周期管理。
- **回退 HTTP/WS**：`http://127.0.0.1:<port>`，便于跨语言与调试。
- 事件推送（写入完成/冲突/遗忘确认）经 `NotifyService` 转 `kysdk-notification` 弹窗。

---

## 6. 主题与视觉一致性

- 启动时读取 UKUI 主题（8.5 Theme），监听明暗切换信号实时换肤。
- 通过 `UkuiStyleHelper`（4.2.3）套用系统控件风格，无边框窗口配圆角 + 阴影（`KTranslucentFloor`）。
- 多语言 i18n（中/英），字体跟随系统。

---

## 7. 构建与适配（CMake 片段）

```cmake
cmake_minimum_required(VERSION 3.5)
find_package(Qt5 COMPONENTS Widgets Network WebSockets DBus REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(KYSDK_NOTIFY  kysdk-notification)
pkg_check_modules(KYSDK_SHORTCUT kysdk-shortcut)
target_link_libraries(pixiu-frontend
  Qt5::Widgets Qt5::Network Qt5::WebSockets Qt5::DBus
  ${KYSDK_NOTIFY_LIBRARIES} ${KYSDK_SHORTCUT_LIBRARIES})
```

- 安装依赖：`sudo apt install libkysdk-notification-dev libkysdk-shortcut-dev`。
- 打包为 `.deb` + `.desktop`，注册自启动与全局快捷键。
- 提供麒麟桌面适配测试报告（D-08）：快捷键唤起、通知、主题跟随、悬浮窗在已适配机型（x86/ARM）验证。

---

## 8. 开发期降级方案

非麒麟开发机上：
- `kysdk` 调用通过编译开关 `PIXIU_HAVE_KYSDK` 切换为本地桩实现（Qt 原生托盘通知 + `QShortcut`），保证 UI 可在普通 Linux/Windows 开发联调。
- 后端 `MockEmbedding` 配合，端到端流程可离线演示。
