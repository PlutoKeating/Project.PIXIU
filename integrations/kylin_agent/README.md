# PIXIU openKylin Agent 适配器（Module E）

本目录是 PIXIU 原创的 `MemoryProvider` 插件，只通过 `docs/API.md` 定义的公共
HTTP 契约连接记忆服务。它不包含、不复制 Agent 的会话、模型规划、Shell、联网
搜索或工具循环，也不修改 `third_party/` 上游工作树。

## 已实现边界

- 启动时读取 `/capabilities`；`PIXIU_AGENT_STRICT=1` 时，非麒麟 V11 或任一指定
  SDK 未实际启用都会拒绝初始化。
- turn 写入、生命周期事件和召回进入有界后台队列；写入携带 session/run/turn
  provenance 与幂等键，队列满时不阻塞 Agent，并通过 `diagnostics()` 暴露丢弃数。
- `prefetch` 只读取缓存；召回结果中的 `memory-context` 边界文本先被中和，再由
  上游统一安全围栏包装。
- 映射 turn start/end、pre-compress、session switch/end、delegation。
- 暴露 `pixiu_memory_search`、`pixiu_memory_remember`、`pixiu_memory_forget`、
  `pixiu_sync_status` 四个稳定 JSON 工具。遗忘必须先预览，再使用 120 秒内的一次性
  token 执行；工具说明要求第二步前取得用户明确确认。

当前未完成：随 `.deb` 自动部署到当前桌面 Agent profile、真实宿主多轮端到端取证、
失败 receipt 管理、生命周期长期化策略。因此本目录通过契约测试不等于完整 Agent
验收通过。

## 宿主兼容基线

当前契约测试固定使用：

- `third_party/kylin-agent-runtime` commit
  `92c57beb0d6ff1ec5df6bf9a1919a73b1a244012`
- `third_party/kylin-agent` commit
  `1334c8ee9765a2e1649276b3bca21188598ff445`

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
python3 -m pytest -q integrations/kylin_agent/tests
```

测试覆盖上游 ABC/插件发现、严格能力拒绝、非阻塞召回、对话 provenance、六类生命
周期映射、重试/背压诊断、四个工具、两阶段遗忘和错误脱敏。测试无需启动真实后端。
