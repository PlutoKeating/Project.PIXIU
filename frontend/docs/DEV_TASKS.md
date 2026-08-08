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
- 双路径（`PIXIU_HAVE_KYSDK=OFF/ON`）ctest 20/20 通过；自动化回归脚本
  `scripts/regression.sh`（OFF/ON 构建+测试、offscreen 冒烟、desktop 校验、`.deb` 校验）
  已纳入 Phase 8 本地基线。
- 查询失败提示行已带“重试”按钮（点击以原输入重新提交，输入保留），
  对应 `MessageList::appendQueryError`/`retryRequested` 与 `t_message_list` 用例。
- 键盘可达补强：ForgetDialog Esc/关闭触发取消（默认按钮为“取消”）、
  MemoryPanel Esc 隐藏、主要按钮/输入框 accessibleName，均已补测试。
- 空结果提示行已带“录入知识”引导按钮（点击打开录入对话框），
  对应 `MessageList::appendEmptyResult`/`importKnowledgeRequested` 与用例。
- 进度与验证记录以 `frontend/docs/DEVELOPMENT_PLAN.md` 为准；真实桌面会话复测与
  x86/ARM 目标机验收仍需人工执行。

---

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

- **悬浮球（FloatingBall）**：常驻桌面边缘，可拖拽、可贴边收起
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
| `src/widgets/FloatingBall.{h,cpp}` | ★★★ | 桌面悬浮球（KTranslucentFloor + KDragWidget），角标、贴边收起 |
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
