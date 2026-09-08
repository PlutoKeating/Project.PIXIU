# Module A 前端开发执行计划

> 模块：唯一 PIXIU 桌面宿主中的原生记忆管理与桌面适配（`frontend/`）。
> 技术栈：C++17、Qt5 Widgets；麒麟专有依赖经适配层隔离，保留 Debian 系通用路径。
> 产品边界：ADR-0006 确认 openKylin Agent 为唯一宿主；不交付第二套小窗口前端。
> 本文保留原有章节标题和顺序；标题中的旧阶段名称、日期和完成标记仅为结构兼容，
> 不是当前验收结论。正文以实际代码为准，完整任务及证据见 `docs/UNIFIED_FRONTEND_PLAN.md`。

## 1. 当前进度摘要

本模块的产品输入是 `frontend/management/CMakeLists.txt` 与宿主导出清单。
根前端 CMake 仅构建保留回归，不是可启动的独立产品。

### 1.1 已完成

- 正式宿主提供会话、记忆、设备、设置四个主入口，管理页共享同一 QApplication。
- 记忆页支持直接检索、范围选择、文本录入、版本化编辑、来源阅读、偏好/冲突审计、
  遗忘预览确认及洞察/简报；代码存在不等于完整原生矩阵已通过。
- HostTray、HostCloseGuard 统一唤起和退出保护；快捷键配置复用唯一注册器，
  信息说明与升级入口属于正式设置页。
- 独立产品 main、安装规则、前端单独包、PixiuApp 装配层及其旧单实例/托盘/
  证据弹窗已经删除。旧控件、控制器和资源仍有专属回归，继续清理。
- 已撤下失效的小窗口图库；不把仓库外诊断图自动纳入产品展示。

### 1.2 当前剩余

- 完成剩余旧控件、控制器、测试、翻译资源和脚本的依赖清理，保留正式共用组件。
- 完成全宿主能力/版本门控、跨入口范围一致性、记忆来源与错误状态矩阵。
- 补齐偏好提取、实际通知、OCR 绑定、停用竞态、双端/多端配对同步及遗忘恢复验证。
- 完成主题、语言、键盘、多屏、DPI、真实升级/回滚/重启和用户数据保留验收。
- 按当前代码更新全部非 README 文档，维持目录与章节；完成真实安装/启动/功能
  截图库、交付材料及自动化生产发布。
- 本清单不是“仅剩人工验收”；实现、删除、契约核对和发布工作均仍有未完成项。

### 1.3 下一项最小独立 feature

先验证已提交的自定义快捷键在 V11 候选中的真实注册、按键和重启恢复，再清理
已由正式组件替代的旧设置/聊天依赖。原生作业须绑定提交和安装文件哈希；观察
超时不能作为重复发起或取消作业的理由。其余任务按统一计划推进，不缩减总目标。

## 2. 职责边界与 SDK 策略

实现切片遵守根 AGENTS.md 的模块归属；跨模块协作通过公共契约和独立提交边界。

### 2.1 前端职责

Module A 维护嵌入管理页和桌面适配，通过公共 HTTP/WS 与记忆后端通信。
完整 Agent 会话、模型及工具生命周期由宿主与 Runtime 提供；Module E 负责适配。

不直接访问后端数据库、导入私有实现或在 UI 内重写向量化、检索、冲突仲裁、
遗忘执行、CRDT、Gossip、TLS 与墓碑回收。不另建 Agent 循环或 MemoryProvider。

### 2.2 官方 third_party submodule

- `third_party/kylin-agent`、`third_party/kylin-agent-runtime` 提供已锁定的宿主和 Runtime。
- `third_party/kylin-coreai-embedding`、`third_party/libkysdk-vector-engine-client`
  服务后端 SDK 适配，不因初始化 submodule 就成为 UI 直接依赖。
- 精确提交以 gitlink 和 `build/release/agent-supply-chain-policy.json` 为准。
  上游目录只读；经批准的最小补丁由导出流程应用到独立副本，不直接修改上游源码。
- 初始化使用仓库现有 submodule 流程；不在 frontend 下复制或重复引入上游。

### 2.3 前端直接使用的麒麟桌面能力

| 能力 | 正式实现 | 无专有能力时 |
|---|---|---|
| 唤起快捷键 | ShortcutManager；ON 使用 kysdk-shortcut | Qt 应用内快捷键，明确标识 |
| 桌面通知 | NotifyService；ON 使用 KNotifier | 托盘或日志降级 |
| 同窗唤起/退出 | HostTray、HostCloseGuard | 无托盘仍可正常启动和退出 |
| 主题与窗口 | 宿主 ThemeManager 及批准的桌面适配 | Qt 通用控件与主题路径 |
| 快捷键配置 | 宿主 QSettings，HostTray 单一所有者 | 相同存储和校验，不假报全局注册 |

