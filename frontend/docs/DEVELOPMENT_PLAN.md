# Module A 前端开发执行计划

> 模块：UKUI 桌面客户端（`frontend/`）
> 分支：`feature/frontend`
> 技术栈：C++17、Qt5 Widgets、KylinSDK
> 计划周期：2026-08-07 至 2026-09-15
> 对齐基线：2026-08-07，`feature/frontend` 已同步至 `cb8d20e`
> 当前状态：Phase 1A 工程骨架已完成；真实配置、编译和启动验证待补

## 1. 当前进度摘要

### 1.1 已完成

- 已建立独立的 Qt5/CMake 应用骨架，提交为 `9cebaa8 chore(frontend): scaffold Qt5 application`。
- 已建立 `frontend/src/app`、`frontend/src/models`、`frontend/src/services`、
  `frontend/src/widgets` 和 `frontend/resources` 基础目录。
- 已建立 `frontend/src/main.cpp`，完成最小 `QApplication` 入口及应用元数据设置。
- 已建立 `frontend/CMakeLists.txt`，设置 C++17、Qt5 Widgets 和
  `PIXIU_HAVE_KYSDK` 构建选项。
- 已确认构建产物、缓存、`.env` 和 IDE 临时文件不得进入 Git。

### 1.2 尚未完成

- 当前 Windows 环境未发现 `cmake`、`qmake`、`g++`、`clang++` 或 `cl`，因此
  **尚未执行成功的 CMake configure、编译或启动验证**；不得把骨架标记为“已构建通过”。
- `PixiuApp`、单实例、系统托盘、配置持久化及任何界面组件尚未实现。
- `PIXIU_HAVE_KYSDK` 当前只有编译选项，尚未接入任何麒麟桌面 SDK，也尚未验证
  `ON`/`OFF` 两条构建路径。
- 未开始 `MemoryClient`、`SyncClient`、REST、WebSocket 或 D-Bus 客户端实现。

### 1.3 下一项最小独立 feature

下一项为 **`PixiuApp` application lifecycle**，建议提交：

```text
feat(frontend): add application lifecycle
```

本 feature 只负责应用对象的创建、启动、退出以及 QObject 所有权边界，不混入单实例、
托盘、设置、窗口、网络或 KylinSDK。选择它的原因是：

1. 工程骨架完成后，需要先建立统一的生命周期所有者，后续窗口和服务才能有稳定挂载点。
2. 它不依赖仍为占位的 retrieval、sync、D-Bus，也不需要 embedding/vector SDK。
3. 它可以独立编译、启动、退出和回滚，符合“一个 feature 一个 commit”。

若目标 Qt5/CMake/C++ 工具链仍不可用，可以先写代码和做静态审查，但该 feature 在目标环境
完成 configure/build/run 前不得宣称验收通过。

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
- 在正式实现 WebSocket feature 前，由后端负责人确认 `/events` 已被实际启动入口注册，并完成
  一次真实连接、`connected`、`ping` 和 `memory_ready` 冒烟验证。

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
- [ ] 在具备目标工具链的环境补齐 Qt5/CMake/C++ 版本与构建记录。

### Phase 1：应用基础

#### Phase 1A — Qt5/CMake scaffold（已完成，未完成真实编译验证）

- Commit：`9cebaa8 chore(frontend): scaffold Qt5 application`
- 内容：目录、`CMakeLists.txt`、`main.cpp`、资源占位、`PIXIU_HAVE_KYSDK` 选项。
- 待补验证：`PIXIU_HAVE_KYSDK=OFF` 的 configure/build/run；之后再验证 ON 路径。

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
5. 实现 `EvidenceCard`：`feat(frontend): add evidence card`
6. retrieval 落地后接通真实 `/memory/query`：
   `feat(frontend): connect memory query flow`

真实端到端验收受 `/memory/query` 占位阻塞。阻塞期间只允许测试专用 fake transport，生产
程序必须呈现明确的 `not_implemented`/不可用状态。

