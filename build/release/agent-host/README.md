# openKylin Agent 宿主发行适配层

本目录只保存 PIXIU 对固定上游宿主的可审计构建适配，不修改
`third_party/kylin-agent`。上游固定 commit、许可证和证据要求以
`../agent-supply-chain-policy.json` 为准。

`patches/0001-build-coherent-offline-host.patch` 修正上游当前公开树中两类可复现的
构建断裂：入口仍引用已被 `GatewayService` 替代的旧类；CMake 同时编译一批不在当前
简化桌面流程中的半成品设置页，导致其未实现方法参与链接。补丁只保留当前主窗口、
会话、模型选择与 Runtime 聊天路径，并加入 `compat/pixiu_host_compat.cpp`，恢复真实
SSE 对话取消/完成语义以及窗口激活行为。它不是空桩，也不绕过 Runtime。

`patches/0002-pixiu-premium-accessible-ui.patch` 是 ADR-0004 批准的纯表现层补丁：
移除主窗口、侧栏、会话列表和聊天区的局部硬编码颜色，以浅/深两套语义令牌统一
PIXIU 品牌栏、云端模型入口、消息、输入区和状态反馈，并删除空状态中的内部数据库
路径。关键配色由 `test-agent-host-ui-contrast.py` 复算 WCAG AA 4.5:1；补丁不改变
会话、工具、Runtime 或 MemoryProvider 语义。
消息行不得以裸 `QLayout` 嵌入画布：每行必须由 `messageRow` widget 持有气泡与
布局，`clearMessages()` 删除该 widget 时递归释放子控件。这一所有权规则防止历史
刷新或侧栏折叠后的重复气泡、错位残影和空状态遮挡，由
`test-agent-host-adaptation.sh` 失败关闭。
聊天区采用最大 920px 的居中单列阅读流：用户消息在列内右对齐，PIXIU 回复在列内
左对齐并显示稳定的作者标识；输入区使用最大 960px 的居中组合框。该约束避免宽屏下
消息散落在窗口两端，同时保留 760px 最小窗口下的自适应空间。

`patches/0003-kylin-cloud-model-settings.patch` 实施 ADR-0005：新装与升级首次默认选择
“麒灵系统云模型”，通过回环 Kylin GenAI 适配服务跟随系统模型和授权。备用选择面只
展示 DeepSeek、Anthropic、OpenAI 官方直连服务；API Key 从宿主密码框输入，连接检测
通过后由 Runtime 以本用户权限原子保存。宿主模型文件、命令行、日志和构建证据均不
包含真实密钥。OpenRouter 与 Ollama/LM Studio/vLLM/llama.cpp 等入口不进入产品界面。

`patches/0004-working-agent-experience.patch` 将桌面端收敛为默认浅色的工作型 Agent
界面，统一浅/深语义色板与原生窗口层级；Enter 发送，Shift+Enter/Ctrl+Enter 换行；
发送后立即显示等待气泡，并把每轮模型文本、工具生命周期和分支过程按顺序渲染为
独立消息与默认折叠的动态工作进度卡。兼容层按完整 SSE frame 解析普通 `data:` 与
命名 `event:`，在工具开始处生成消息段边界，工具前后的模型文本不会相互覆盖。

`patches/0005-blue-theme-settings-and-pixiu-soul.patch` 采用 Ant Design 语义体系的
稳重科技蓝统一浅色与暗色主题，为设置页增加即时生效并持久化的“浅色 / 深色”分段
控件；同时将宿主身份收敛为 PIXIU 本地 Working Agent，并在每次启动 Runtime 前写入
同包 `SOUL.md` 的正向产品身份。浅色仍是首次启动默认值。

`patches/0006-rich-message-rendering.patch` 将消息气泡升级为 Qt WebEngine 离线富文本
视图。页面内嵌 markdown-it、markdown-it-texmath、KaTeX、Mermaid 及公式字体，覆盖
标准 Markdown、GFM 表格、代码块、复杂公式、思维导图、流程图、甘特图和通用 Mermaid
图表；包内 Noto Color Emoji 提供完整 Unicode emoji 字形。渲染页以 CSP 禁止联网、
任意 HTML 与远端资源。Shell、Web 搜索、记忆、技能和其他工具事件使用默认折叠的动态
工作卡片；运行时显示呼吸式省略号与进行项数，完成后以专用历史记录持久化，重新进入
会话仍保持折叠卡片。工作卡片记录不会进入后续模型上下文。
WebEngine 内的滚轮事件会转交外层会话滚动区，长消息中的表格和图表不会阻断整页滚动。

