# PIXIU API 规格文档

> 本文档定义前端（Module A）与后端（Module C API 网关）之间的全部通信契约。
> 所有端点、请求结构、响应结构、事件类型的变更须经 Module A + Module C 双方确认。

> [!IMPORTANT]
> 这是 **PIXIU 记忆服务 API**，不是完整 OS Agent API。它没有定义会话、消息、
> Agent run、模型规划、工具调用、Shell、联网搜索或审批契约；`/memory/query`
> 返回记忆检索结果，不是聊天补全。目标方案由 `third_party/kylin-agent-runtime`
> 提供 Agent 能力，通过 MemoryProvider/适配器调用本 API。接口映射和缺口见
> `OS_AGENT_INTEGRATION_ASSESSMENT.md`。

> [!IMPORTANT]
> 团队已批准 [ADR-0001](decisions/0001-use-openkylin-agent-host.md)：Module E
> 将通过本 API 接入 openKylin Agent。下节逐项区分已实现基础契约与仍待实现能力；
> 当前可用端点仍以 §2 的状态列为准，禁止据局部完成宣称 Agent 闭环已完成。

## 0. vNext Agent 接入契约（已批准，分阶段实现）

| MemoryProvider 行为 | 当前映射 | 必须补齐的契约 |
|---------------------|----------|----------------|
| `initialize` | `GET /capabilities`（已实现） | 消费 V11、Embedding、Vector Engine 的真实 capability/runtime；Module E 尚需实现严格画像拒绝 |
| `prefetch(query, session_id)` | `POST /agent/context`（已实现） | Module E 调用、后台预取/缓存与失败降级仍待实现 |
| `sync_turn(user, assistant, session_id)` | `POST /memory/write` + `CONVERSATION`（provenance + 持久化幂等已实现） | 异步重试、失败 receipt 恢复与 Module E 调用仍待实现 |
| 工具结果沉淀 | `POST /memory/write` + `TOOL_RESULT`（provenance + 持久化幂等已实现） | 输入摘要策略、失败 receipt 恢复与 Module E 调用仍待实现 |
| 显式记忆工具 | query/write/forget/sync 现有端点 | Module E 做 schema 和错误映射，不新增 Agent 私有直连 |
| `on_pre_compress`/会话结束或切换 | `/memory/flow/promote` 仅处理已有 context | 增加可创建/更新短中期 context 的公共端点，再触发 promote/demote/清理 |
| 运行审计 | evidence provenance + `/agent/context` 回显 session/turn | 日志与 memory_id 跨端点链路仍待贯通 |

`CONVERSATION` 与 evidence provenance 已同步更新 `foundation/core` 模型、Module B
Connector、Module C 路由/存储及契约测试；schema v11 的持久化 receipt 保证完成态
请求跨重启重放不重复产生 evidence/knowledge。后续失败恢复、上下文、生命周期和
Module E 客户端仍须贯通；不得用 `TOOL_RESULT` 伪装普通对话来源，也不得把基础写入
契约解释成完整多轮 Agent 已接入。

---

## 1. 通信协议

| 协议 | 用途 | 默认端口 | 说明 |
|------|------|----------|------|
| HTTP REST | 一问一答的操作（写/查/管理） | 8765 | `http://127.0.0.1:8765` |
| WebSocket | 服务端推送事件 | 8765 | `ws://127.0.0.1:8765/events` |
| D-Bus | 桌面生态整合（可选回退至 HTTP） | — | `com.kylin.pixiu.Memory` |

## 2. 端点一览

