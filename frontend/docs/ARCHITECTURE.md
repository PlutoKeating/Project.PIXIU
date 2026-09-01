# PIXIU 前端 UI/UX 设计架构文档（UKUI 桌面）

> **角色**：运行于银河麒麟桌面环境（UKUI）的原生交互入口——桌面悬浮球 + 聊天框 + 记忆管理面板。
> **技术栈**：C++17 + Qt5 Widgets + KylinSDK（kysdk）。
> **后端通信**：通过 `docs/API.md` 定义的 12 个 REST API 端点 + WS 事件推送（JSON over HTTP/D-Bus）。
> **总体架构见**：`docs/ARCHITECTURE.md`；通俗介绍见同目录 `README.md`；开发任务见 `DEV_TASKS.md`。
>
> **与后端的隔离**：前端是**独立的 C++ Qt5 项目**，与后端（backend/）的代码零交叉、零引用。
> 所有数据通过固定 API 契约获取，后端升级/替换不影响前端编译。
>
> 本文是一份**完整的 UI/UX 设计架构文档**：覆盖设计原则、用户画像、信息架构、界面布局与线框、交互流程、视觉设计系统、状态与反馈、无障碍与主题适配，以及到 kysdk 与代码组件的落地映射。

---

## 1. 设计目标与原则

PIXIU 的交互定位是「**召之即来、答完即走**」的桌面助手，不抢占用户的工作焦点。设计遵循五条原则：

- **零打扰唤起**：全局快捷键随处呼出，关闭即隐藏，不占任务栏、不打断当前应用。
- **极速可信**：检索结果必须在感知上「秒回」，并永远展示**置信度 + 延迟 + 可追溯证据**，让用户信任答案。
- **轻量克制**：界面元素少而精，默认收起；悬浮球面积小、半透明，不遮挡桌面。
- **原生一致**：完全跟随 UKUI 的主题、配色、圆角、字体与控件风格，像系统自带功能一样自然。
- **安全显性**：涉及遗忘、敏感数据、冲突修改等操作时，给出清晰的二次确认与可见的审计入口。

---

## 2. 用户画像与核心场景

| 画像 | 诉求 | 关键交互 |
|------|------|----------|
| **居家多设备用户**（如故事中的林先生） | 随口提问、模糊检索、不想翻文件 | 快捷键唤起 → 提问 → 看带证据的答案 |
| **办公协作用户** | 沉淀工作流/案例、跨设备复用 | 录入知识、查看同步状态、偏好复用 |
| **注重隐私的用户** | 控制敏感数据、精准遗忘 | 遗忘指令 + 二次确认、敏感标记可见 |

**三大核心任务流**：① 提问检索 ② 录入知识 ③ 管理记忆（偏好/冲突/遗忘/同步）。

---

## 3. 为什么是 UKUI 原生（而非 Web）

- 赛题要求**适配银河麒麟桌面操作系统**并提供适配测试报告（D-08）。
- 桌面级能力（全局快捷键唤起、系统通知、主题跟随、无边框悬浮窗）必须依赖 `kysdk` 桌面环境 SDK（第 8 章），Web 方案无法原生调用。
- 与 OS Agent 同处桌面生态，交互延迟低、视觉体验一致。

> 采用 **Qt5 Widgets + UKUI 风格**，使用应用支撑 SDK 的 Qt 扩展控件（4.1.x）保证视觉与系统一致。

---

## 4. 信息架构（IA）

整个前端只有**三个顶层界面入口**，层级极浅，降低认知负担：

```
PIXIU 前端
├── ① 悬浮球 FloatingBall          （常驻 · 入口）
│     ├── 单击 → 唤起聊天框
│     ├── 角标 → 未读记忆事件/冲突计数
│     └── 右键菜单 → 设置 / 记忆面板 / 退出
├── ② 聊天框 ChatWindow            （主交互）
│     ├── 消息流（提问/答案/证据卡）
│     ├── 输入栏（文本 / 图片拖入 / 发送）
│     └── 顶栏（同步状态 · 打开记忆面板 · 关闭）
└── ③ 记忆管理面板 MemoryPanel     （管理）
      ├── 偏好 Tab（列表 + 版本回溯）
      ├── 冲突 Tab（old/new 审计）
      └── 同步 Tab（节点列表 + 配对/解绑 + 同步进度）
            └── 配对对话框 PairDialog（扫码/PIN）
```

