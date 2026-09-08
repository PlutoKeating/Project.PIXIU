# 模块 A · UKUI 桌面客户端 —— 开发任务书

> **模块**：A — UKUI 桌面客户端
> **目录**：`frontend/`
> **技术栈**：C++17 · Qt5 Widgets · KylinSDK
> **与后端契约**：`docs/API.md` 定义的 32 个 REST 端点 + WS

> [!IMPORTANT]
> 当前按 ADR-0006 执行唯一宿主迁移：openKylin `kylin-agent` 与 Runtime 承担
> 会话和 Agent 生命周期，自有 Qt 管理页嵌入同一应用。此为团队批准的技术路线，
> 不是赛方指定实现；完整开发与交付尚未完成。

---

## 实现状态（2026-09-03 · v0.1.7 发布）

标题保留用于既有文档定位；本节按当前单一包体更新，不沿用旧版本的完成声明。

产品版本由根 `VERSION` 派生，管理库为静态库，随唯一宿主构建，不再独立打包。
升级复用 `UpgradeController`、`CheckUpdateDialog` 和随包安装 helper，具备签名、
架构/版本检查及安装后健康判断。完整新宿主图形升级、回滚、重启和数据保留矩阵
仍须完成；已实现状态不等于生产发布或全部验收通过。

## 实现状态（2026-09-02 · v0.1.6 本机验收）

旧窗口的本机验收不能代表当前产品。现行验证分为管理组件离屏回归、通用 OFF
宿主构建、麒麟 V11 ON 整包自动安装，以及安装后真实桌面操作四层，结果分别记录。
不得降低应用版本、替换授权入口或使用测试桩截图来声称当前图形升级链路已经通过。
原生验证必须核对安装清单和运行文件，避免把安装前仍存活的进程当成新包。

## 实现状态（2026-09-01 · 0.1.6 发布候选）

发布候选须从当前 `main` 的版本提交生成，生产入口为 `v*` 标签自动工作流；
通用 CI 与麒麟 V11 原生门通过后才可发布。包体、版本派生、离线宿主/Runtime
供应链和升级签名以 `build/release/` 为准。arm64 通用结果不能代替麒麟 arm64
硬件验证；历史候选版本与截图不作为本次交付依据。

## 实现状态（2026-08-11）

撤销旧独立界面“全部完成”和旧翻译条数的完成口径。当前产品只有同一宿主中的
会话、记忆、设备、设置导航；现有管理文案使用 Qt 翻译调用，但完整英文资源、
全部主题、键盘、缩放和多屏仍须验证。旧测试目标存在不表示相应旧窗口仍属于产品。
完整待办以根 `docs/UNIFIED_FRONTEND_PLAN.md` 的 U01～U16 为准。

## 实现状态（2026-08-08 更新）

当前 `scripts/regression.sh` 运行保留回归、管理测试与所选 OFF/ON 唯一宿主构建，
再委托根发布目录打包，不再启动旧程序冒烟。检索失败由状态行说明并允许再次检索，
原输入保留；空结果与失败分别展示。录入为真实文本表单，不继承旧附件预览的
OCR 承诺。截图仅取实际安装后的桌面像素，测试服务器和离屏渲染只用于自动回归。

## 实现状态（2026-08-09 更新）

同步、审计、隐私和生命周期均由正式管理页接管，不继续扩展旧 PixiuApp 接线。
设备页展示实际节点、发现结果、同步状态和开关；令牌交换不等于摄像头扫码，
本地解除信任不等于远端已解除或数据已送达。偏好和冲突页区分加载、空态与失败，
冲突只读展示后端仲裁结果，不提供界面裁决或回滚。

正式托盘恢复同一主窗口，退出经过 HostCloseGuard；没有托盘仍可正常启动。
Ctrl+Alt+P 复用 ShortcutManager，ON 通过官方 SDK 与会话服务注册，OFF 或失败
降级为应用内快捷键。定向清理仅涉及 PIXIU 自身绑定，不影响其他应用或停止共享服务。
系统通知仅使用受限固定文案，不把敏感事件正文转发给桌面。完整通知与退出矩阵待验收。

## 实现状态（2026-08-10 更新）