| 方法 | 路径 | 说明 | 实现状态 |
|------|------|------|----------|
| GET | `/capabilities` | 平台与双 SDK 的配置/实际运行能力 | ✅ 已实现（不含主机、网络、路径信息） |
| POST | `/memory/write` | 写入一条记忆 | ✅ 已实现 |
| POST | `/memory/query` | 混合检索（BM25+ANN+Graph） | ✅ 已实现（2026-08-10） |
| POST | `/agent/context` | Agent 轮次的预算化、可追溯安全上下文 | ✅ 已实现（scope/敏感过滤/freshness/冲突状态） |
| GET | `/evidence/{id}` | 证据详情（查看原文） | ✅ 已实现（2026-08-24） |
| POST | `/memory/ocr` | 图片文字识别（麒麟 kysdk-ocr） | ✅ 已实现（2026-08-24，无 SDK 环境返回 503 OCR_UNAVAILABLE） |
| POST | `/preference/extract` | 触发偏好提取 | ✅ 已实现 |
| GET | `/preferences` | 偏好列表（支持 scope 过滤） | ✅ 已实现（2026-08-24） |
| GET | `/preference/{id}/history` | 偏好版本回溯 | ✅ 已实现 |
| POST | `/forget` | 自然语言遗忘 | ✅ 已实现 |
| GET | `/conflicts` | 冲突审计列表 | ✅ 已实现 |
| POST | `/memory/flow/promote` | 短/中期→长期流转 | ✅ 已实现（2026-08-10） |
| POST | `/sync/token` | 生成配对令牌（QR/PIN） | ✅ 已实现（2026-08-24） |
| POST | `/sync/pair` | 设备配对（QR/PIN + 签名令牌） | ✅ 已实现（2026-08-10） |
| GET | `/sync/peers` | 节点列表 | ✅ 已实现（2026-08-10） |
| GET | `/sync/discover` | 发现局域网设备（含未配对） | ✅ 已实现（2026-08-29） |
| POST | `/sync/pair/request` | 发起确认式配对请求（含 6 位 PIN） | ✅ 已实现（2026-08-29） |
| POST | `/sync/pair/confirm` | 确认/拒绝配对请求 | ✅ 已实现（2026-08-29） |
| GET | `/sync/status` | 同步状态（含运行时开关 enabled/paused） | ✅ 已实现（2026-08-10） |
| PUT | `/sync/settings` | 更新同步开关（enabled/paused，热生效） | ✅ 已实现（2026-08-29） |
| POST | `/sync/peers/{id}/revoke` | 解绑设备 | ✅ 已实现（2026-08-10） |
| GET | `/monitor/config` | 读取监控配置 | ✅ 已实现（2026-08-26） |
| PUT | `/monitor/config` | 写入监控配置（全量提交，热生效） | ✅ 已实现（2026-08-26） |
| GET | `/monitor/log` | 监控活动日志（分页，最新在前） | ✅ 已实现（2026-08-26） |
| GET | `/delivery/insights` | 洞察流（欢迎页动态建议，最近高质量记忆） | ✅ 已实现（2026-08-29） |
| GET | `/delivery/digest` | 定时简报（按日聚合当日记忆沉淀） | ✅ 已实现（2026-08-29） |
| WS | `/events` | 事件推送 | ✅ 契约已实现（连接/心跳/广播，含全部六类事件） |

> 状态说明（2026-09-03）：26 个 REST 端点已按本文档契约真实实现；
> 六类 WebSocket 事件（memory_ready / conflict_detected / forget_confirmation /
> sync_event / capture_event / pair_request）均已广播。
> 监控三端点 + capture_event 事件自 frontend/docs/MONITOR_API_REQUIREMENTS.md
> 转正（Module A + Module C 双方于 2026-08-26 确认）。
> pair_request/pair/confirm 通道按计划（2026-08-29）实现；confirm 后仍由前端
> 走既有 `/sync/pair` 完成签名入网。

---

## 3. 端点详情

### 3.0 GET /capabilities

返回验收相关的脱敏能力事实。`configured` 表示配置意图，`runtime` 来自已实例化
适配器；`auto` 降级时二者会不同，不得据配置值宣称 SDK 已启用。响应不包含主机名、
IP、文件路径或测试环境拓扑。

```json
{
  "platform": {"family": "kylin", "version_major": "11", "v11": true},
  "embedding": {"configured": "kylin", "runtime": "kylin", "compliant": true},
  "vector_store": {"configured": "kylin", "runtime": "kylin", "compliant": true},
  "contest_ready": true
}
```

`contest_ready` 仅在平台为麒麟 V11 且 Embedding、Vector Engine 的实际 runtime 均为
`kylin` 时为 `true`。任一后端配置为严格 `kylin` 且无法实例化时，应用在启动预检
阶段直接失败，不等待首个业务请求，也不静默降级。

### 3.1 POST /memory/write

写入一条记忆。同步落 evidence 后立即 ACK，结构化处理异步执行。

**请求体：**

