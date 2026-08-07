# Module A 前端开发执行计划

> 模块：UKUI 桌面客户端（`frontend/`）
> 分支：`feature/frontend`
> 技术栈：C++17、Qt5 Widgets、KylinSDK
> 计划周期：2026-08-07 至 2026-09-15
> 状态：准备执行

## 1. 目标与边界

前端负责为 PIXIU 提供银河麒麟 UKUI 原生交互入口，形成“悬浮球唤起—记忆问答—证据追溯—记忆管理—设备配对”的完整用户链路，并为比赛演示、功能验收和麒麟适配测试提供稳定界面。

前端仅修改 `frontend/`，不引用或修改 `backend/`。记忆写入、向量化、检索、冲突仲裁、遗忘执行和 CRDT 同步均由后端负责；前端只通过 `docs/API.md` 约定的 HTTP REST、WebSocket 和可选 D-Bus 接口进行异步通信。

### 1.1 核心交付物

- CMake 可构建的独立 C++17 / Qt5 Widgets 应用。
- 常驻桌面的悬浮球、全局快捷键和系统托盘入口。
- 聊天窗口、消息流、输入栏及可追溯证据卡。
- 记忆写入、查询、遗忘确认和实时事件通知。
- 偏好、冲突、设备同步三个管理页签。
- PIN/二维码设备配对、节点状态展示和解绑操作。
- UKUI 主题、通知、快捷键和扩展控件集成。
- 非麒麟环境降级实现、麒麟适配测试记录和演示说明。

### 1.2 不在前端实现的内容

- embedding 和向量数据库算法或 SDK 封装。
- SQLite、FTS5、ANN、知识图谱和重排计算。
- CRDT、Gossip、反熵对账、TLS 传输和墓碑回收。
- 后端 API、Repository 或业务 Service 的直接实现。

## 2. SDK 与公开例程使用策略

赛方提供的 `kylin-coreai-embedding` 文本向量化例程主要供 `backend/engine` 参考，`libkysdk-vector-engine-client` 向量数据库例程主要供 `backend/foundation` 参考。前端不直接集成二者，也不把它们添加为 `frontend/` 子模块；前端只依据稳定 API 消费其最终结果，例如 `answer`、`source_evidence`、`confidence` 和 `latency_ms`。

前端直接使用或研究的 KylinSDK 能力如下：

| 能力 | 计划用途 | 非麒麟降级 |
|---|---|---|
| `kysdk-shortcut` | 全局快捷键唤起聊天框 | `QShortcut` |
| `kysdk-notification` | 记忆、冲突、同步事件通知 | `QSystemTrayIcon::showMessage` |
| Theme / `UkuiStyleHelper` | 明暗主题与系统配色跟随 | Qt Palette / QSS |
| `KTranslucentFloor` | 半透明悬浮窗口 | 普通无边框 `QWidget` |
| `KDragWidget` | 悬浮球拖动 | 鼠标事件实现 |
| WindowManager | 窗口定位与 UKUI 集成 | Qt 窗口 API |
| Qt Network / WebSockets / DBus | 后端异步通信 | HTTP/WS 始终可用 |

所有麒麟专有调用放在适配层之后，并由 `PIXIU_HAVE_KYSDK` 控制，避免 UI 组件散落条件编译代码。

## 3. 实施原则

1. 优先打通可演示的端到端最小链路，再扩展管理功能。
2. UI 线程不得执行阻塞式网络或等待操作。
3. UI 只依赖 `MemoryClient`、`SyncClient` 等服务接口，不直接拼装网络请求。
4. 所有危险操作，特别是遗忘和设备解绑，必须二次确认。
5. 后端不可用时必须有明确离线态；请求失败后保留输入并允许重试。
6. 颜色、字体和图标尽量跟随 UKUI，不硬编码只适用于单一主题的值。
7. 每个特性独立实现、验证并提交，不跨组件堆积大提交。