本节不保留旧小窗口截图、演示数据与视觉完成声明。管理区已嵌入唯一宿主，
但源码清退、全部功能验证和完整新图库尚未完成。旧图库已撤下；新素材必须由
真实安装包、真实操作及明确标注的合成示例数据产生，不能把诊断图自动列为交付图。
主题和原生控件修复需核对同一构建，不能由离屏通过推导出全部桌面验收通过。

## 实现状态（2026-08-10 契约对齐更新）

当前公共接口见 `docs/API.md`；不再保留已经解除的历史端点阻塞或旧分支状态。
HttpBackendTransport 兼容统一错误对象及 FastAPI detail 错误形状；查询携带请求 ID，
管理组件串行处理详情和写请求，失败不伪装为空结果。TCP 契约回归与真实 portable
后端联调分开执行，二者均不能代替真实多设备传输或原生桌面验收。

## 开工要求（本地环境准备）

先完成根 AGENTS.md 的强制阅读，再核对当前代码与模块边界。官方 submodule 使用
仓库锁定提交，不修改上游工作树；唯一宿主适配在导出副本中应用已批准补丁。

```bash
git submodule update --init --recursive
cmake -S frontend/management -B <build> -DPIXIU_MANAGEMENT_TESTS=ON -DPIXIU_HAVE_KYSDK=OFF
cmake --build <build>
ctest --test-dir <build> --output-on-failure
```

依赖以管理 CMake、`build/release/profiles/` 和后端 requirements 为准。Qt Widgets、
Network、WebSockets 与 libqrencode 是管理库现有依赖；ON 另使用 Qt DBus 和画像
声明的快捷键/通知 SDK。后端有可测试的 portable 路径，不能再写成无 SDK 必然不可用。
正式 ON 验证还须准备麒麟 embedding/Vector Engine 绑定与真实桌面会话。

## 1. 模块概述

Module A 维护 `frontend/management/` 嵌入页、必要公共适配及测试。产品启动器
`build/release/debian/usr/bin/pixiu` 准备用户服务和 Agent 集成，再经随包
`launch-agent.py` 执行唯一 `kylin-agent` 宿主；不回退到第二套前端。

会话和模型/工具生命周期来自已批准的 openKylin 宿主与 Runtime；记忆业务由后端
公共接口提供。管理模块不实现另一个 Agent 循环，不直接访问后端数据库。
PixiuApp、FloatingBall、ChatWindow 等残留源码仍被回归引用，待按调用关系清退；
其存在不是产品入口或恢复旧交互的理由。

## 2. 源文件清单与实现优先级

保留原章节名称以维持引用；下表只说明当前归属和剩余清退边界，不采用星级、
日期或旧阶段完成率作为实施顺序。产品输入以管理 CMake 与宿主导出清单为准。

### 第一阶段：基础骨架

| 文件 | 当前归属 |
|---|---|
| `CMakeLists.txt` | 保留回归目标，无旧可执行产品或安装规则 |
| `management/CMakeLists.txt` | 嵌入静态库及管理测试 |
| `management/HostTray.*`、`HostCloseGuard.*` | 同一宿主恢复、退出与未保存状态保护 |
| `src/app/ShortcutManager.*`、`src/services/NotifyService.*` | 正式复用的 SDK/通用适配，不能随旧壳删除 |
| `src/app/PixiuApp.*` | 旧生命周期残留，非产品构建输入，待清退 |
| 宿主 ThemeManager 导出补丁 | 正式主题路径；旧 ThemeService 测试不能替代它 |

### 第二阶段：核心交互

| 文件 | 当前归属 |
|---|---|
| `management/MemoryWorkspace.*` | 检索、证据正文与文件来源的统一阅读器 |
| `management/AgentEvidence.*`、`AgentEvidenceClient.*` | 验证并读取实际 Runtime 会话工具来源 |
| `management/MemoryWriteDialog.*`、`MemoryEditDialog.*` | 所属宿主的文本录入、完整快照编辑与版本冲突保护 |
| `src/services/BackendTransport.*`、`HttpBackendTransport.*` | 公共 HTTP 通信与错误处理 |
| `src/widgets/ChatWindow.*`、`FloatingBall.*` 等旧聊天控件 | 不进入正式宿主，残留引用与测试逐项清退，不迁移其独立窗口 |