宿主构建与管理适配使用 `PIXIU_HAVE_KYSDK`；整包/回归脚本入口选择
`PIXIU_KYSDK=OFF/ON`。两者不是 embedding/vector 后端选择器。
新增依赖前核对官方 SDK 文档和发布画像，不沿用旧壳的链接清单。

## 3. 最新 backend/foundation 接口基线

下表只列管理相关契约，不声称覆盖全部后端或完整 Agent 接口。

### 3.1 REST 实现状态

| 接口 | 当前消费方与约束 |
|---|---|
| `POST /memory/query` | MemoryWorkspace；请求 ID 隔离，范围变化清空结果 |
| `POST /memory/write` | MemoryWriteDialog；显式范围、幂等键、在途防重 |
| `GET /memory/items/{id}`、`POST /memory/update` | MemoryEditDialog；完整快照、expected_version、冲突不覆盖 |
| `GET /evidence/{id}` | 统一阅读器；正文、raw、Agent/file 来源分开 |
| `GET /preferences`、`GET /preference/{id}/history`、`POST /preference/extract` | MemoryAudit；范围、记录匹配、真实证据 ID |
| `GET /conflicts` | MemoryAudit；显示双方与仲裁结果，不充当健康探测 |
| `POST /forget` | ForgetPage；一次性预览凭证绑定命令/范围，不只发送 confirm=true |
| `/monitor/config`、`/monitor/log` | PrivacyPage；先读后显式保存、分页日志 |
| `/sync/*` | DevicePage/PairingDialog；发现、配置、令牌、信任和退出网络 |
| `/health`、`/version`、`/capabilities` | ServiceStatusPage；核对一致性，不把 WS 在线当健康 |
| `/agent/context`、`/agent/lifecycle`、`/memory/flow/promote` | Agent 集成契约；不开放任意上下文晋升表单 |

具体载荷、错误码和权限以 `docs/API.md` 为准。成功回执不等于全部设备同步完成；
兼容额外字段不能放宽必需字段、范围和响应目标校验。

### 3.2 WebSocket 状态与兼容规则

`http_app.py` 已加载 `ws.py`，WebSocket 类型导入完整；不存在待补注册阻塞。
`connected` 与应用层 `ping` 是控制消息；业务事件包括 memory_ready、
conflict_detected、forget_confirmation、sync_event、capture_event 和 pair_request。

WebSocketClient 负责连接、消息解析及退避重连；BackendEventStatus 只给出只读
失效提示与受限通知。广播不是遗忘或配对授权，不恢复旧弹窗执行语义。
未知事件不触发动作；协议无重放游标，重连后需重新读取。
复核入口见 `BACKEND_ISSUES.md`，心跳与完整网络恢复须另验。

### 3.3 D-Bus 状态

后端公开 D-Bus 服务见 `backend/foundation/api/dbus_service.py`。
正式 UI 当前使用 HttpBackendTransport 与 WebSocketClient，没有第二个 D-Bus
前端实现。不得把后端 D-Bus 方法存在描述为 UI 已通过该传输完成验收。

### 3.4 2026-08-09 历史接口阻塞（已关闭/被后续契约取代）

原列出的 WS 注册/导入、证据详情、偏好列表及配对接口缺失已不符合当前代码，
不再保留为待修复清单。当前差距是统一计划中的集成、原生与跨设备验证，以及
仍未完善的实际功能。严格 SDK 模式失败与 portable 降级必须分开描述。

## 4. 实施原则

1. 一项逻辑变更一个可审查提交，源码、依赖/构建配置和相关文档同步。
2. HTTP 异步执行并保护请求身份、在途状态和未保存输入；平台调用需有边界与超时。
3. 复用现有 transport，不直接访问数据库或复制业务算法。
4. 写入、遗忘、信任和退出以真实状态与显式用户动作授权，不从广播推导授权。
5. 错误、空态、未知响应和降级明确区分；不内置假成功或演示后端。
6. 新控件复用宿主布局/主题，避免独立顶层工作台。
7. 测试替身、临时数据库和配置隔离；测试成功不等于原生或多设备验收。
8. 提交前审查 diff/status，禁止提交密钥、实际配置、构建产物与缓存。

## 5. 分阶段、按 feature 的实施计划

保留既有标题供引用；以下是当前任务与替代关系，不再使用旧阶段完成率或日期
安排工作。完整实施及验收清单统一维护在根统一前端计划。

### Phase 0：同步、契约和环境基线（已完成本轮对齐）

持续核对当前分支、工作区、API、SDK 画像、供应链 gitlink 与构建入口。
已有根/模块文档相互矛盾时先核对源码再修订，不以旧完成记录覆盖实际实现。