## 4. 阶段与里程碑

### 阶段 0：接口确认与环境基线（08-07 至 08-09）

工作内容：

- 确认 Qt5、CMake、编译器和目标麒麟环境可用性。
- 核对 `docs/API.md` 的请求、响应、错误码和 WebSocket 事件。
- 与 Module C 确认 D-Bus 是否为首版强制项。
- 确认“查看证据原文”和“偏好列表”所需接口。
- 建立 `PIXIU_HAVE_KYSDK=OFF` 的开发基线。

完成标准：

- 形成接口疑问清单并完成负责人确认。
- 非麒麟环境的构建命令、依赖和限制明确。
- 每个后续阶段都有可独立验收的 feature。

### 阶段 1：应用与构建骨架（08-10 至 08-13）

工作内容：

- 创建 `CMakeLists.txt`、资源文件和 `src/main.cpp`。
- 实现 `PixiuApp` 生命周期、单实例和退出流程。
- 实现系统托盘入口和基础配置持久化。
- 建立 KylinSDK 适配层及关闭 SDK 时的桩实现。

完成标准：

- `PIXIU_HAVE_KYSDK=OFF` 时可配置、编译和启动。
- 应用可正常退出，无重复实例和明显资源泄漏。
- 构建产物不进入 Git。

建议提交：

- `feat(frontend): add CMake application skeleton`
- `feat(frontend): add application lifecycle and single-instance guard`
- `feat(frontend): add system tray integration`

### 阶段 2：悬浮入口与聊天静态界面（08-14 至 08-18）

工作内容：

- 实现 `FloatingBall` 的显示、拖动、贴边和角标状态。
- 实现 `ChatWindow` 无边框窗口、显示/隐藏和焦点管理。
- 实现 `InputBar`、`MessageList` 和基本消息气泡。
- 实现快捷键适配：开发环境使用 Qt，麒麟环境使用 KylinSDK。

完成标准：

- 点击悬浮球或快捷键可在 150ms 级别唤起聊天窗口。
- 输入、发送、关闭、再次唤起流程稳定。
- 窗口不长期抢占用户工作焦点。

建议提交：

- `feat(frontend): add draggable floating ball`
- `feat(frontend): add chat window shell`
- `feat(frontend): add chat input and message list`
- `feat(frontend): add shortcut manager`

### 阶段 3：查询 MVP 与证据展示（08-19 至 08-23）

工作内容：

- 实现基于 `QNetworkAccessManager` 的 `MemoryClient`。
- 对接 `POST /memory/query`。
- 实现加载、成功、空结果、超时、错误和重试状态。
- 实现 `EvidenceCard`，展示证据标识、置信度和延迟。
- 在后端未就绪时使用固定 mock 响应联调 UI。

完成标准：

- 用户问题立即上屏，网络请求不阻塞 UI。
- 正确解析并展示 `answer`、`source_evidence`、`confidence`、`latency_ms`。
- 超时或断连时输入不丢失，用户可重试。
- 家庭支出标准问题可完成一次端到端演示。

建议提交：

- `feat(frontend): add asynchronous memory client`
- `feat(frontend): connect memory query flow`
- `feat(frontend): add evidence card`
- `fix(frontend): handle query timeout and retry states`

### 阶段 4：写入、事件和精准遗忘（08-24 至 08-28）

工作内容：

- 对接 `POST /memory/write`，支持文本和图片拖入预览。
- 连接 `/events` WebSocket，并实现断线重连与事件分发。
- 处理 `memory_ready`、`conflict_detected`、`forget_confirmation`、`sync_event`。
- 实现 `NotifyService`。
- 对接 `POST /forget` 并实现 `ForgetDialog` 二次确认。

完成标准：

- 写入 ACK 和异步完成事件均有清晰反馈。
- WebSocket 断开不会导致崩溃，并能退避重连。
- 遗忘执行前展示目标和级联影响范围。
- 未确认时绝不执行不可逆遗忘。