**导航模型**：悬浮球是唯一常驻入口；聊天框与管理面板均为模态/半模态浮层，按需出现、随手关闭。

---

## 5. 界面布局与线框图

### 5.1 悬浮球（FloatingBall）

```
        ╭─────╮
        │ 貔  │   ← 半透明圆形，直径约 56px
        │ 貅 ②│   ← 右上角标：未读事件数
        ╰─────╯
   默认停靠桌面右下角，可拖拽到任意位置
```

- 形态：半透明圆形悬浮窗，鼠标左键按住可拖拽到任意位置并停留在放置处；
  默认初始位于屏幕可用区域右下角。
- 状态：空闲（静态）/ 有新事件（角标 + 轻微呼吸动效）/ 处理中（旋转光环）。

### 5.2 聊天框（ChatWindow）

```
┌────────────────────────────────────────────┐
│  ◉ PIXIU 貔貅                 📌  ✕ │  ← 顶栏：Logo/应用入口 + 置顶/关闭
├────────────────────────────────────────────┤
│            ◉ PIXIU                        │  ← 欢迎页（首屏，可滚动）
│        你好，我是 PIXIU                    │
│    问问你的记忆，或录入新的知识             │
│    您可以问我：                            │
│    ┌ 我们家的水电燃气花了多少钱？ ┐        │  ← 建议卡片（点击填入输入框）
│    ┌ 我最近记下了哪些知识点？ ┐          │
│    ┌ 我的偏好设置有哪些？ ┐              │
│    ┌ 忘记上个月的家庭支出清单 ┐          │
│    按 Ctrl+Alt+P 随时唤起                │
│                                              │
│   ┌──────────────────────────────────┐      │
│   │ 我们在水电燃气方面花了多少钱？      │ ←用户 │  右对齐气泡
│   └──────────────────────────────────┘      │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │ 2026年4月，你们在水电燃气方面共支出      │  │  左对齐气泡
│ │ 434.50 元，其中电费210/水费68.5/燃气156 │  │
│ │ ┌─ 证据卡 ──────────────────────────┐  │  │
│ │ │ 📄 2026年4月家庭支出清单            │  │  │  EvidenceCard
│ │ │ 置信度 0.93 · 延迟 210ms  [查看原文]│  │  │
│ │ └────────────────────────────────────┘  │  │
│ └────────────────────────────────────────┘  │
│                                              │
├────────────────────────────────────────────┤
│ [记忆][设置][录入][同步][更多]              │  ← chip 快捷行（空间不足收缩）
│ ┌────────────────────────────────────────┐ │
│ │ 📎  输入问题，或拖入图片录入…          │ │  ← 多行输入卡片
│ │ ● 在线                    [ 发送 ]    │ │  ← 状态 badge / 发送
│ └────────────────────────────────────────┘ │
└────────────────────────────────────────────┘
```

- 形态为「窄而高的桌面侧边 AI 助手浮窗」：默认 380×640，可拉伸（最小
  320×480），无边框、大圆角 + 柔和阴影（`KTranslucentFloor`）。
- 顶栏：Logo + 应用入口（左侧），置顶/关闭两个扁平图标按钮（右侧）；功能入口
  统一收敛到输入区上方 chip 行（记忆/设置/录入/同步），不设重复的“更多”菜单；
  消息区为欢迎页（Logo + 问候 + 建议问题卡片，点击填入输入框）与消息流的
  自动切换；输入区为圆角浅灰卡片 + chip 快捷行，左下角状态 badge、右下角
  主题高亮发送胶囊，多行输入（Enter 发送 / Shift+Enter 换行）。