```jsonc
{
  "source_type": "OCR|TOOL_RESULT|USER_BEHAVIOR|MANUAL_CONFIG|CONVERSATION",
  "raw": {
    "title": "2026年4月家庭支出清单",
    "body": {
      "items": [
        {"category": "水电燃气", "vendor": "国家电网", "amount": 210.00, "date": "2026-04-10", "tags": ["电费"]}
      ]
    },
    "entities": ["国家电网", "市自来水公司"],
    "relations": [
      {"from": "国家电网", "to": "水电燃气", "type": "BELONG_TO"}
    ]
  },
  "scope": "user:alice|shared:home",
  "context": {
    "source_device": "书房工作站",
    "trigger_event": "OCR_RESULT"
  },
  "provenance": null
}
```

Agent 对话轮次使用独立来源，关联信息不得混入 `raw`：

```jsonc
{
  "source_type": "CONVERSATION",
  "raw": {"user": "请保持回答简洁", "assistant": "好的，我会记住。"},
  "scope": "user:alice",
  "idempotency_key": "session-01:turn-03",
  "provenance": {
    "session_id": "session-01",
    "run_id": "run-01",
    "turn_id": "turn-03",
    "occurred_at": 1788393600
  }
}
```

校验规则：

- `CONVERSATION` 必须同时提供非空 `raw.user`、`raw.assistant` 以及
  `session_id`、`run_id`、`turn_id`、`occurred_at`、`idempotency_key`。
- Agent 产生的 `TOOL_RESULT` 一旦携带 `provenance`，还必须提供 `tool_call_id`、
  `tool_name`、布尔值 `approved` 与 `idempotency_key`；旧版非 Agent 工具采集允许
  不携带 provenance 和幂等键。
- `idempotency_key` 为 1～128 位安全标识符，字符集为字母、数字、`.`、`_`、`:`、
  `-`。同键同载荷的完成态请求返回首次保存的完整响应且不重复执行副作用；同键异
  载荷返回 `409 IDEMPOTENCY_CONFLICT`。
- 首次执行仍在进行中或已失败时，重试分别返回 `IDEMPOTENCY_IN_PROGRESS` 或
  `IDEMPOTENCY_FAILED`，不自动重放可能已发生的外部向量/同步副作用。失败恢复管理
  端点尚待实现。
- provenance 单独持久化并由 `GET /evidence/{id}` 原样返回；当前尚未提供基于这些
  标识的查询索引或生命周期端点。

**响应体（200）：**

```jsonc
{
  "evidence_id": "evd_01H...",
  "status": "accepted",
  "quality_score": 0.94,
  "sensitivity": 0,
  "latency_ms": 42
}
```

### 3.2 POST /memory/query

混合检索。

**请求体：**

```jsonc
{
  "text": "我们好像在水电燃气方面花了一些钱，花了多少钱来着？",
  "context_hint": {
    "time_range": "last_month",
    "scope": "shared:home",
    "top_k": 5
  }
}
```

**响应体（200）：**

```jsonc
{
  "answer": "2026年4月，你们在水电燃气方面共支出 434.50 元，其中电费 210 元、水费 68.50 元、燃气费 156 元。",
  "source_evidence": ["evd_01H..."],
  "source_knowledge": "knw_02K...",
  "confidence": 0.93,
  "latency_ms": 210
}
```

### 3.2a POST /agent/context

为 OS Agent 即将开始的一个 turn 构建可直接交给 MemoryProvider 的结构化上下文。
该端点复用 BM25/向量/图检索，但返回多候选和审计元数据；`scope` 是硬过滤，任何
关联 evidence 的 `sensitivity > 0` 都会使该候选从上下文中排除，客户端不能提高
这一服务端阈值。

**请求体：**

```jsonc
{
  "query": "请按我的习惯整理结果",
  "scope": "user:alice",
  "session_id": "session-01",
  "turn_id": "turn-04",
  "top_k": 5,
  "max_chars": 4000,
  "freshness_seconds": 2592000
}
```

`session_id`、`turn_id` 必填；`top_k` 范围 1～20，`max_chars` 范围 64～16000。
`freshness_seconds` 只决定 `fresh|stale` 标签，不放宽 scope、状态或敏感过滤。

**响应体（200）：**

```jsonc
{
  "session_id": "session-01",
  "turn_id": "turn-04",
  "context": "- 用户偏好简洁回答: {...} [knowledge=knw_...; evidence=evd_...]",
  "items": [
    {
      "knowledge_id": "knw_...",
      "title": "用户偏好简洁回答",
      "scope": "user:alice",
      "evidence_ids": ["evd_..."],
      "confidence": 0.91,
      "updated_at": 1788393600,
      "freshness": "fresh",
      "conflict_status": "none|resolved|manual"
    }
  ],
  "truncated": false,
  "latency_ms": 42
}
```