建议提交：

- `feat(frontend): add memory write flow`
- `feat(frontend): add websocket event client`
- `feat(frontend): add desktop notification service`
- `feat(frontend): add forget confirmation flow`

### 阶段 5：记忆管理与设备同步（08-29 至 09-03）

工作内容：

- 实现 `MemoryPanel` 的偏好、冲突和同步页签。
- 对接偏好历史与冲突列表接口。
- 实现 `SyncClient`，对接配对、节点列表、同步状态和解绑。
- 实现 `PairDialog` 的 PIN 输入与二维码展示。
- 展示节点在线状态、待同步数和最近同步时间。

完成标准：

- 三个页签具备加载、空、错误和正常状态。
- 配对和解绑操作均有结果反馈与必要确认。
- 前端仅展示同步状态，不实现 CRDT 或传输逻辑。

建议提交：

- `feat(frontend): add memory management panel`
- `feat(frontend): add preference history view`
- `feat(frontend): add conflict audit view`
- `feat(frontend): add sync client and peer list`
- `feat(frontend): add device pairing dialog`

### 阶段 6：UKUI 集成与视觉完善（09-04 至 09-08）

工作内容：

- 接入 KylinSDK 快捷键、通知、主题和扩展控件。
- 实现明暗主题即时切换、高 DPI 和多屏位置处理。
- 完成系统图标、QSS、中文文案和基础 i18n。
- 增加 `.desktop`、自启动配置和 `.deb` 打包支持。

完成标准：

- 麒麟 UKUI 环境可编译运行。
- 全局快捷键、系统通知和主题跟随有效。
- 深浅主题、常见 DPI 与分辨率下无严重布局问题。

建议提交：

- `feat(frontend): integrate Kylin global shortcut`
- `feat(frontend): integrate Kylin notifications`
- `feat(frontend): follow UKUI theme changes`
- `feat(frontend): add desktop entry and packaging`

### 阶段 7：验收、文档与发布候选（09-09 至 09-15）

工作内容：

- 按家庭支出场景执行完整演示回归。
- 验证加载、空结果、后端离线、超时、重连和长文本。
- 验证键盘操作、高 DPI、明暗主题和目标麒麟机型。
- 记录 D-08 麒麟适配结果，补充用户操作和演示说明。
- 在 `staging` 集成前整理已知问题和回退办法。

完成标准：

- 检索结果能展示答案、证据、置信度和端到端延迟。
- 精准遗忘、冲突提醒、同步状态均可演示。
- 形成可审查的测试记录和适配证据。
- 工作区干净，提交按 feature 可独立回滚。

## 5. API 联调矩阵

| 前端功能 | API / 事件 | UI 结果 |
|---|---|---|
| 写入记忆 | `POST /memory/write` | ACK、质量分、敏感标记、处理状态 |
| 查询记忆 | `POST /memory/query` | 答案、证据卡、置信度、延迟 |
| 偏好提取 | `POST /preference/extract` | 提取进度或结果反馈 |
| 偏好历史 | `GET /preference/{id}/history` | 版本时间线 |
| 精准遗忘 | `POST /forget` | 影响范围确认与执行结果 |
| 冲突审计 | `GET /conflicts` | old/new、裁决和时间 |
| 记忆流转 | `POST /memory/flow/promote` | 流转结果反馈 |
| 设备配对 | `POST /sync/pair` | 新节点与共享域 |
| 节点列表 | `GET /sync/peers` | 在线状态和最近同步时间 |
| 同步状态 | `GET /sync/status` | 待同步数和对账状态 |
| 设备解绑 | `POST /sync/peers/{id}/revoke` | 二次确认与列表刷新 |
| 实时事件 | `WS /events` | 角标、通知、对话框和页面刷新 |

## 6. 接口待确认事项

以下事项在对应 UI 开发前与 Module C 负责人确认，不在前端单方面修改契约：

