# PIXIU 前端 · UKUI 桌面交互入口

> 本文用通俗语言说明**前端做了哪些事**、**用什么技术实现**、以及**怎么构建运行**。
> 想了解界面与交互的完整设计，请看同目录的 [`ARCHITECTURE.md`](./ARCHITECTURE.md)；想了解整个产品，请看仓库根目录 [`README.md`](../../README.md)。

---

## 一句话介绍

PIXIU 前端是运行在**银河麒麟桌面（UKUI）**上的原生交互入口——一个常驻桌面的**悬浮球**加一个随叫随到的**聊天框**。用户按下全局快捷键即可唤起对话，向 PIXIU 提问、录入知识、管理记忆，所有答案都带可点击追溯的证据卡。它不是网页，而是用 Qt5 + KylinSDK 写的桌面原生应用，和系统主题、通知、快捷键深度融合。

---

## 它做了哪些事

- **悬浮球常驻** — 半透明小球停在桌面边缘，可拖拽、可贴边收起；有新记忆或冲突时角标提示。
- **快捷键唤起聊天框** — 全局快捷键（如 `Ctrl+Alt+P`）一键呼出/隐藏对话窗口，不打断当前工作。
- **提问检索** — 输入模糊问题，展示后端返回的答案 + 置信度 + 延迟，并附**证据卡**，点开可回溯原始记忆。
- **录入知识** — 粘贴文本或拖入图片（走 OCR），把内容写入长期记忆。
- **自然语言遗忘** — 输入"忘记那张 4 月支出清单"，弹出二次确认对话框后执行精准遗忘。
- **记忆管理面板** — 查看偏好列表与版本历史、冲突审计记录。
- **多设备同步管理** — 扫码/PIN **配对新设备**加入共享域；查看节点列表、在线状态与同步进度；一键**解绑**设备。节点上下线与同步事件会以系统通知提醒。
- **系统级融合** — 跟随 UKUI 明暗主题换肤；记忆事件通过系统通知弹出；字体/语言跟随系统。

> 前端本身不存储记忆、不做检索计算，只负责**交互与展示**，所有数据能力由后端 Memory Daemon 提供。

---

## 技术栈

| 层面 | 选型 | 说明 |
|------|------|------|
| 语言 | **C++17** | 桌面原生开发 |
| GUI 框架 | **Qt5 Widgets** | UKUI 桌面采用 Qt 生态 |
| 桌面风格 | **UKUI + `UkuiStyleHelper`** | 与系统控件视觉一致（应用支撑 SDK 4.2.3）|
| 全局快捷键 | **`libkysdk-shortcut`** | 唤起聊天框（SDK 8.3）|
| 系统通知 | **`libkysdk-notification`** | 记忆事件、冲突提醒（SDK 8.2）|
| 主题跟随 | **Theme 模块** | 明暗主题实时换肤（SDK 8.5）|
| 悬浮/拖拽 | **`KTranslucentFloor` / `KDragWidget`** | 半透明悬浮球（SDK 4.1.13/4.1.14）|
| 配置持久化 | **统一配置** | 端侧设置存储（SDK 5.7）|
| 后端通信 | **QtDBus / QNetworkAccessManager + QWebSocket** | D-Bus 优先，HTTP/WS 回退 |

---

## 构建与工具链

| 用途 | 工具 |
|------|------|
| 构建系统 | **CMake**（≥3.5）+ `pkg-config` 发现 kysdk 库 |
| 编译器 | 支持 C++17 的 GCC / Clang |
| 依赖 | `Qt5`（Widgets/Network/WebSockets/DBus）、`libkysdk-*-dev` |
| 打包 | `.deb` + `.desktop`（注册自启动与全局快捷键）|
| 开发降级 | 编译开关 `PIXIU_HAVE_KYSDK`，非麒麟环境用 Qt 原生桩实现 |

安装依赖示例（麒麟/Debian 系）：

```bash
sudo apt install qtbase5-dev libqt5websockets5-dev \
                 libkysdk-notification-dev libkysdk-shortcut-dev
```

构建：

```bash
cmake -B build -S . && cmake --build build
```

---

## 目录结构

```
frontend/
├── src/
│   ├── main.cpp        # 应用入口，注册全局快捷键，常驻托盘
│   ├── app/            # 应用生命周期、主题监听、快捷键管理
│   ├── widgets/        # 悬浮球、聊天窗、消息列表、输入栏、证据卡、管理面板
│   ├── services/       # 后端客户端、通知服务、主题服务
│   └── models/         # 消息/记忆/偏好数据模型
├── resources/          # 图标、qss 样式、i18n 翻译
├── CMakeLists.txt
└── docs/               # 本目录文档
```

---

## 与后端的关系

前端通过本地 IPC 调用后端 Memory Daemon：

- **首选 D-Bus**：`com.kylin.pixiu.Memory`，贴合桌面生态。
- **回退 HTTP/WS**：`http://127.0.0.1:<port>`，便于调试。
- 后端推送的事件（写入完成 / 冲突 / 遗忘确认 / **节点上下线 / 同步状态**）经通知服务转成 `kysdk-notification` 弹窗。
- 多设备同步由后端分布式同步层负责，前端只通过 `/sync/*` 接口做**配对、状态展示与解绑**，不参与同步逻辑本身。

界面布局、交互流程、视觉规范、组件设计等完整内容见 [`ARCHITECTURE.md`](./ARCHITECTURE.md)。