`context` 保证不超过 `max_chars`；`truncated=true` 表示最后一项或后续候选因预算
被截断。每个返回项必须至少解析到一条真实 evidence，缺失来源的候选 fail-closed。
返回内容仍属于不可信外部记忆，Module E 必须继续使用上游 MemoryProvider 的上下文
隔离/转义机制，不能把其中的文本当系统指令执行。

### 3.3 GET /evidence/{id}

按 evidence_id 获取原始证据详情，供前端 EvidenceCard「查看原文」。

**响应体（200）：**

```jsonc
{
  "id": "evd_01H...",
  "source_type": "OCR",
  "raw": { "...": "写入时的原始结构化内容" },
  "quality_score": 0.94,
  "sensitivity": 0,
  "scope": "shared:home",
  "created_at": 1714435200
}
```

### 3.4 POST /memory/ocr

图片文字识别。请求体二选一：`image_base64`（前端上传，≤20MB base64）
或 `image_path`（本机绝对路径）。无麒麟 kysdk-ocr 环境返回
`503 {"error": "OCR_UNAVAILABLE"}`。

**响应体（200）：**

```jsonc
{
  "text_lines": ["2026年4月家庭支出清单", "电费 210 元"],
  "text": "2026年4月家庭支出清单\n电费 210 元",
  "engine": "KylinOcr",
  "latency_ms": 850
}
```

### 3.5 POST /preference/extract

触发偏好提取。

**请求体：**

```jsonc
{
  "evidence_ids": ["evd_01H..."]
}
```

**响应体：**

```jsonc
{
  "extracted_preferences": [
    {
      "id": "pref_...",
      "category": "OP_HABIT|OUTPUT_STYLE|SECURITY_POLICY",
      "key": "output_style.compact",
      "value": {"enabled": true},
      "confidence": 0.85
    }
  ],
  "latency_ms": 1500
}
```

### 3.6 GET /preferences

偏好列表，支持 `scope` 查询参数过滤，供前端 MemoryPanel 偏好选择器使用。

**查询参数：** `scope`（可选，e.g. `shared:home`）

**响应体（200）：**

```jsonc
{
  "preferences": [
    {
      "id": "pref_...",
      "category": "OP_HABIT|OUTPUT_STYLE|SECURITY_POLICY",
      "key": "output_style.compact",
      "value": {"enabled": true},
      "confidence": 0.85,
      "version": 3,
      "scope": "shared:home",
      "created_at": 1714435200,
      "updated_at": 1714608000
    }
  ]
}
```

### 3.7 GET /preference/{id}/history

偏好版本回溯。

**响应体：**

```jsonc
{
  "id": "pref_...",
  "key": "output_style.compact",
  "current_version": 3,
  "history": [
    {"version": 1, "value": {"enabled": false}, "updated_at": 1714435200},
    {"version": 2, "value": {"enabled": true}, "updated_at": 1714521600},
    {"version": 3, "value": {"enabled": true, "detail_level": "high"}, "updated_at": 1714608000}
  ]
}
```

### 3.8 POST /forget

自然语言遗忘指令。

**请求体：**

```jsonc
{
  "command": "忘记那张4月支出清单",
  "confirm": false
}
```

**响应体（confirm=false，待确认）：**

```jsonc
{
  "targets": [
    {"type": "knowledge", "id": "knw_02K...", "title": "2026年4月家庭支出清单"}
  ],
  "cascade": {
    "evidence_count": 1,
    "relation_count": 3
  },
  "irreversible": true
}
```

**响应体（confirm=true，已执行）：**

```jsonc
{
  "status": "forgotten",
  "forgotten_ids": ["knw_02K...", "evd_01H..."],
  "latency_ms": 85
}
```

### 3.9 GET /conflicts

冲突审计列表。

**响应体：**

```jsonc
{
  "conflicts": [
    {
      "id": "cfl_...",
      "target_knowledge": "knw_02K...",
      "field": "body.items[2].amount",
      "old_value": 156,
      "new_value": 186,
      "resolution": "NEW_WINS",
      "created_at": 1714608000,
      "knowledge_title": "2026年4月家庭支出清单",
      "severity": "medium"
    }
  ]
}
```