- 默认在屏幕右下/悬浮球附近弹出，记忆上次位置。

### 5.3 记忆管理面板（MemoryPanel）

```
┌─────────────────────────────────────────────┐
│  记忆管理            [偏好] [冲突] [同步]   ✕ │  ← Tab 切换
├─────────────────────────────────────────────┤
│ 偏好 Tab：                                    │
│  ┌─────────────────────────────────────────┐ │
│  │ 输出风格 · 简洁          v3  [历史] […] │ │  列表项 + 版本回溯
│  │ 操作习惯 · 优先深色主题   v1  [历史] […] │ │
│  │ 安全策略 · 财务数据不外传 v2  [历史] […] │ │
│  └─────────────────────────────────────────┘ │
│                                               │
│ 冲突 Tab：old/new 对比 + 裁决结果 + 时间       │
│                                               │
│ 同步 Tab：                          [+ 配对设备]│
│  ┌─────────────────────────────────────────┐ │
│  │ 💻 书房工作站(本机)   ●在线  刚刚同步      │ │
│  │ 🖥 客厅一体机        ●在线  2分钟前  [解绑]│ │
│  │ 💻 麒麟笔记本        ○离线  1小时前  [解绑]│ │
│  └─────────────────────────────────────────┘ │
│  同步进度：待同步 0 条 · 上次对账 14:32        │
└─────────────────────────────────────────────┘
```

### 5.4 设备配对对话框（PairDialog）

```
┌───────────────────────────────────┐
│  配对新设备 加入共享域 shared:home  │
│  ┌───────────┐                      │
│  │  [二维码]  │   或输入 PIN：______ │
│  └───────────┘                      │
│  在另一台设备的「同步」面板扫码/输码  │
│                 [ 取消 ]  [ 完成配对 ]│
└───────────────────────────────────┘
```

### 5.5 遗忘确认对话框（ForgetDialog）

```
┌───────────────────────────────────┐
│  ⚠ 确认遗忘                         │
│  即将遗忘：「2026年4月家庭支出清单」 │
│  将级联清理：1 条知识 · 1 条证据 ·   │
│  3 个实体关系。此操作不可撤销。       │
│                 [ 取消 ]  [ 确认遗忘 ]│
└───────────────────────────────────┘
```

---

## 6. 关键交互流程

### 6.1 提问检索（核心流，呼应 ≤500ms / SC-05）

```
用户按 Ctrl+Alt+P
   → 聊天框淡入（≤150ms 动效）→ 输入框自动聚焦
用户输入问题 → 回车/点发送
   → 用户气泡立即上屏 + 答案区显示「思考中…」骨架占位
   → MemoryClient.query() → 后端 /memory/query
   → 收到 MemoryAtom：替换骨架为答案气泡 + EvidenceCard
点击「查看原文」
   → 展开/弹出原始 evidence 详情（可追溯 OCR 原文）
```

### 6.2 录入知识

```
拖入图片到输入栏 / 粘贴文本
   → 显示待录入预览卡（缩略图 + 识别提示）
点「录入记忆」
   → MemoryClient.write(source_type=OCR/MANUAL) → /memory/write
   → 后端 ACK 后，气泡提示「已沉淀，正在结构化…」
   → 结构化完成的 WS 事件到达 → 通知「记忆已就绪」
```

### 6.3 自然语言遗忘（F5-03/F5-04）

```
输入「忘记那张4月支出清单」
   → 识别为遗忘意图 → MemoryClient.forget()
   → 后端返回匹配目标与级联影响范围
   → 弹出 ForgetDialog 展示影响范围 → 二次确认
   → 确认后执行 → 通知「已遗忘，相关证据与关系已清理」
```

### 6.4 冲突提醒与审计（F3-01）

```
后端检测到冲突 → WS 推送事件
   → 悬浮球角标 +1 + kysdk-notification 弹窗
点击通知 / 角标
   → 打开 MemoryPanel 冲突 Tab → 查看 old/new 与裁决结果
```