1. 文档中的“12 个 REST 端点”是否实际指 11 个 REST 加 1 个 WebSocket。
2. D-Bus 是首版必做项还是 HTTP/WS 稳定后的增强项。
3. `source_evidence` 只有 ID 时，“查看原文”从哪个端点获取详情。
4. 偏好管理页如何取得偏好列表，目前文档只明确提取与单项历史接口。
5. `GET /conflicts` 的分页、排序、状态字段和单条详情格式。
6. WebSocket 认证、心跳、重连以及事件是否需要 ACK。
7. 二维码配对令牌由哪个端点生成、有效期多长、过期错误码是什么。

## 7. 验证策略

### 7.1 每个 feature 的最低检查

- 编译或至少完成 CMake 配置检查。
- 检查新增信号槽连接和 QObject 所有权。
- 人工执行该 feature 的正常路径和一个错误路径。
- 执行 `git diff`，确认无跨模块或无关修改。
- 确认未加入 `.env`、`build/`、缓存、日志和个人绝对路径。

### 7.2 阶段回归

- 阶段 2：唤起、隐藏、焦点、拖动和多次重复操作。
- 阶段 3：正常查询、空结果、超时、后端离线和重试。
- 阶段 4：写入 ACK、WS 重连、遗忘取消和遗忘确认。
- 阶段 5：列表空态、配对失败、节点离线和解绑取消。
- 阶段 6：麒麟快捷键、通知、主题、高 DPI 和多屏。
- 阶段 7：家庭支出端到端演示及 D-08 适配记录。

## 8. Git 与提交工作流

当前开发分支为 `feature/frontend`。所有工作遵循 `AGENTS.md`：

1. 开工前阅读强制文档并检查 `git status`、`git diff`。
2. 一个 feature 或组件对应一个逻辑提交。
3. 只精确暂存该 feature 涉及的文件，不使用大范围混合暂存。
4. 提交信息使用 `feat(frontend):`、`fix(frontend):`、`docs(frontend):` 等模块前缀。
5. 提交后再次检查 `git diff` 和 `git status`，避免孤儿文件。
6. Agent 只完成本地 commit；远程 push、PR 和合并由 Human 执行。
7. 个人分支进入 `staging` 前必须完成构建、测试和人工审查；不得直接进入 `production`。

计划文档本身使用独立提交：

```text
docs(frontend): add detailed development execution plan
```

## 9. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 无可用麒麟开发机 | KylinSDK 集成延期 | 前期用适配层和 Qt 降级实现，尽早预约真机 |
| 后端接口未就绪 | UI 联调阻塞 | 使用与 `docs/API.md` 一致的 mock JSON |
| API 字段变更 | 重复返工 | JSON 解析集中在 client/model 层，契约变更先书面确认 |
| D-Bus 工作量不确定 | 挤压核心功能 | 先保证 HTTP/WS，再按负责人确认补 D-Bus |
| 一次提交过大 | 难审查、难回滚 | 按上述 feature 列表小步 commit |
| UKUI 组件版本差异 | 编译或样式异常 | pkg-config 探测能力并保留 Qt fallback |
| 截止期紧 | 非核心完善项拖累 MVP | 优先级为查询演示链路、遗忘、同步展示、适配证据 |

## 10. 下一开发 Session 的首个任务

首个实现任务定为“前端构建与应用骨架”，仅包含：

- 检查本机 Qt5 / CMake / C++ 编译器。
- 创建基础目录、`CMakeLists.txt`、`main.cpp` 和最小资源文件。
- 加入 `PIXIU_HAVE_KYSDK` 选项，但暂不实现具体 KylinSDK 功能。
- 在可用环境运行 CMake 配置和编译验证。
- 以 `feat(frontend): add CMake application skeleton` 独立提交。

若本机缺少 Qt5，先记录可复现的环境检查结果和麒麟/WSL 开发方案，不在首个 feature 中混入 UI 组件实现。
