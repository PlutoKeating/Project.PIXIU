# PIXIU openKylin Agent 适配器（Module E）

本目录包含 PIXIU 原创 MemoryProvider、文档 MCP、受控 Dreaming 执行器及 Runtime 适配，只通过 `docs/API.md` 的公共 HTTP 契约连接记忆服务。正常对话、Shell、联网搜索和工具调度复用上游 Runtime，不修改 `third_party/` 工作树。

## 已实现边界

- 启动时读取 `/version`、`/health`、`/capabilities`；校验 Agent Memory API v1、
  后端组件身份、Provider/后端同包版本与已验证 runtime 0.9.x。严格模式还要求明确
  的发行版本，以及麒麟 V11 与两个指定 SDK 均实际启用。
- turn 写入、生命周期事件和召回进入有界后台队列；写入携带 session/run/turn
  provenance 与幂等键，队列满时不阻塞 Agent，并通过 `diagnostics()` 暴露丢弃数。
- `prefetch` 优先读取缓存，首次召回尚未完成时在既有 HTTP 超时内请求当前问题；召回结果中的 `memory-context` 边界文本先被中和，再由
  上游统一安全围栏包装。
- 映射 turn start/end、pre-compress、session switch/end、delegation。
- 暴露记忆 search/remember/update/forget、sync_status 及 `pixiu_document_read` 工具。更正使用目标 ID 和版本；遗忘只预览并交接桌面确认，模型不能执行删除或获得审批凭证。
- 文档工具每次读取一个原文块；文字返回 JSON，图像复用 Runtime 的 `_multimodal` 内容格式，将页面作为真实图像交给当前模型。模型不支持图片时拒绝视觉读取，纯扫描附件在上传时停用。
- 超过两个内容块的附件保留既有 24 小时文档引用，模型沿 next_cursor 读取，后续问答可回读；短附件直接传递。分块不等于模型已完整理解，真实模型容量和全文任务验收仍未完成。

`.deb` 已携带只读 Provider，并由 PIXIU 桌面启动器幂等部署/升级到当前用户 Agent
profile；激活器会在变更前拒绝不受管插件、符号链接或非 Gateway 用户 unit，并为
Provider、`SOUL.md`、`.env`、Runtime 配置及迁移 unit 建立事务快照。`SOUL.md` 使用
纯正向身份定义，将助手定位为 PIXIU 本地 Working Agent 与分布式记忆工作台。写入配置或启动包内 Gateway
任一步失败会恢复原状态；成功激活会显式重启已运行的包管 Gateway，使新 Runtime 和
配置立即生效；每版被迁移 unit 另按内容哈希保留可恢复副本。服务端失败
receipt 管理亦已实现。V11 安装包同时启用回环 Kylin GenAI 适配服务，默认
`kylin-default` 不指定部署类型，按系统 AI 模块管理优先级选择；显式选择目录中的云端模型时才指定 PublicCloud，避免默认模型初始化返回 MODEL_NOT_FOUND（10）。Runtime 的会话、工具、审批和记忆循环保持不变。
适配服务先配置模型再初始化 SDK 会话，使用 SDK 原生聊天、工具回调和结果续传接口；
先前轮次按角色封装为系统上下文，因此多轮语义与自主工具执行可同时保持。
OpenAI-wire 请求携带完整会话历史时，适配器只把最近一条 assistant tool_calls 之后的
当前工具结果批次提交给同一个 Kylin GenAI 原生会话；历史已完成工具结果不会混入
当前 pending call，连续工具调用可完成 running、completed 与下一轮模型回复闭环。
Runtime 发行适配会在系统提示、动态上下文、技能目录与工具 schema 进入模型前统一使用
PIXIU 产品名称和公共工具术语；宿主向模型回灌历史时同步规范助手消息身份。该处理只作用于
模型输入，不改写用户原文和本地会话记录。