### 6.5 多设备同步管理（去中心化网络）

```
配对：同步 Tab 点「+ 配对设备」
   → PairDialog 显示本机二维码/PIN（含设备公钥）
   → 另一台设备扫码/输码 → MemoryClient.pair() → /sync/pair
   → 双向建立信任、加入共享域 → 节点列表新增该设备

状态：MemoryClient.peers()/syncStatus() 轮询或订阅 WS
   → 渲染节点在线状态、最近同步时间、待同步条数
   → 节点上下线 / 同步事件 → kysdk-notification 提醒

解绑：点节点「解绑」→ 二次确认
   → MemoryClient.revokePeer(id) → /sync/peers/{id}/revoke
   → 撤销信任、移出共享域
```

> 前端仅做配对、展示与解绑；CRDT 合并、Gossip/反熵对账等由后端同步层完成（见 `backend/docs/ARCHITECTURE.md` 第 7 章）。

### 6.6 应用内安全升级

```
设置 → 检查更新
  → UpgradeController 请求公开 GitHub Release latest API
  → 按当前 Debian 架构（amd64 / arm64）选择同版本 .deb + .sha256
  → 流式下载到唯一临时文件 → 流式 SHA-256 校验（含资产文件名绑定）
  → pkexec /usr/lib/pixiu/install-update <deb> <sha256> → polkit 系统授权
  → 特权 helper 复制到 root-only 文件并再次校验
  → 非交互 dpkg（保留已安装的设备配置）
  → 成功后提示用户手动重启
```

- 下载及每次重定向均限制为 HTTPS 和 GitHub 精确域名白名单。
- 元数据、校验清单和 DEB 均有限额；特权 helper 对 root-only 副本再次校验，
  消除 polkit 授权等待期间替换用户临时文件的竞态。
- 下载/校验可取消；`dpkg` 启动后禁用关闭与强制取消，避免产生半配置包。
- 安装进程启动失败、授权取消和 `dpkg` 错误分别呈现；错误输出限制长度。
- 安装包 `postinst` 保留 SQLite 记忆与配置，并在轮换历史公开同步口令时原地
  重加密 Ed25519 私钥，保留设备 ID、peer 与配对关系。

---

## 7. 视觉设计系统（Design System）

### 7.1 配色（跟随 UKUI 主题，不写死）

| 角色 | 取色来源 | 说明 |
|------|----------|------|
| 主色 / 强调 | UKUI 主题高亮色（Theme 8.5）| 发送按钮、链接、选中态 |
| 背景 | 系统窗口背景 | 明/暗主题自动切换 |
| 气泡（用户）| 主色浅化 | 右对齐 |
| 气泡（PIXIU）| 系统卡片背景 | 左对齐 |
| 证据卡描边 | 分隔线色 | 弱化、可点击 |
| 警示（遗忘/冲突）| 系统语义色（橙/红）| 二次确认场景 |

> 颜色全部经 `ThemeService` 从系统主题读取，禁止硬编码，保证明暗主题与个性化配色一致性。

### 7.2 字体与排版

- 字体跟随系统默认字体；字号分级：标题 14pt / 正文 11pt / 辅助 9pt。
- 行高 1.5，气泡内边距 12px，证据卡内边距 10px。

### 7.3 间距与圆角

- 基础间距栅格：4 / 8 / 12 / 16px。
- 2026-08-10 侧边浮窗视觉统一：窗口圆角 16px，卡片圆角 10px，气泡圆角
  12px（用户气泡 14px），按钮圆角 8px，输入卡片圆角 14px；无边框窗口配
  柔和阴影。
- 浅色模式以白 / 极浅灰（`palette(Base)` 白、`palette(Window/AlternateBase)`
  极浅灰）为主，控件弱边框、低噪声；深色模式为结构一致的深灰蓝变体；颜色
  仍全部取 palette 角色，随 UKUI 主题联动。

### 7.4 动效（Motion）