> `severity`（B3-3 起）：`low | medium | high`，按 `resolution` 派生的打扰级别
> （MERGE→low 自动合并静默 / NEW_WINS→medium 自动裁决但用户应知晓 /
> MANUAL→high 需人工确认）。读取路径始终按 resolution 派生，保证改判后
> 自洽；SQL 层列值随 save / resolve 同步维护，供过滤与直查。

### 3.10 POST /memory/flow/promote

短/中期记忆沉淀到长期记忆。

**请求体：**

```jsonc
{
  "source": "SHORT_TERM|MID_TERM",
  "context_ids": ["ctx_..."],
  "scope": "user:alice"
}
```

**响应体：**

```jsonc
{
  "promoted_count": 2,
  "knowledge_ids": ["knw_03K..."],
  "latency_ms": 3200
}
```

### 3.11 POST /sync/token

生成设备配对令牌（QR/PIN），供前端 PairDialog 展示二维码或 PIN 码。
注意：`method=PIN` 时必须提供 6 位数字 `pin`；`method=QR` 时无需 pin。

**请求体：**

```jsonc
{
  "method": "QR|PIN",
  "pin": "123456",
  "ttl_seconds": 300
}
```

**响应体（200）：**

```jsonc
{
  "token": "base64_encoded_pairing_token",
  "method": "QR",
  "ttl_seconds": 300
}
```

### 3.12 POST /sync/pair

设备配对，加入共享域。

**请求体：**

```jsonc
{
  "method": "QR|PIN",
  "token": "base64_encoded_pairing_token",
  "pin": "123456"
}
```

**响应体：**

```jsonc
{
  "peer_id": "dev_...",
  "device_name": "麒麟笔记本",
  "domain": "shared:home",
  "status": "paired"
}
```

### 3.13 GET /sync/peers

节点列表。

**响应体：**

```jsonc
{
  "peers": [
    {
      "id": "dev_abc",
      "name": "书房工作站",
      "is_self": true,
      "status": "ONLINE",
      "last_sync_ts": 1714608000,
      "pending_ops": 0
    },
    {
      "id": "dev_def",
      "name": "客厅一体机",
      "is_self": false,
      "status": "ONLINE",
      "last_sync_ts": 1714607900,
      "pending_ops": 3
    }
  ]
}
```

### 3.14 GET /sync/status

同步状态（SN-4 起含运行时开关）。

**响应体：**

```jsonc
{
  "domain": "shared:home",
  "peers_online": 2,
  "peers_total": 3,
  "pending_outgoing_ops": 0,
  "last_anti_entropy_ts": 1714608000,
  "total_ops_synced": 1285,
  "enabled": true,
  "paused": false
}
```

字段说明：`enabled` 为同步总开关（KV `sync_runtime:enabled` 覆盖 env 默认
`PIXIU_SYNC_NETWORK_ENABLED`，未写时回 env 默认——代码默认 true）；
`paused` 为数据流暂停（KV `sync_runtime:paused`，默认 false）。

### 3.15 POST /sync/peers/{id}/revoke

解绑设备。

**响应体：**

```jsonc
{
  "status": "revoked",
  "peer_id": "dev_def",
  "domain": "shared:home"
}
```

### 3.16 GET /sync/discover

发现局域网内已广播的 PIXIU 设备（**含未配对**）。`paired` 标注本地信任关系，
本机自身被过滤。

**响应体（200）：**

```jsonc
{
  "devices": [
    {
      "device_id": "dev_...",
      "device_name": "Alpha",
      "addresses": ["192.168.1.10"],
      "port": 8766,
      "pairable": true,
      "paired": true
    }
  ]
}
```

字段说明：`pairable` 来自设备 mDNS 通告（未配对设备广播的可配对标志；
旧版通告缺省 false）；`paired` 表示该设备是否已在本地信任列表
（`sync.peers()`）；sync runtime 未启动时返回 `{"devices": []}`。

### 3.17 GET /monitor/config

读取当前监控配置（daemon 视角的全量状态）。

**响应体（200）：**

```jsonc
{
  "enabled": false,
  "sources": {
    "directory": false,
    "clipboard": false,
    "behavior": false,
    "screenshot": false
  },
  "directories": ["/home/u/Downloads"]
}
```

