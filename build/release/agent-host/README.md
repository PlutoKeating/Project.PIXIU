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

同一补丁还执行负责人批准的云端模型边界：新装和既有配置补入并优先显示 DeepSeek
官方 `deepseek-chat`，宿主下拉框只展示 DeepSeek、Anthropic、OpenAI 直连云端模型；
OpenRouter 与 Ollama/LM Studio/vLLM/llama.cpp 等本地入口不进入产品选择面。API Key
只由 Runtime 安全认证存储接收，不能进入宿主模型文件、命令行、源码或构建证据。

构建脚本必须在洁净的固定上游归档中按编号顺序应用补丁；任何 hunk 不匹配都立即失败。最终宿主
产物、完整已补丁源码、构建日志和摘要必须由供应链记录器生成，不能用本目录本身代替
目标 V11 构建证据。

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