### 第三阶段：管理面板

| 文件 | 当前职责 |
|---|---|
| `management/MemoryAudit.*` | 偏好列表、历史、提取及只读冲突审计 |
| `management/ForgetPage.*` | 显式范围、一次性预览凭证与确认 |
| `management/DevicePage.*`、`PairingDialog.*` | 节点/发现、同步设置、令牌配对和信任解除 |
| `management/PrivacyPage.*` | 采集授权配置、目录和活动日志 |
| `management/DeliveryPage.*` | 实际洞察候选及按日期采集简报 |
| `management/SettingsWorkspace.*`、`ServiceStatusPage.*` | 应用/升级、隐私、服务能力及宿主配置入口 |

### 第四阶段：完善

| 文件或资源 | 当前职责与约束 |
|---|---|
| `management/BackendEventStatus.*` 与 `src/services/WebSocketClient.*` | 事件连接与页面失效通知，不执行广播中的命令 |
| `management/MemoryScopes.h`、`MemoryScopeControl.*` | 共用范围与显式自定义选择，不隐式合并旧数据域 |
| `src/app/UpgradeController.*`、`UpgradeUtils.*` 与升级对话框 | 同一产品的更新状态机及校验，保留有效公共代码 |
| `src/app/ProductInformation.h`、`src/widgets/InfoDialog.*` | 共用只读产品、数据边界及第三方说明 |
| `resources/icons/pixiu.svg`、desktop 文件 | 同一产品身份，宿主导出嵌入实际资源 |
| `resources/i18n/` | 保留有效公共翻译，正式管理模块完整翻译仍须补齐 |
| `src/models/` 与其余旧控件/控制器 | 按实际消费者区分复用与残留，不以目录整体删除 |

## 3. 与后端的接口契约

管理页依赖 `BackendTransport` 抽象，当前实现为 HttpBackendTransport；事件由
WebSocketClient 单独连接。正式引导器从有效 Agent profile 读取范围和 endpoint，
与 PIXIU 管理通信对齐，配置冲突拒绝启动。没有前端 D-Bus 业务 transport 或自动
D-Bus/HTTP 切换。下面保留原接口章节标题，但不再描述不存在的客户端类。

### MemoryClient 接口

不存在 MemoryClient 类。实际方法与用途为：

| BackendTransport 方法 | 公共端点/用途 |
|---|---|
| `queryMemory` | POST /memory/query，返回查询请求 ID |
| `writeMemory` | POST /memory/write，携带显式 scope 和幂等键 |
| `memoryItem`、`updateMemory` | GET /memory/items/{id} 与 POST /memory/update，完整快照及 expected_version |
| `memoryContext` | POST /agent/context，版本化召回，不作为编辑快照 |
| `evidenceDetail` | GET /evidence/{id}，核对所选 ID 及会话来源边界 |
| `reviewedForget` | POST /forget，一次性凭证预览与确认 |
| `preferencesList`、`preferenceHistory`、`extractPreferences` | 偏好列表、历史及证据驱动提取 |
| `listConflicts` | GET /conflicts，只读后端仲裁记录 |

方法、信号及参数以 `src/services/BackendTransport.h` 和 `docs/API.md` 为准。
旧 `forget(command, confirm)` 残留不是正式安全遗忘页的调用路径。

### SyncClient 接口

不存在 SyncClient 类。DevicePage/PairingDialog 经同一抽象调用实际接口：

| BackendTransport 方法 | 公共用途 |
|---|---|
| `listPeers`、`syncStatus` | 当前节点和同步状态 |
| `discoverDevices` | 实际局域网发现列表；合法空列表不等于失败 |
| `createPairingToken`、`pairDevice` | 生成与交换 PIN/QR 格式令牌 |
| `updateSyncSettings` | 明确提交 enabled/paused，不自动保存草稿 |
| `revokePeer` | 对指定非本机节点解除本地信任 |

抽象层还保留 `requestPairing` 与 `confirmPairing`，方法存在不代表正式页面已经完成
全部确认式配对入口。配对响应、身份、有效期和方法必须核对，不能由请求发出推导成功。