### Phase 4：写入、WebSocket、通知和遗忘

1. 对接已实现的 `/memory/write` 文本写入：`feat(frontend): add memory write flow`
2. 增加图片拖入与录入预览：`feat(frontend): add memory import preview`
3. 实现 WS 连接、控制事件、未知事件兼容和退避重连：
   `feat(frontend): add websocket event client`
4. 将已接入的 `memory_ready` 映射到应用状态：
   `feat(frontend): handle memory ready events`
5. 实现桌面通知抽象及普通 Qt 降级：
   `feat(frontend): add desktop notification service`
6. 实现 `/forget` 两段式确认：`feat(frontend): add forget confirmation flow`

`conflict_detected`、`forget_confirmation` 和 `sync_event` 只有在后端开始真实广播后才做
端到端验收；客户端事件分发可以先具备未知事件兼容能力。

### Phase 5：记忆管理

1. `MemoryPanel` 壳和 Tab 状态：`feat(frontend): add memory management panel`
2. 偏好历史：`feat(frontend): add preference history view`
3. 冲突审计：`feat(frontend): add conflict audit view`
4. 偏好列表：等待列表契约后独立实现。
5. 证据原文：等待详情契约后独立实现。

### Phase 6：设备同步管理

该阶段受 `foundation/sync` 和 `/sync/*` 占位阻塞。后端契约落地后按以下独立 feature 实现：

1. `SyncClient` 数据模型和 transport：`feat(frontend): add sync client`
2. 节点列表：`feat(frontend): add peer list`
3. 同步状态：`feat(frontend): add sync status view`
4. PIN 配对：`feat(frontend): add device PIN pairing`
5. 二维码展示：等待令牌生成契约后 `feat(frontend): add device QR pairing`
6. 解绑确认：`feat(frontend): add peer revoke flow`

前端只管理配对和展示状态，不参与 CRDT 或传输实现。

### Phase 7：UKUI/KylinSDK 桌面集成

1. Kylin 全局快捷键适配：`feat(frontend): integrate Kylin global shortcut`
2. Kylin 通知适配：`feat(frontend): integrate Kylin notifications`
3. UKUI 主题实时跟随：`feat(frontend): follow UKUI theme changes`
4. UKUI 悬浮/拖动/窗口能力：`feat(frontend): integrate UKUI window helpers`
5. 高 DPI 与多屏：`fix(frontend): support high DPI and multiple screens`
6. `.desktop`：`feat(frontend): add desktop entry`
7. `.deb` 打包：`build(frontend): add Debian packaging`

每项需在目标银河麒麟/UKUI 环境验证；不得以 Windows 降级路径代替适配结论。

### Phase 8：验收与发布候选

- 查询、写入、遗忘、冲突、同步的正常/空/离线/超时路径回归。
- WebSocket 断线、重连、心跳、未知事件和重复事件回归。
- 键盘可达、明暗主题、高 DPI、多屏和 x86/ARM 目标机验证。
- 形成 D-08 麒麟适配记录、演示说明和已知问题清单。
- 每类修复仍按一个可复现问题一个 commit，避免发布前大包提交。

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
| WS 启动级可用性未冒烟确认 | 实时事件联调有风险 | 实现客户端前与 foundation 负责人共同验证入口和事件 |
| 证据详情、偏好列表接口缺失 | 对应页面无法闭环 | 提交接口需求，由双方确认后再实现 |
| SDK/UKUI 版本与目标机差异 | Kylin 集成可能编译或行为不一致 | 使用适配层，并在真实 x86/ARM UKUI 环境留证 |
| 根/模块部分状态文档仍可能写“前端未开始” | 进度认知不一致 | 本文件以提交 `9cebaa8` 为事实基线；其他文档由对应负责人另行对齐 |

在上述阻塞中，`PixiuApp` application lifecycle 不依赖 backend、D-Bus、submodule 或麒麟专有
桌面能力，因此仍是当前真正应该执行的下一项最小独立 feature。