| 场景 | 动效 | 时长 |
|------|------|------|
| 聊天框唤起/隐藏 | 淡入 + 轻微上移 | 150ms |
| 答案加载 | 骨架屏 / 打字光标 | 直到结果到达 |
| 悬浮球新事件 | 角标弹入 + 呼吸 | 循环 |
| 处理中 | 悬浮球旋转光环 | 循环 |

> 动效以「快、轻、可中断」为准则，避免冗长动画影响响应感。

### 7.5 图标

使用 UKUI 系统图标主题，保持线性风格统一；自定义图标提供明/暗两套。

---

## 8. 状态、反馈与边界情况

| 情况 | UI 表现 |
|------|---------|
| 检索加载中 | 答案区骨架屏 + 顶栏细进度条 |
| 检索超时/失败 | 气泡红字提示 + 「重试」按钮，不丢失输入 |
| 后端未连接 | 顶栏「●离线」+ 输入禁用 + 引导启动服务 |
| 空结果 | 友好空态文案 + 录入知识引导 |
| 敏感内容 | 录入预览标记「含敏感信息，默认不同步」 |
| 长答案 | 气泡可滚动；证据卡折叠默认收起 |
| 多设备同步中 | 同步 Tab 显示进度与节点状态 |

---

## 9. 无障碍与多端适配

- **键盘可达**：全流程支持 Tab 焦点导航与回车提交；快捷键可在设置中自定义。
- **高 DPI**：Qt 高 DPI 缩放，悬浮球/图标提供多倍图。
- **明暗主题**：监听 UKUI 主题切换信号实时换肤（8.5）。
- **多语言 i18n**：中/英文案经 Qt `tr()` 与 `.ts` 资源管理。
- **x86 / ARM**：升级器按运行架构选择 Debian 资产；GitHub Release 在原生
  amd64/arm64 runner 分别构建。麒麟 V11 x86_64 已验证，ARM 麒麟真机仍须按
  独立平台画像完成 D-08 验收，不以通用 ARM CI 代替真机结论。

---

## 10. 前端技术架构与组件落地

### 10.1 组件结构

```
frontend/
├── src/
│   ├── main.cpp                 # 应用入口，注册全局快捷键，常驻托盘
│   ├── app/
│   │   ├── PixiuApp.{h,cpp}     # 应用生命周期、主题监听、单例守护
│   │   ├── ShortcutManager.*    # kysdk-shortcut 唤起聊天框
│   │   ├── UpgradeController.*  # 检查/下载/校验/polkit 安装状态机
│   │   └── UpgradeUtils.*       # 版本、架构、Release 资产与流式 SHA-256
│   ├── widgets/
│   │   ├── FloatingBall.*       # 桌面悬浮球（KTranslucentFloor + KDragWidget）
│   │   ├── ChatWindow.*         # 聊天主窗口（无边框、圆角、UKUI 风格）
│   │   ├── MessageList.*        # 对话气泡列表（KListView 派生）
│   │   ├── InputBar.*           # 输入框 + 发送 + 图片拖入（4.1.3）
│   │   ├── EvidenceCard.*       # 检索结果证据卡（可追溯 source_evidence）
│   │   ├── MemoryPanel.*        # 记忆/偏好/冲突/同步管理面板
│   │   ├── ForgetDialog.*       # 遗忘确认对话框（4.1.2 Dialog）
│   │   ├── PairDialog.*         # 设备配对对话框（二维码/PIN）
│   │   └── CheckUpdateDialog.*  # 应用内升级状态、进度与安全提示
│   ├── services/
│   │   ├── MemoryClient.*       # 后端 IPC 客户端（DBus/HTTP/WS）
│   │   ├── SyncClient.*         # 同步管理客户端（/sync/* 配对/节点/状态/解绑）
│   │   ├── NotifyService.*      # kysdk-notification 封装
│   │   └── ThemeService.*       # 8.5 主题跟随 + UkuiStyleHelper
│   └── models/                  # 消息/记忆/偏好数据模型
├── resources/                   # 图标、qss 样式、i18n
├── CMakeLists.txt
└── docs/
```