### WebSocket 事件订阅

BackendEventStatus 复用 WebSocketClient 连接 /events；事件通道在线不代表后端健康。
重连没有历史重放保证，提示重新核对数据。事件不覆盖未保存表单、不打开遗忘确认框。

| 事件 | 正式响应边界 |
|---|---|
| memory_ready / forget_confirmation | 记忆页面失效提示及接线刷新，不授权遗忘 |
| conflict_detected | 审计变化；仅 high/critical 请求限流固定通知，不传正文 |
| sync_event / pair_request | 设备变化提示及受控只读刷新，不接受配对请求 |
| capture_event | 采集日志变化提示，可见首页合并刷新，不传文件名或内容 |
| 连接恢复 | 各页面按自身在途/草稿/可见状态核对，不重放写请求 |

## 4. 关键状态与边界情况处理

本节描述当前实现约束，不以历史测试数量或旧版本桌面记录声明整体完成。完整
任务及限定到具体构建的原生证据见根统一计划；新增界面和生产发布仍需对应验证。

产品身份由宿主导出适配保持 PIXIU 名称、图标与 `com.kylin.pixiu` desktop 关联。
内部组织/应用身份和用户会话存储不因显示名变化而迁移或删除。恢复、单实例、托盘、
关闭和升级重启属于同一宿主，不恢复另一套生命周期。

HostCloseGuard 检查所属对话框、管理请求、会话在途请求、未发送草稿及采集/同步
未保存配置。确认默认保留，明确放弃不发送写请求；确认返回后再次核对在途状态。
`--quit` 先恢复窗口再检查。升级重启在调度 helper 前复用检查，仅排除发起重启的
对话框。UKUI 对退出按钮的处理已有专门原生测试，完整实际模型/升级退出矩阵尚未完成。

快捷键 ON 路径使用官方 SDK 和会话 D-Bus 就绪处理；缺少官方服务时按已接入入口
启动，等待或失败期间降级。SDK 配置缺失但 compositor 存在 PIXIU 自身残留时，
仅在确定错误条件下做一次定向恢复，不清空其他应用绑定。屏外恢复保留正常位置和
最大化/全屏状态；真实多屏和跨应用快捷键冲突仍须验收。

服务诊断串行读取 /health、/version、/capabilities，使用独立传输，失败或矛盾响应
不返回成功快照。周期健康探测校验实际 /health 就绪和数据库字段，不再探测冲突列表。
业务错误不覆盖健康失败，断开后迟到业务响应不恢复连接。事件连接状态与服务健康
分开显示；全宿主共用的能力/版本门控仍待完善。

MemoryScopes 保留本机采集域 user:local、家庭共享域及有效 Agent 域。MemoryScopeControl
可显式输入其他合法范围，界面上限 256 字符；选择不写数据、不隐式持久化或合并域。
录入只自动选择私有 Agent 域，Agent 配置共享不意味着本机采集自动共享。正式启动
只读解析 profile，不执行 shell 或向 Qt 传递凭证；错误拒绝启动。历史范围自动发现、
各入口长度约束统一与跨入口真实数据验收仍待完成。

证据正文优先展开 body.text/body.content、字符串 body 或顶层 text，并保留其他
结构化字段。普通展开限制约 64 Ki 字符、256 节点和深度 8，截断明确说明；高级 raw
保留完整 JSON，二者均为只读纯文本。来源或范围切换、会话变化和数据失效清空旧值，
迟到响应不能恢复正文；会话引用另核对当前 scope 和敏感级别，不把模型文字当引用。

schema 13 的 capture_source 独立显示，不混入正文或高级 raw。有效元数据展示采集
方法、JSON 转义路径、UTC 时间和存在性限制；支持 0～253402300799 秒。来源文本框
高度上限 110 像素并可滚动复制，不自动打开文件。缺失/null 与非法来源分别显示紧凑
可选取标签，隐藏并清空独立文本框，不推测路径。阅读区横向分栏，左侧摘要/来源
列表，右侧元数据/正文；可调宽度而不允许折叠，两侧最低宽度分别 200/400 像素。
正文最低 100 像素并使用右侧剩余高度。新增几何和状态回归通过，
完整管理 12 组与宿主导出检查通过。新合成目录文件的实际来源链路已完成原生
核对，采集授权随后恢复全关。d5167fe 原生复测确认分栏可拖动，来源四行信息
与多行正文可同时阅读，正文/raw 往返及范围切换清空通过。完整主题、键盘、
长路径和异常矩阵仍待补齐，不作为最终图库验收。

