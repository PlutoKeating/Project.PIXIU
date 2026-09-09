---
title: API 与配置
---

# API 与配置

PIXIU 记忆服务默认使用本机回环地址 `http://127.0.0.1:8765`。这些接口服务记忆能力，不是聊天补全 API。

## 先做只读检查

::: code-group

```bash [服务健康]
curl --fail http://127.0.0.1:8765/health
```

```bash [实际能力]
curl --fail http://127.0.0.1:8765/capabilities
```

```bash [组件版本]
curl --fail http://127.0.0.1:8765/version
```

:::

## 写入和查询示例

下面的写入会在本机 `user:website-demo` 范围创建真实记忆。仅在你准备好保存这条合成内容时执行；官网不会代你调用本机服务。

```bash
curl --fail-with-body http://127.0.0.1:8765/memory/write \
  -H 'Content-Type: application/json' \
  -d '{"source_type":"MANUAL_CONFIG","raw":{"title":"官网练习：输出顺序","body":{"text":"先给结论，再列待办"}},"scope":"user:website-demo"}'
```

使用同一范围查询：

```bash
curl --fail-with-body http://127.0.0.1:8765/memory/query \
  -H 'Content-Type: application/json' \
  -d '{"text":"输出顺序","context_hint":{"scope":"user:website-demo","top_k":5}}'
```

保存响应中的证据引用，到管理页核对来源。空结果应从写入、范围与索引状态排查。

## 端点按职责分类

| 分类  | 代表端点                                           | 用途                   |
| ----- | -------------------------------------------------- | ---------------------- |
| 诊断  | `/health`、`/version`、`/capabilities`             | 就绪、版本、实际适配器 |
| 记忆  | `/memory/write`、`/memory/query`、`/memory/update` | 写入、检索、乐观锁更新 |
| 来源  | `/evidence/{id}`                                   | 证据详情               |
| Agent | `/agent/context`、`/agent/lifecycle`               | 上下文与生命周期       |
| 管理  | `/preferences`、`/conflicts`、`/forget`            | 偏好、审计、两段遗忘   |
| 同步  | `/sync/peers`、`/sync/status`                      | 可信设备和状态         |
| 采集  | `/monitor/config`、`/monitor/log`                  | 设置与日志             |
| 递送  | `/delivery/insights`、`/delivery/digest`           | 洞察与简报             |

完整请求字段、错误码、事件与确认机制以[仓库 API 契约](https://github.com/PlutoKeating/Project.PIXIU/blob/main/docs/API.md)为准。

## 配置要点

| 配置                         | 说明                                                       |
| ---------------------------- | ---------------------------------------------------------- |
| `PIXIU_EMBEDDING`            | `auto` 优先探测麒麟；`kylin` 严格原生；`portable` 软件路径 |
| `PIXIU_SYNC_NETWORK_ENABLED` | 控制同步网络运行时，传输仍需身份与配置就绪                 |
| `XDG_CONFIG_HOME`            | 用户配置根目录                                             |
| `XDG_DATA_HOME`              | 用户数据根目录                                             |
| `XDG_STATE_HOME`             | 用户状态根目录                                             |

`scope` 格式校验不是身份认证。不要为方便网站演示把本机记忆 API 暴露到公网，也不要把模型凭据放入浏览器代码。
