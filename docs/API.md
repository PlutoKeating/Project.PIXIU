# PIXIU API 规格文档

> 本文档定义前端（Module A）与后端（Module C API 网关）之间的全部通信契约。
> 所有端点、请求结构、响应结构、事件类型的变更须经 Module A + Module C 双方确认。

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
| POST | `/memory/write` | 写入一条记忆 | ✅ 已实现 |
| POST | `/memory/query` | 混合检索 | ⬜ 占位（待 retrieval 阶段） |
| POST | `/preference/extract` | 触发偏好提取 | ✅ 已实现 |
| GET | `/preference/{id}/history` | 偏好版本回溯 | ✅ 已实现 |
| POST | `/forget` | 自然语言遗忘 | ✅ 已实现 |
| GET | `/conflicts` | 冲突审计列表 | ✅ 已实现 |
| POST | `/memory/flow/promote` | 短/中期→长期流转 | ⬜ 占位（待 flow 阶段） |
| POST | `/sync/pair` | 设备配对 | ⬜ 占位（待 sync 阶段） |
| GET | `/sync/peers` | 节点列表 | ⬜ 占位（待 sync 阶段） |
| GET | `/sync/status` | 同步状态 | ⬜ 占位（待 sync 阶段） |
| POST | `/sync/peers/{id}/revoke` | 解绑设备 | ⬜ 占位（待 sync 阶段） |
| WS | `/events` | 事件推送 | ✅ 已实现（连接/心跳/广播；`memory_ready` 已接入写入链路） |

> 状态说明（2026-08-07）：带 ⬜ 的端点为契约占位，当前返回
> `{"status": "not_implemented"}`，待对应模块实现后按本文档契约落地。

---

## 3. 端点详情

### 3.1 POST /memory/write

写入一条记忆。同步落 evidence 后立即 ACK，结构化处理异步执行。

**请求体：**

```jsonc
{
  "source_type": "OCR|TOOL_RESULT|USER_BEHAVIOR|MANUAL_CONFIG",
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
  }
}
```

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

### 3.3 POST /preference/extract

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

### 3.4 GET /preference/{id}/history

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

### 3.5 POST /forget

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

### 3.6 GET /conflicts

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
      "knowledge_title": "2026年4月家庭支出清单"
    }
  ]
}
```

### 3.7 POST /memory/flow/promote

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

### 3.8 POST /sync/pair

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

### 3.9 GET /sync/peers

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

### 3.10 GET /sync/status

同步状态。

**响应体：**

```jsonc
{
  "domain": "shared:home",
  "peers_online": 2,
  "peers_total": 3,
  "pending_outgoing_ops": 0,
  "last_anti_entropy_ts": 1714608000,
  "total_ops_synced": 1285
}
```

### 3.11 POST /sync/peers/{id}/revoke

解绑设备。

**响应体：**

```jsonc
{
  "status": "revoked",
  "peer_id": "dev_def",
  "domain": "shared:home"
}
```

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

### 4.2 conflict_detected ⬜ 占位（检测到冲突时暂未广播，待接入）

```jsonc
{
  "event": "conflict_detected",
  "data": {
    "conflict_id": "cfl_...",
    "knowledge_title": "2026年4月家庭支出清单",
    "field": "body.items[2].amount",
    "old_value": 156,
    "new_value": 186
  }
}
```

### 4.3 forget_confirmation ⬜ 占位（待接入）

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

### 4.4 sync_event ⬜ 占位（待 sync 阶段）

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

---

## 5. 错误码

| 错误码 | HTTP 状态码 | 说明 |
|--------|-------------|------|
| `INVALID_REQUEST` | 400 | 请求体不符合 Schema |
| `NOT_FOUND` | 404 | 资源不存在 |
| `CONFLICT_TIMEOUT` | 408 | 遗忘确认超时 |
| `PAIRING_FAILED` | 422 | 设备配对失败 |
| `PEER_NOT_FOUND` | 404 | 解绑的设备 ID 不存在 |
| `INTERNAL_ERROR` | 500 | 后端内部错误 |

错误响应体格式：

```jsonc
{
  "error": "INVALID_REQUEST",
  "message": "field 'source_type' must be one of: OCR, TOOL_RESULT, USER_BEHAVIOR, MANUAL_CONFIG",
  "request_id": "req_..."
}
```