宿主消息资源位于 `frontend/resources/message_renderer/`，随固定上游补丁构建为 `qrc:` 离线页面：
markdown-it 负责 Markdown 与表格，markdown-it-texmath + KaTeX 负责公式，Mermaid
负责思维导图、框图、甘特图和流程图，Noto Color Emoji 负责彩色 emoji。工具生命周期
事件独立保存为默认折叠工作卡片；会话历史组装会过滤该 UI 角色，仅将用户与模型消息
发送给 Runtime。渲染页以 CJK 文本字体承载正文与普通空格，彩色 Emoji 字体仅作字形
回退，并显式使用自然词距和起始方向对齐；消息发送、流式分段、工作事件
以及 WebEngine 异步高度变化都会触发会话跟随到底部。工作卡片与助手消息共享左侧内容列。

用户可从宿主 GUI 导入官方直连 API Key。管理接口只返回是否已配置的布尔状态，空白
输入保留原凭据，显式清除才删除；探测拒绝非 HTTPS 远端地址和重定向。
Gateway 的健康检查、能力发现和模型目录统一以 `pixiu` 标识平台与所有者。

发布测试已用确定性、无推理的 OpenAI-compatible 节点，经真实 Runtime/Gateway 验证
Provider 的本地/共享记忆写入、检索、更新和同步状态工具链，以及系统提示和逐轮增长的
会话历史；去敏 trace 还断言 system prompt 内的四项记忆操作契约、按原顺序保留的用户
轮次、assistant/tool 回灌，以及五个 PIXIU 工具的关键参数 schema。该结果仅证明集成
接线，不证明模型自主规划，也不属于最终原生验证证据。

源码只维护 `plugin.yaml.in`，其中版本为 `@VERSION@` 占位符；开发态兼容检查读取
仓库根 `VERSION`，发布打包时才生成 Agent 可发现的合法 `plugin.yaml`。禁止在
Module E 中另行维护静态产品版本。

## 宿主兼容基线

当前契约测试固定使用：

- `third_party/kylin-agent-runtime` commit
  `92c57beb0d6ff1ec5df6bf9a1919a73b1a244012`
- `third_party/kylin-agent` commit
  `1334c8ee9765a2e1649276b3bca21188598ff445`

上述固定版本的可执行包/模块存在 0.9.8/0.9.4 元数据差异，故运行时兼容窗口按经测试
的 0.9.x 定义，而非锁死单个补丁号；0.10+ 与不可解析版本明确拒绝。扩大范围前必须
更新 submodule、复跑发现/生命周期/工具契约并提交审查证据。

运行时按上游规则从 `$HERMES_HOME/plugins/pixiu/` 发现本插件，并在 `config.yaml`
把 `memory.provider` 设为 `pixiu`。正式安装必须由发布包完成这些操作；不要手工修改
submodule。

## 配置

| 变量 | 默认值 | 含义 |
|------|--------|------|
| `PIXIU_AGENT_ENDPOINT` | `http://127.0.0.1:8765` | PIXIU 公共 API |
| `PIXIU_AGENT_SCOPE` | `user:default` | 强制作用域；仅允许 `user:*` / `shared:*` |
| `PIXIU_AGENT_STRICT` | `0` | `1` 时要求 `/capabilities.contest_ready=true` |

## 契约测试

```bash
python3 -m pytest -q backend/agent/tests
```

契约测试覆盖上游 ABC/插件发现、宿主/API/组件/健康握手、HTTP API 0.5
兼容门禁、真实后端错误码透传、严格能力拒绝、非阻塞
召回、对话 provenance、六类生命周期映射、重试/背压诊断、五个工具、版本化更新、两阶段遗忘
和错误脱敏。测试无需启动真实后端。

Provider 现只接受 HTTP API 0.5.x，拒绝不具备后端预览凭证协议的 0.3/0.4 以及
未经验证的后续 minor。产品版本和 Agent Memory API v1 不随 HTTP minor 混用。

## 2026-09-10 助手记忆范围

`GET/PUT /agent/settings` 读取/保存 include_capture（默认 true）、shared_scopes（默认空数组，仅 shared:*）、write_scope（默认 null，沿用当前 Agent）。设置保存于本机安全偏好，不随记忆共享同步。`POST /agent/context` 的可选 use_settings 默认 false；Agent 设置为 true 时，默认个人 user:default/user:local 可读取授权采集，另外查询用户选择的共享空间，返回 read_scopes。自定义个人范围保持隔离。显式记忆工具按 write_scope 保存，普通会话保存范围不变；设置页面分别控制读取与保存，不迁移已有数据。不新增依赖或数据库 schema。

