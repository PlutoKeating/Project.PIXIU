# ADR-0005：优先使用麒灵系统云模型

- **状态**：已批准（Accepted）
- **日期**：2026-09-05
- **适用范围**：KylinAgent 宿主、Agent Runtime 发行适配、银河麒麟 V11 安装画像

## 决策

PIXIU 在银河麒麟 V11 上默认使用系统 `libkysdk-genai-nlp` 提供的 PublicCloud
文本模型。宿主将“麒灵系统云模型”置于模型列表首位，新安装或升级后首次激活时选择
`kylin-default`；实际模型跟随系统“AI 模块管理”的选择与授权，PIXIU 不读取、复制或
保存系统云模型凭据。

KylinAgent Runtime 保持会话、规划、工具调用、审批和 MemoryProvider 主循环。PIXIU
提供仅监听回环地址的 OpenAI-wire 适配服务，把 Runtime 的消息、工具 schema 和工具
结果转换为 Kylin GenAI SDK 的会话、回调及 continuation 接口。只有
`PublicCloud` 且声明支持 tool choice 的系统模型进入 Agent 可选集合。

用户仍可在 KylinAgent 的“云端模型设置”中导入 DeepSeek、Anthropic 或 OpenAI
官方直连 API Key。输入框使用密码模式；Runtime 在本用户配置中以 `0600` 原子写入，
管理 API 只返回 `credential_configured` 状态。保存前必须验证 HTTPS 地址、认证和模型
ID；探测不跟随重定向。OpenRouter 中转及本地推理入口不进入产品选择面。

## 边界

- `third_party/kylin-agent*` 继续只读；全部变更以 `build/release` 下的顺序补丁交付。
- 桥接服务仅监听 `127.0.0.1` 或 `::1`，不提供局域网服务。
- 系统模型允许回环 HTTP 且不需要用户 API Key；外部服务只允许 HTTPS。
- 赛题指定的 Embedding SDK 与 Vector Engine SDK 仍分别承担向量化和向量存储；本决策
  只确定 Agent 推理模型接入，不把 GenAI SDK 表述为赛题硬门槛。
- 缺少 Kylin GenAI SDK 的 Debian 通用画像仍可运行 PIXIU 记忆服务，并使用用户配置的
  官方直连模型。

## 验证

发布门验证系统模型发现、真实生成、工具回调与结果续传、停止/超时、GUI 凭据脱敏、
首次默认选择、服务启动顺序和安装依赖。供应链证据绑定 Runtime/宿主补丁及构建输入
SHA-256，任何适配变化都要求重建同版产物。