`patches/0007-chat-layout-follow.patch` 为发送、流式文本、工作事件和富消息异步高度变化提供
一致的最新消息跟随，并将工作卡片放入助手消息的左侧内容列。渲染资源以文本字体优先、
彩色 Emoji 字体回退并固定自然词距，避免 Emoji 字体的宽空格度量拉伸英文、中文与行内
代码。`patches/0008-pixiu-assistant-history.patch` 在既有助手
历史进入模型上下文时统一 PIXIU 身份，同时完整保留用户消息原文。

构建脚本必须在洁净的固定上游归档中按编号顺序应用补丁；任何 hunk 不匹配都立即失败。最终宿主
产物、完整已补丁源码、构建日志和摘要必须由供应链记录器生成，不能用本目录本身代替
目标 V11 构建证据。
宿主记录同时绑定当前 release commit，以及构建脚本、全部补丁、离线渲染资源和兼容层源码的逐文件
SHA-256。任一适配输入或提交变化都会使旧宿主证据失效，严格打包必须重新构建并记录，
不能在新候选中复用旧二进制。

`patches/0010-embedded-memory-workspace.patch` 将 `frontend/management` 静态模块
接入同一主窗口的“记忆”页签，会话页实例不会因页签切换销毁。自有界面和共用 HTTP
源码复制进宿主对应源码树，并逐文件纳入供应链摘要；不编译旧 PixiuApp 或聊天外壳。
嵌入模块现覆盖检索、证据正文查看和带幂等重试的手动文本录入；旧可执行程序尚未从统一包删除。

`patches/0009-optional-kylin-desktop.patch` 按 ADR-0006 将实际编译路径中的对话框
接入 `compat/pixiu_desktop.h`。默认 `PIXIU_HAVE_KYSDK=ON`，使用官方 KDialog、
KInputDialog、KMessageBox；`build-agent-host.sh` 接收 `PIXIU_KYSDK=OFF` 时，
同一宿主改用 Qt 对话框，保留内容、输入、确认与取消语义，不提供麒麟专有标题栏样式。
SDK 专有按钮提示仅在原生路径编译。通用 CI 编译完整宿主并测试对话框交互；这不是
Runtime、管理模块或原生 SDK 验收，也尚未替代通用安装包中的旧前端入口。

源码准备统一由 `prepare-agent-host.sh <已存在的空目录>` 执行，构建器与
`test-agent-host-adaptation.sh` 调用同一入口。该入口验证固定提交和 submodule 洁净状态，
拒绝非空目录或符号链接目标，不删除目标已有内容。它统一导出、应用补丁、复制自有资源
和清理发行源码；测试另行独立扫描最终树，避免构建与测试维护两份处理逻辑。
该脚本自身也列入供应链输入摘要。唯一前端管理模块接入按 ADR-0006 和
`docs/UNIFIED_FRONTEND_PLAN.md` 实施；源码准备统一不表示界面迁移已完成。

固定上游还包含一条带用户信息的 clone URL 和两个未参与编译的在线 Runtime bootstrap
脚本。构建器严格要求命中且只命中一次，将该 URL 改为公开上游地址，并从“对应源码”
发行归档删除两个未编译脚本；上游结构变化会失败关闭。原始 submodule 保持只读，
审计报告只公开命中文件与处理结果，不复制认证信息。

原始只读上游参考树的命中会继续作为非阻断发现列入审计；发布硬门检查实际发行适配
源码，并由宿主证据记录器再次递归扫描最终“对应源码”归档。这样既不篡改事实，也不
让永远只读的参考副本使已经清除问题的发行产物永久无法过门。

宿主启动阶段还被明确改为只接受同一 Debian 包提供的、哈希锁定的 Runtime launcher；
不会执行上游联网安装器，也不把可选 CUA 当作 Shell/联网搜索/记忆工具主链的前置条件。
Runtime 不存在时启动失败关闭。