字段说明：`enabled` 全局总闸（关闭时各数据源开关状态保留）；`sources`
四类数据源开关，键名固定 `directory | clipboard | behavior | screenshot`；
`directories` 监视目录绝对路径清单（去重、非空）。

### 3.18 PUT /monitor/config

写入监控配置，请求体结构与 GET 响应一致（**全量提交，不做局部 patch**）。
服务端持久化配置并对运行中的 daemon **热生效**（开启/关闭采集器、增删
inotify 监视点），无需重启。每次成功写入追加一条 `state_changed` 活动日志
并广播 `capture_event`。

**请求体 / 响应体（200，返回归一化后的完整配置）：**

```jsonc
{
  "enabled": true,
  "sources": {
    "directory": true,
    "clipboard": false,
    "behavior": false,
    "screenshot": false
  },
  "directories": ["/home/u/Downloads"]
}
```

**错误响应（400）：** 未知 source 名、字段类型错误、目录为相对路径等 →
`{"error": "INVALID_REQUEST", "message": "...", "request_id": "req_..."}`。

### 3.19 GET /monitor/log

分页查询监控活动记录（按时间倒序，最新在前）。`limit` 缺省 100、上限 500；
`offset` 缺省 0。空日志返回 `{"events": []}` 而非 404。

**查询参数：** `limit`（1–500，默认 100）、`offset`（≥0，默认 0）

**响应体（200）：**

```jsonc
{
  "events": [
    {
      "ts": 1756080000,
      "source": "directory|clipboard|behavior|screenshot|system",
      "status": "ingested|sensitive_quarantined|ignored|state_changed",
      "summary": "记住文件 支出清单.xlsx",
      "evidence_id": "evd_...",
      "knowledge_id": "knw_..."
    }
  ]
}
```

字段说明：`ts` Unix 秒时间戳；`source` 含 `system`（监控自身状态变更，
如总闸开闭）；`status` 四态（ingested / sensitive_quarantined / ignored /
state_changed）；`evidence_id`/`knowledge_id` 事件未产生入库时允许缺失或为
null。`summary` 由服务端生成用户可读文案，**不含敏感原文全文**（隔离类条目
只给脱敏摘要）。

### 3.20 POST /sync/pair/request

发起确认式配对请求（「一键发现+确认配对」GUI 主路径）：本机生成 6 位 PIN
并落库（`pair_request:{request_id}`，TTL 60s），随后向所有 WebSocket 客户端
广播 `pair_request`（`type: "INCOMING"`）供目标机弹窗确认。确认后仍复用既有
`POST /sync/pair` 完成签名入网（QR/PIN 令牌流程保留为备选）。

**请求体：**

```jsonc
{
  "target_device_id": "dev_..."
}
```

**响应体（200）：**

```jsonc
{
  "request_id": "req_...",
  "pin": "483920",
  "target_device_id": "dev_...",
  "expires_at": 1756080060
}
```

**错误响应（400）：** 目标 ID 格式非法或自配对 →
`{"error": "INVALID_REQUEST", "message": "...", "request_id": "req_..."}`。

### 3.21 POST /sync/pair/confirm

确认或拒绝一条配对请求（按 `request_id` 直查本机存储）。`accept=true` 返回
`accepted`，实际签名入网由前端在确认成功后自动执行既有 `POST /sync/pair`
（Task SN-6 接线），后端 confirm 仅返回状态。

**请求体：**

```jsonc
{
  "request_id": "req_...",
  "accept": true
}
```

**响应体（200）：** `{"status": "accepted" | "rejected" | "expired"}`

**错误响应（404）：** `request_id` 不存在 →
`{"error": "REQUEST_NOT_FOUND", "message": "...", "request_id": "req_..."}`。

### 3.22 PUT /sync/settings

更新同步运行时开关（SN-4）。两字段均可缺省，只更新显式传入的键；
KV 持久化（`sync_runtime:enabled` / `sync_runtime:paused`）+ 热生效：
`enabled=false` 停止 runtime（mDNS 注册与监听停）；`enabled=true` 启动
（若未启动）；`paused=true` 暂停 gossip 数据流（保留发现与配对）。

**请求体：**

```jsonc
{
  "enabled": false,
  "paused": true
}
```

**响应体（200）：** 合并后的当前运行时设置（enabled 缺省回 env 默认）

```jsonc
{
  "enabled": false,
  "paused": true
}
```