AgentEvidence 只接受当前会话、当前范围、具有匹配开始/完成记录的
pixiu_memory_search 工具结果。输入上限 2 MiB、来源上限 256，重复去重；
其他工具、分支、非法 ID 和损坏记录不返回部分有效引用。AgentEvidenceClient
有超时、流式大小上限、取消和拒绝重定向；不输出认证配置或原始错误正文。
宿主按钮导航到同一阅读器，会话/后端切换取消请求并清空来源；完整异常矩阵待验证。

文本录入提交时禁用重复保存和关闭，失败保留输入及同载荷幂等键；仅合法 accepted
且 evidence_id 非空才清空输入，不把接收成功称为跨设备送达。当前不提供附件 OCR
录入表单或敏感预览标记，共享敏感内容由后端拒绝。

编辑读取明确 scope 的完整知识快照，不使用召回摘要填充正文；提交 expected_version
与幂等键。无修改不可保存；文本/高级 JSON 切换保留附加字段，非法结构不能静默丢弃。
版本冲突保留输入、拒绝覆盖并要求刷新，不自动重试；在途拒绝关闭。
实际后端联调使用现有依赖和独立临时数据：

```bash
python frontend/management/tests/run-memory-edit-live.py <管理构建目录>/t_memory_edit_live
```

该脚本启动真实 portable 后端，使用动态端口、临时数据库和独立 XDG 目录，关闭
采集及同步网络；Qt 操作后由另一路 HTTP 核对数据和版本。它不是麒麟 SDK 或
安装后真实桌面验收。复杂字段、缩放和完整故障矩阵仍待补齐。

MemoryAudit 展示偏好、所选记录历史和后端冲突双方；提取只用已有证据 ID。
列表与历史区分加载、空态、错误；损坏或 ID 不匹配响应拒绝展示。已知仲裁结果有
中文解释并保留枚举，未知值不伪装成功，MANUAL 不宣称人工裁决已完成。
事件合并只读刷新，在途提取不重放；记录消失清空详情。变化通知按 scope/id/版本
建立基线，首次加载、重复、回退和损坏记录不推断学习；只传数量与固定通知文案，
不暴露偏好值。真实提取、通知及完整错误态仍须验收。

ForgetPage 要求显式范围和一次性预览凭证；编辑命令/范围、到期、取消或失败使
凭证失效。确认核对预览知识 ID，未知关联计数不显示成零。失败可能已经部分生效，
必须先检索核对、重新预览，不能自动确认重放。广播不构成用户授权，后端确认不证明
所有设备送达；完整 outbox、崩溃恢复与跨设备遗忘链仍待验证。

DevicePage 串行读取配置/节点/状态，本机不可解除信任。发现空列表与网络失败分别
展示；保存超时不假定生效。事件只读刷新在隐藏、在途或有配置草稿时延后，按 ID
恢复选择，目标消失则清空。解除确认默认取消，并保护嵌套事件循环中的目标。
全部退出需读取、确认、串行解除、关闭网络后再核对，失败中止。PairingDialog
检查令牌方法、有效期及成功响应，失败保留输入，关闭清理令牌；不是摄像头扫码。
双端/多端配对、实际传输与全部退出尚未完成原生验收。

PrivacyPage 必须先读取完整配置才允许保存。目录要求绝对路径并去重，保存是明确
用户动作；错误保留编辑，未实现的剪贴板/截图配置字段原样保留但不宣称可用。
日志分页不覆盖配置，可见首页合并刷新，历史页不自动跳转。目录文本采集与文件
来源已有后端链路，新目录文本元数据已完成原生核对；OCR 绑定、权限失败与停用竞态仍待验证；
配置保存成功不能证明采集成功。