## 2026-09-10 偏好与账单使用

普通 CONVERSATION 从用户原话提取输出风格，不从助手回答反向推断；沿用稳定偏好 ID、版本和历史。Agent 上下文返回 preferences 并优先放入当前有效回答风格；首次会话预取未完成时在既有 HTTP 超时内读取当前问题，避免漏掉已保存偏好。金额查询按账单明细类别/标签及日期筛选，汇总同范围的多份有效账单；指定类别没有记录时不再退回整份总额。未改变依赖和数据库 schema。

预取来源：后台 context 请求带 trace=true，缓存连同 trace_id 保存；实际 prefetch 消费缓存后排队确认使用。同步读取与显式搜索带 consumed=true。桌面从 /agent/sources 获取同一会话的实际来源。

账单修正：聊天 update 可使用搜索返回的 scope；对结构化账单的单项金额更正保留其他明细与日期，目标不明确返回 BILL_ITEM_CORRECTION_REQUIRED。按月查询在明细/正文日期缺失时使用明确的账单标题年月，不猜测录入时间为账单日期。

图片知识提取：runtime/image_draft.py 被构建为 gateway.pixiu_image_draft，由自有 Runtime 补丁暴露经过现有认证的 /api/memory/image-draft。复用保存的模型地址/凭据，模型直接接收图片，返回待核对 JSON，不运行 Agent 工具或记忆生命周期。当前支持 OpenAI 兼容图片接口；麒麟文本 GenAI 桥接明确拒绝图片。

## 源码目录与安装目录

Agent 自有源码统一位于 `backend/agent/`，仓库根目录不再保留 `integrations/`。
2026-09-10 已清除旧根目录中被 Git 忽略的 Python 字节码缓存及空目录，并检查正式源码、构建与启动引用。
安装包仍将 Provider 部署到 `/usr/lib/pixiu/integrations/kylin_agent/`；这是已批准迁移计划保留的安装路径，
由打包脚本、用户插件激活器、桥接服务和升级检查共同使用，不是第二份源码目录。
`build/release/out/stage/` 下的对应目录是打包暂存产物，不作为源码交付。
文档解码归 `backend/foundation/documents/`，MCP 与 dreaming 归 `backend/agent/` 内部子模块，
不重新引入根级集成目录，也不在 build 内维护产品实现。

`mcp/` 使用 SDK 1.26.0，通过公共文档 API 提供任务授权范围内的真实 stdio 工具；`dreaming/session.py` 提供固定私人范围的检索、来源校验、计划及获准创建，向量更新沿既有 `/memory/write` 进行。目录已接 Runtime 认证入口与逐块模型工具循环，聊天附件已调用同一 MCP 文档工具读取所有内容块，结束撤销暂存。模拟模型链路通过不代表真实模型或最终包已交付。构建包携带这两个模块，离线依赖锁与最终安装包按文档计划验证。

后台整理进度：Runtime harness 在读取开始、每批模型处理后及结束时调用 `POST /documents/{document_id}/progress`，以有效文档引用重新检查授权与数量边界；模型工具不包含该接口。后端经既有 WebSocket 发送 `dreaming_progress`，仅包含状态、处理数量和保存数量，不广播文件名或原文。主窗口自动显示进度/完成/未完整整理，无需刷新或确认；不新增依赖或数据库表。

Dreaming corrections use memory_read + memory_plan(operation="update") and the existing versioned update API. Each update needs trusted per-plan approval, which is never an MCP tool. Directory approval remains create-only. Desktop approval and merge integration remain on the 0.1.10 completion plan; no additional dependencies.

2026-09-10：Dreaming 更正方案持久化到私有 schema v15 表 dreaming_plans，公共接口 `/dreaming/plans`（GET/POST）及 `/{id}/decision`（POST approve 布尔值）；模型工具只提交方案，审批由桌面操作执行。`dreaming_review` 事件只携带方案 ID 与状态，桌面重新读取方案列表。`dreaming_progress` 新增 awaiting_approval 状态。界面仅有待办时展示入口，审批前后内容可对照；已批准写入沿现有版本化更新服务。新增 Qt 对话框已登记 CMake/宿主导出清单，无新依赖。合并仍在实施。