---

### 3.23 GET /delivery/insights

洞察流（批次④ B4-1）：返回最近 24h 入库的高质量记忆候选（按关联证据
`quality_score` 降序、过滤 `sensitivity>0`），供聊天窗欢迎页渲染动态建议卡。

**查询参数：**

| 参数 | 类型 | 缺省 | 说明 |
|------|------|------|------|
| `limit` | int | 3 | 返回条数；上限 10，`>10` 或 `<1` → 400 `INVALID_REQUEST` |

**生成规则（服务端，无 LLM）：**
- 候选 = 最近 24h 入库（`created_at >= now-24h`）的 ACTIVE knowledge，scope 为本机
  `user:local`；
- 质量分/敏感度取自关联 Evidence（`knowledge_evidence` 链接）；
- `sensitivity > 0` 的候选不出现；summary 为服务端生成文案（标题 + 正文前 60 字），
  不含敏感原文；
- 任一 `MANUAL` 冲突待处理 → 整体抑制（返回空列表，避免干扰人工裁决）；
- 空库/无候选 → `{"insights": []}`。

**响应体（200）：**

```jsonc
{
  "insights": [
    {
      "title": "2026年4月家庭支出清单",
      "summary": "2026年4月家庭支出清单：本月水电燃气共支出 434.50 元，其中电费 210 元、水费…",
      "knowledge_id": "knw_02K...",
      "score": 0.94,
      "kind": "recent"
    }
  ]
}
```

**错误（400）：** `limit > 10` 或 `limit < 1` → `INVALID_REQUEST`（错误体见 §5）。

---

### 3.24 GET /delivery/digest

定时简报（批次④ B4-2）：按日聚合当日 `monitor_log` 捕获事件，服务端规则化
生成中文简报（无 LLM、离线可运行），供前端「今日简报」入口消费。

**查询参数：**

| 参数 | 类型 | 缺省 | 说明 |
|------|------|------|------|
| `date` | str | 今天（本地时区） | `YYYY-MM-DD`；非法格式/无效日历日 → 400 `INVALID_REQUEST` |

**生成规则（服务端，无 LLM）：**
- 按本地时区日边界取当日 `monitor_log` 事件（跨日不串）；
- 仅 `status == "ingested"` 计为「新增记忆」，按 `source` 分组计数
  （`directory|clipboard|behavior|screenshot|system`，无独立「文本」枚举——
  文本文件经目录捕获走 `directory`，见批次②）；
- `sensitive_quarantined` 不计入新增，> 0 时单列「另有 N 条敏感内容已隔离」；
  `ignored` / `state_changed` 不计入；
- summary 为模板计数文案，不含任何事件原始 summary 文本（敏感隔离原则）；
- 空日 → summary 为「当日无新记忆」。

**响应体（200）：**

```jsonc
{
  "date": "2026-08-29",
  "summary": "当日新增 12 条记忆（目录 8、剪贴板 3、行为 1），另有 1 条敏感内容已隔离"
}
```

**错误（400）：** `date` 非严格 `YYYY-MM-DD`（如 `2026-13-01` / `2026-02-30` /
`2026-1-1` / 非日期）→ `INVALID_REQUEST`（错误体见 §5）。

---

## 4. WebSocket 事件

连接 `ws://127.0.0.1:8765/events`。JSON 行协议。

### 4.1 memory_ready ✅ 已实现（写入链路已广播）

```jsonc
{
  "event": "memory_ready",
  "data": {
    "evidence_id": "evd_01H...",
    "knowledge_id": "knw_02K...",
    "title": "2026年4月家庭支出清单",
    "scope": "shared:home"
  }
}
```

### 4.2 conflict_detected ✅ 已实现（写入链路冲突仲裁命中时广播）

```jsonc
{
  "event": "conflict_detected",
  "data": {
    "conflict_id": "cfl_...",
    "knowledge_title": "2026年4月家庭支出清单",
    "field": "body.items[2].amount",
    "old_value": 156,
    "new_value": 186,
    "severity": "medium"
  }
}
```

> `severity`（B3-3 起）：`low | medium | high`，按裁决方式派生
> （MERGE→low / NEW_WINS→medium / MANUAL→high，见 §3.9）。前端按此分流
> 打扰级别：low 静默仅计数 / medium 温和通知+角标 / high 全动作。
> 旧后端广播无此字段时，前端缺省按 `high` 处理（宁可打扰不漏报）。