### 10.2 UI 组件与 kysdk 映射

| UI 组件 | 职责 | kysdk / Qt |
|---------|------|------------|
| FloatingBall | 常驻入口、拖拽、角标 | `KTranslucentFloor` 4.1.13 / `KDragWidget` 4.1.14 |
| ChatWindow | 主对话浮层 | 无边框窗 + WindowManager 4.2.1 |
| MessageList | 气泡流 | `KListView` 派生（4.1.x）|
| InputBar | 输入/发送/拖图 | 输入框模块 4.1.3 |
| ForgetDialog | 二次确认 | Dialog 4.1.2 |
| PairDialog | 设备配对（二维码/PIN）| Dialog 4.1.2 + Qt 绘制 |
| MemoryPanel·同步 Tab | 节点列表/进度/解绑 | `KListView` 派生（4.1.x）|
| 全局唤起 | 快捷键 | `libkysdk-shortcut` 8.3 |
| 通知 | 事件弹窗 | `libkysdk-notification` 8.2 |
| 主题 | 换肤 | Theme 8.5 + `UkuiStyleHelper` 4.2.3 |
| 设置持久化 | 位置/快捷键/语言 | 统一配置 5.7 |

### 10.3 技术选型

| 层面 | 选型 | 对应 SDK |
|------|------|----------|
| 语言/框架 | C++17 + Qt5 Widgets | — |
| 构建 | CMake + pkg-config | 见 §12 |
| 全局唤起 | `libkysdk-shortcut` | 8.3 快捷键模块 |
| 桌面通知 | `libkysdk-notification` | 8.2 通知模块 |
| 主题跟随 | Theme 模块 + `UkuiStyleHelper` | 8.5 / 4.2.3 |
| UI 控件 | Qt 扩展控件 | 4.1.x |
| 悬浮/拖拽 | `KTranslucentFloor` / `KDragWidget` | 4.1.13 / 4.1.14 |
| 窗口管理 | WindowManager | 4.2.1 |
| 配置持久化 | 统一配置 | 5.7 |
| 后端通信 | QtDBus / QNetworkAccessManager + QWebSocket | — |

---

## 11. 与后端通信

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

// SyncClient：去中心化同步的管理面（仅配对/状态/解绑，不含同步逻辑）
class SyncClient : public QObject {
public:
    void pair(const QString &token);                 // -> /sync/pair
    void listPeers();                                // -> GET /sync/peers
    void syncStatus();                               // -> GET /sync/status
    void revokePeer(const QString &peerId);          // -> /sync/peers/{id}/revoke
signals:
    void peersUpdated(const QList<PeerInfo> &peers);  // 节点列表 + 在线状态
    void syncStatusChanged(const SyncStatus &st);     // 待同步条数/上次对账
    void peerEvent(const QJsonObject &evt);           // 节点上下线 -> 触发通知
};
```

- **首选 D-Bus**：`com.kylin.pixiu.Memory`，贴合桌面生态、随会话总线生命周期管理。
- **回退 HTTP/WS**：`http://127.0.0.1:<port>`，便于跨语言与调试。
- 事件推送（写入完成/冲突/遗忘确认/**节点上下线/同步状态**）经 `NotifyService` 转 `kysdk-notification` 弹窗。
- UI 层永不阻塞：所有后端调用异步，UI 用骨架屏/进度态过渡。

---

## 12. 构建与适配（CMake 片段）

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

## 13. 开发期降级方案

非麒麟开发机上：
- `kysdk` 调用通过编译开关 `PIXIU_HAVE_KYSDK` 切换为本地桩实现（Qt 原生托盘通知 + `QShortcut`），保证 UI 可在普通 Linux/Windows 开发联调。
- 后端无 mock 降级（`PIXIU_EMBEDDING` 仅支持 `kylin`）；开发机无后端时可运行
  `frontend/scripts/demo_stub_server.py` 演示桩，完整演示端到端 UI 流程
  （见 `DEMO_GUIDE.md` §5）。