### Phase 1：应用基础

应用基础归属于唯一宿主，不再为旧小窗口维护并行生命周期。

#### Phase 1A — Qt5/CMake scaffold（✅ 已完成并验证）

根 frontend CMake 是回归入口；management CMake 构建嵌入静态库及测试。
产品可执行文件由已导出的宿主构建，版本来自根 VERSION，没有独立前端版本。

#### Phase 1B — PixiuApp application lifecycle（✅ 已完成）

PixiuApp 源码和旧应用装配测试已删除，不再创建或挂载旧聊天框/悬浮球。
正式生命周期由宿主承担，HostCloseGuard 检查管理请求、Agent 在途工作和草稿。

#### Phase 1C — 单实例守护（✅ 已完成）

旧 SingleInstanceGuard 已删除。唯一宿主使用自己的单实例/激活协议，
按键及重复启动恢复已有窗口。完整 profile、异常退出、重启恢复矩阵仍须验收。

#### Phase 1D — 系统托盘与退出入口（✅ 已完成）

HostTray 恢复同一窗口并保持最大化/全屏状态，屏外标题区可恢复到实际屏幕；
退出走 HostCloseGuard，关闭最后窗口退出，不留下隐形替代应用。
旧 TrayIcon 源码已删除，不再保留重复托盘菜单。

#### Phase 1E — 基础配置持久化（✅ 已完成）

快捷键配置写入宿主 QSettings 的 `pixiu/activationShortcut`（PortableText）；
编辑后显式应用，非法组合保留旧绑定，存储失败不宣称重启后保留。
不导入旧小窗口配置，用户已有数据库及会话不在删除范围。

### Phase 2：静态交互入口

正式入口为会话、记忆、设备和设置。FloatingBall、ChatWindow、InputBar 及专属测试、翻译已删除。
MessageList 等旧控件不属于产品构建；保留中的专属回归继续按替代关系清退。
不把旧布局、角标或演示数据重新引入正式宿主。

### Phase 3：HTTP 查询客户端与证据展示

MemoryWorkspace 直接检索，不要求先配置大模型。范围切换清空旧来源与正文，
迟到响应不恢复旧内容。阅读区可拖动横向分栏，正文/结构字段与高级 raw 分离；
文件 capture_source 独立显示方法、路径、UTC 时间及有效性限制，缺失不猜测。
AgentEvidence 只接受当前会话/范围中匹配的工具记录，不把模型文案当真实引用。
继续验证长文、异常来源、超时、主题和会话切换矩阵。

### Phase 4：写入、WebSocket、通知和遗忘

- 文本录入通过 MemoryWriteDialog；已接受回执与实际送达分开。
- 编辑读取完整版本快照，保留结构字段并使用乐观锁；失败不覆盖用户输入。
- 附件 OCR 录入表单尚未提供，不以旧图片预览控件证明 OCR 已实现。
- 事件通道只读刷新，不触发确认或写入；通知使用固定脱敏文案。
- ForgetPage 先获取绑定范围/命令的预览凭证，再显式确认；失败后核对并重新预览，
  不自动重放。完整 outbox、崩溃恢复及跨设备遗忘仍须验证。

### Phase 5：记忆管理

MemoryAudit 展示偏好列表、所选记录历史及冲突双方，提取依据明确证据 ID，
MANUAL 不等于人工裁决完成。DeliveryPage 展示后端实际洞察和按日简报，
标题跳转同一阅读器，不以静态候选冒充洞察。
PrivacyPage 先读取完整配置再显式保存，保留未知/未实现来源字段但不宣称可用；
目录文本溯源已有原生样例，OCR、权限失败与停用竞态继续验证。

### Phase 6：设备同步管理

DevicePage/PairingDialog 管理实际配置、节点、发现和信任；令牌方式及响应需匹配，
QR 展示不是摄像头扫码。解除信任默认取消，本机不可解除；退出网络串行操作并
重新读取核对，失败中止。界面成功不证明双端或三端数据一致性。
继续进行真实多设备配对、传输、撤销、离线恢复及同步遗忘验证。

### Phase 7：UKUI/KylinSDK 桌面集成

- 快捷键使用已有官方 SDK 接口，失败或服务未就绪时保留应用内降级。
- 设置中的自定义组合与托盘提示共享注册状态；原生按键、重启和冲突须绑定候选。
- NotifyService 复用 KNotifier；真实通知显示、交互和脱敏需实际桌面验证。
- 宿主 ThemeManager 负责正式主题，旧 ThemeService/UkuiWindow 测试不替代它。
- 完成各页主题、语言、键盘、DPI、多屏及目标架构矩阵，不以离屏启动证明视觉。
- 桌面入口和安装规则归属整包；不再安装 pixiu-frontend 或前端单独 deb。