### 4.3 forget_confirmation ✅ 已实现（遗忘执行后广播，含 targets/forgotten_ids/expires_at）

```jsonc
{
  "event": "forget_confirmation",
  "data": {
    "command": "忘记那张4月支出清单",
    "targets": [
      {"type": "knowledge", "id": "knw_02K..."},
      {"type": "evidence", "id": "evd_01H..."},
      {"type": "relation", "count": 3}
    ],
    "expires_at": 1714608100
  }
}
```

### 4.4 sync_event ✅ 已实现（配对/解绑时已广播）

```jsonc
{
  "event": "sync_event",
  "data": {
    "type": "PEER_ONLINE|PEER_OFFLINE|SYNC_COMPLETE|ANTI_ENTROPY_DONE",
    "peer_id": "dev_def",
    "peer_name": "客厅一体机",
    "timestamp": 1714608000
  }
}
```

### 4.5 capture_event ✅ 已实现（2026-08-26，监视捕获/状态变更时已广播）

每次目录捕获（ingested / sensitive_quarantined / ignored）与监控配置变更
（state_changed）推送；`data` 与 §3.19 日志条目同构，`knowledge_id` 可缺
（事件未产生入库时为 null）。

```jsonc
{
  "event": "capture_event",
  "data": {
    "source": "directory",
    "status": "ingested",
    "summary": "记住文件 支出清单.xlsx",
    "ts": 1756080000,
    "evidence_id": "evd_...",
    "knowledge_id": "knw_..."
  }
}
```

> 前端行为：普通事件 → 角标 +1（可选）+ 监控中心「活动记录」实时追加；
> `sensitive_quarantined` 额外弹系统通知（隔离区查看/恢复交互属批次③范围）。

### 4.6 pair_request ✅ 已实现（2026-08-29，发起配对请求时已广播）

本机发起 `POST /sync/pair/request` 后全局广播（前端按目标设备过滤展示，
确认对话框接线见 Task SN-6）。MVP 语义：`from_device_id` 为请求目标设备
（request_id 由本机生成，confirm 也按 request_id 查本机存储）；`from_name`
留空，由前端在确认成功后展示目标设备名。

```jsonc
{
  "event": "pair_request",
  "data": {
    "type": "INCOMING",
    "request_id": "req_...",
    "from_device_id": "dev_...",
    "from_name": "",
    "pin": "483920",
    "expires_at": 1756080060
  }
}
```

---

## 5. 错误码

| 错误码 | HTTP 状态码 | 说明 |
|--------|-------------|------|
| `INVALID_REQUEST` | 400 | 请求体不符合 Schema |
| `IDEMPOTENCY_CONFLICT` | 409 | 幂等键已绑定到不同请求载荷 |
| `IDEMPOTENCY_IN_PROGRESS` | 409 | 同键首次请求尚未完成，安全拒绝重复执行 |
| `IDEMPOTENCY_FAILED` | 409 | 同键首次请求失败，需恢复处理后再决定是否重放 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `CONFLICT_TIMEOUT` | 408 | 遗忘确认超时 |
| `PAIRING_FAILED` | 422 | 设备配对失败 |
| `PEER_NOT_FOUND` | 404 | 解绑的设备 ID 不存在 |
| `REQUEST_NOT_FOUND` | 404 | 配对请求 ID 不存在 |
| `INTERNAL_ERROR` | 500 | 后端内部错误 |

错误响应体格式：

```jsonc
{
  "error": "INVALID_REQUEST",
  "message": "field 'source_type' must be one of: OCR, TOOL_RESULT, USER_BEHAVIOR, MANUAL_CONFIG, CONVERSATION",
  "request_id": "req_..."
}
```

> **错误响应实现（2026-08-11）**：后端经 request_id 中间件将错误响应统一对齐
> 上述 §5 契约（`{error, message, request_id}`）：
> - HTTPException → 原状态码 + `{error:<错误码>, message:<错误码>, request_id}`；
> - 参数校验失败 → 400 + `INVALID_REQUEST`；
> - 未捕获异常 → 500 + `INTERNAL_ERROR`；
> - 所有响应携带 `X-Request-Id` 响应头。
> 前端 `parseBackendError` 同时兼容 `error` 与早期 `detail` 两种形状，错误码不丢失。
