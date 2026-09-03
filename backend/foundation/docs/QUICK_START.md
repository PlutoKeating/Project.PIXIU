# 模块 C · 后台基础设施 —— 快速启动

> 本指南启动的是当前记忆基础设施。capability、evidence Agent provenance、完成态
> 幂等、context 生命周期和审计式失败 receipt 恢复已实现；Module E 已有独立适配，
> 但真实宿主与长期化尚未完成，不得把 API 启动成功解释成 Agent 接入完成。

---

## 环境

```bash
cd /path/to/Project.PIXIU
conda activate pixiu
pip install -r backend/requirements.txt
pip install -r backend/foundation/requirements-sync.txt
```

## 初始化数据库

```bash
# 通过迁移骨架建表（幂等）
python -c "import sqlite3; from backend.foundation.storage.migrations import apply_pending; c=sqlite3.connect('pixiu.db'); apply_pending(c); c.commit(); c.close()"
```

## 启动 API 网关

```bash
# 开发模式（hot reload，仓库根目录运行；embedding 需已构建麒麟 SDK 绑定）
uvicorn backend.foundation.api.http_app:app \
  --host 127.0.0.1 --port 8765 --reload

# 或直接运行（http_app 内置 uvicorn 入口）
python -m backend.foundation.api.http_app
```

## 验证启动

```bash
# 写入一条记忆（真实链路：ingest → knowledge → preference → conflict）
curl -X POST http://127.0.0.1:8765/memory/write \
  -H "Content-Type: application/json" \
  -d '{"source_type":"MANUAL_CONFIG","raw":{"title":"output_style.compact","body":{"key":"output_style.compact","enabled":true}},"scope":"user:test"}'
# → {"evidence_id":"evd_...","status":"accepted","quality_score":...,"latency_ms":...}

# 冲突审计
curl http://127.0.0.1:8765/conflicts
# → {"conflicts":[...]}

# 查询记忆（真实链路：路由 → 多通道召回 → 融合/重排 → 组装）
curl -X POST http://127.0.0.1:8765/memory/query -H "Content-Type: application/json" -d '{"text":"上个月水电燃气支出是多少？","context_hint":{"scope":"user:test","time_range":"last_month"}}'

# Agent 每轮预取：scope/敏感度硬过滤 + 字符预算 + evidence 引用
curl -X POST http://127.0.0.1:8765/agent/context \
  -H "Content-Type: application/json" \
  -d '{"query":"按我的习惯回答","scope":"user:test","session_id":"session-demo","turn_id":"turn-1","max_chars":2000}'

# 生命周期事件：服务端按事件选择 SHORT_TERM/MID_TERM，完成态重试不重复创建
curl -X POST http://127.0.0.1:8765/agent/lifecycle \
  -H "Content-Type: application/json" \
  -d '{"event":"PRE_COMPRESS","scope":"user:test","session_id":"session-demo","run_id":"run-demo","turn_id":"turn-1","occurred_at":1788393600,"idempotency_key":"session-demo:compress:1","data":{"summary":"受控摘要"}}'

# 将 FlowService.remember 生成的短期上下文沉淀为长期知识
curl -X POST http://127.0.0.1:8765/memory/flow/promote \
  -H "Content-Type: application/json" \
  -d '{"source":"SHORT_TERM","context_ids":["ctx_..."],"scope":"user:test"}'
# → {"promoted_count":1,"knowledge_ids":["knw_..."],"latency_ms":...}
```

> `context_ids` 由后端会话/摘要流程调用 `FlowService.remember(...)` 创建；当前公开 API
> 只承担沉淀动作。`/sync/*` 已按 `docs/API.md` 接入真实本地状态。


## 局域网同步（默认开启）

同步网络**默认开启**（`PIXIU_SYNC_NETWORK_ENABLED` 缺省 true，SN-4 起）：代码默认
即创建监听/mDNS；空 advertise 由 runtime 自动取本机 LAN IP（回退 127.0.0.1 并告警），
缺 TLS 证书由 di 层降级（log warning，不阻塞 API）。如需显式关闭：

```bash
export PIXIU_SYNC_NETWORK_ENABLED=false
```

正式多设备互连前，建议为每台设备准备由同一受信 CA 签发的客户端/服务端证书；
证书 SAN 必须包含 `PIXIU_SYNC_SERVER_NAME`，广告地址只能是私网、链路本地或 loopback 地址。

```bash
export PIXIU_SYNC_DEVICE_NAME='study-workstation'
export PIXIU_SYNC_DOMAIN='shared:home'
export PIXIU_SYNC_KEY_PASSPHRASE='<at-least-16-characters>'
export PIXIU_SYNC_BIND_HOST='<device-lan-ip>'
export PIXIU_SYNC_PORT='8766'
export PIXIU_SYNC_ADVERTISE_ADDRESSES='<device-lan-ip>'
export PIXIU_SYNC_SERVER_NAME='study.pixiu.local'
export PIXIU_SYNC_CERTFILE='/secure/path/device.crt'
export PIXIU_SYNC_KEYFILE='/secure/path/device.key'
export PIXIU_SYNC_CAFILE='/secure/path/peers-ca.crt'
```

可选的加密 TLS 私钥口令使用 `PIXIU_SYNC_TLS_KEY_PASSWORD`。不要把口令、私钥或真实证书提交到仓库。
启动 API 后可用 `GET /sync/status`、`GET /sync/peers` 检查状态；配对令牌由
`SyncService.create_pairing_token(...)` 生成，再交给 `POST /sync/pair`。只有已配对、未撤销且
公钥/域与 mDNS 广告一致的节点会进入传输目录；`user:*` 永不进入同步 oplog。

## 运行测试


```bash
# 全部 foundation 测试（仓库根目录运行）
python -m pytest backend/foundation/tests -v

# Foundation 与 Engine 联合集成基线
python -m pytest backend/foundation/tests backend/engine/tests -q -ra
```