### Phase 8：验收与发布候选

完成正常、空、离线、超时、重连、重复/迟到响应及敏感/共享状态矩阵；
核对安装、升级、签名、失败、回滚、重启和数据保留；清退全部旧界面材料。
截图必须来自同版真实安装程序，合成示例明确标注，原生/通用证据分开。
最终通过已授权的标签自动流程发布，不以手工上传安装包替代发布门。

## 6. 构建与验证门禁

构建成功、组件测试、实际后端联调、原生桌面和多设备证据分别记录，不互相替代。

### 6.1 当前真实验证结果

已核对的局部证据包括：正式管理回归、宿主导出检查、V11 严格包构建/安装及
SDK 生命周期门，以及同版阅读器的来源、分栏和 raw/正文切换。
精确提交、作业、运行文件哈希和测试数量在根统一前端计划集中维护。
完整语言、主题、升级、多设备及最终图库仍未完成；新版生产发布不能据此视为完成。

### 6.2 工具链补齐后的最小验证

在具备 Qt5 Widgets/Network/WebSockets/Test/DBus 与 libqrencode 开发依赖的环境，
于仓库根目录执行通用组件验证：

```bash
cmake -S frontend/management -B frontend/build/management-tests \
  -DPIXIU_MANAGEMENT_TESTS=ON -DPIXIU_HAVE_KYSDK=OFF
cmake --build frontend/build/management-tests --parallel 2
ctest --test-dir frontend/build/management-tests --output-on-failure
```

包含宿主和整包的回归入口：

```bash
PIXIU_KYSDK=OFF bash frontend/scripts/regression.sh
```

在匹配麒麟画像、SDK 与桌面环境后另行运行 ON 路径。脚本每次选择一个画像，
不是自动证明 OFF/ON 都通过；组件测试仍有确定性降级与 SDK 替身。
根 frontend 构建不产出可启动产品，不能再执行 frontend/build/pixiu-frontend。
测试/构建目录应被忽略，不能提交。

### 6.3 本地验证记录（2026-08-08，Linux + Qt 5.15）

保留章节标题，不保留旧小窗口的版本、尺寸、通知 ID、截图或累计测试数量。
当前检查按以下证据层执行：

| 证据层 | 证明范围 | 不证明 |
|---|---|---|
| 管理组件测试 | 输入、状态、响应校验、退出保护和局部几何 | 真实桌面完整表现 |
| 后端隔离联调 | 临时数据库中的真实契约/业务路径 | 用户环境和跨设备送达 |
| SDK 函数替身 | 注册/失败/服务变化状态机 | 麒麟 SDK 实际注册成功 |
| 原生自动作业 | 指定提交的严格构建、安装与 SDK 门 | 全部 GUI 操作 |
| 真实桌面取证 | 指定运行程序的实际画面/交互 | 未操作的功能和其他平台 |

引用同一候选的安装清单与运行文件哈希；包更新不会自动使旧 GUI 进程成为新版本。
诊断截图与最终展示截图分别管理，不保留失效展示归档。

## 7. Git 工作流

1. 遵守根 AGENTS.md，先核对分支、工作区和用户授权；不假定远程 staging/production 已存在。
2. 逻辑变更独立提交，精确暂存；排除配置、缓存、构建产物和秘密。
3. 提交后检查干净状态；对无关用户改动不回滚、不擅自删除。
4. main 推送和生产发布需要当次明确授权；授权清晰时执行并复核远程提交。
5. 不强制推送；网络观察失败先核对同一作业/远程状态，不重复发布。
6. 模块实现不跨越文件归属；上游源码只读，契约调整须按项目协作约束处理。

## 8. 当前风险与依赖

| 风险/依赖 | 当前影响与处理 |
|---|---|
| 旧实现/资源仍有残留 | 根据正式调用与替代测试逐组删除，不只删除入口 |
| 范围/版本/能力状态 | 全宿主一致性仍需完善，不能隐式合并旧域或假装服务就绪 |
| 真实 SDK 与架构差异 | OFF、ON、x86/ARM 分开记录，使用目标画像及真机证据 |
| 语言/主题/多屏 | 完整覆盖未完成；tr()、链接成功和离屏测试不是验收 |
| 多设备/遗忘/采集 | 真实双端/三端、恢复、权限及竞态仍需验证 |
| 安装升级 | GUI 授权、失败、回滚、重启与用户数据保留须同版验证 |
| 文档和截图 | 剩余非 README 文档及导出材料需更新，正式图库尚待完成 |
| 生产发布 | 使用已授权标签触发自动 CI 与原生门，不跳过失败门或手工冒充自动发布 |

开发工作继续以统一计划中的完整任务为目标，不再以“前端可做事项全部完成”
或“仅等待后端契约”结束实施。