DeliveryPage 读取后端实际洞察，标题跳转限定本机个人域；不提供伪造静态候选。
简报按后端本地日期聚合采集日志，不代表全部记忆量。日期变化清空旧正文，在途
禁用编辑，错误日期或迟到响应拒绝；事件失效保留所选日期。已完成一条真实目录
合成记录的非空洞察→检索→正文路径，完整候选、日期、计数和错误矩阵仍未完成。

SettingsWorkspace 复用宿主模型配置入口、升级状态机和 InfoDialog。关于、数据与
联网、第三方说明共用 ProductInformation，说明共享、模型发送、采集及遗忘边界，
不承诺“永不上传”或“任意清除”。升级 helper 位于根发布包体目录，无独立前端包；
成功后用户选择重启才退出整个宿主。真实图形授权、签名异常、安装失败、回滚、
重启及配置/数据保留矩阵仍须完成。

正式 ThemeManager 的普通容器、选中项、日期/日历、复选框样式与延迟对象生命周期
已有导出回归和局部原生验证。完整语言、主题、焦点、DPI、多屏及所有页面仍未验收。
旧 ChatWindow 洞察卡、DeliveryController 和部分重复通知已清退。旧遗忘广播的
确认执行接线、命令缓存与 confirmRemote 方法已删除，不继承无预览凭证流程；
正式广播只读提示和安全遗忘回归保留。其余旧控件、
控制器与测试按调用关系继续移除，不删除仍被正式宿主复用的公共升级/SDK代码。

| 场景 | 当前正式界面行为 |
|---|---|
| 检索加载 | 状态行提示，禁用重复检索；不宣称骨架屏或顶栏进度条 |
| 检索失败 | 保留输入，说明原因，可再次点击检索 |
| 空结果 | 与失败区分，保留独立录入入口 |
| 长正文 | 纯文本滚动阅读，普通展开有界，高级 raw 可查看完整数据 |
| 共享敏感写入 | 后端拒绝后显示失败，不自动改域或宣称已共享 |
| 同步 | 设备页显示实际返回值，本地成功不代表远端完成 |
| 遗忘 | 页内预览、明确确认、一次性凭证；失败要求先核对 |
| 事件离线 | 明确可能过期，不等同于健康检查结论 |

## 5. 开发降级方案

非麒麟开发机仍构建同一宿主，不恢复悬浮球或旧聊天程序。

- 管理组件测试显式使用 `PIXIU_HAVE_KYSDK=OFF`；完整宿主/打包脚本使用
  `PIXIU_KYSDK=OFF`。不能混淆两个入口的变量名。
- 快捷键降级为应用内 QShortcut；通知使用托盘/日志降级，界面明确可用范围。
- 后端 `PIXIU_EMBEDDING=portable`、`PIXIU_VECTOR_STORE=portable` 提供真实软件
  路径，不是测试桩。质量和性能不能等同麒麟 SDK；auto 与严格 kylin 的语义见后端配置。
- 管理 HTTP 地址使用 `PIXIU_BACKEND_URL`，正式启动由 profile 引导器对齐；直接启动
  宿主不等于完成该配置检查。没有前端 D-Bus 自动回退。
- 测试桩只验证契约或控件，不能用于最终截图、真实 SDK、安装或多设备验收。

## 6. 参考文档

| 内容 | 路径 |
|---|---|
| 当前前端架构与组件职责 | `frontend/docs/ARCHITECTURE.md` |
| 完整迁移、清退及交付任务 | `docs/UNIFIED_FRONTEND_PLAN.md` |
| 已批准的唯一宿主边界 | `docs/decisions/0006-unify-agent-desktop-frontend.md` |
| 公共 API 请求/响应 | `docs/API.md` |
| 包体与发布门禁 | `docs/DELIVERY_PLAN.md` |
| 官方快捷键模块 | `docs/kylin_sdk_docs/8_Desktop_Environment_SDK/8.3_Hotkey_Module.md` |
| 官方通知模块 | `docs/kylin_sdk_docs/8_Desktop_Environment_SDK/8.2_Notification_Module.md` |
| 官方主题模块 | `docs/kylin_sdk_docs/8_Desktop_Environment_SDK/8.5_Theme_Module.md` |
| 只读赛题原件 | `docs/OriginProblemDescription.md` 与 `docs/完整赛题要求.pptx` |
