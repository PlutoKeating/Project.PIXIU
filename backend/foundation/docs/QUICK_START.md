# 模块 C · 后台基础设施 —— 快速启动

---

## 环境

```bash
cd /path/to/Project.PIXIU
pip install -r backend/requirements.txt
```

## 初始化数据库

```bash
# 通过迁移骨架建表（幂等）
python -c "import sqlite3; from backend.foundation.storage.migrations import apply_pending; c=sqlite3.connect('pixiu.db'); apply_pending(c); c.commit(); c.close()"
```

## 启动 API 网关

```bash
# 开发模式（hot reload，仓库根目录运行）
PIXIU_EMBEDDING=mock uvicorn backend.foundation.api.http_app:app \
  --host 127.0.0.1 --port 8765 --reload

# 或直接运行（http_app 内置 uvicorn 入口）
PIXIU_EMBEDDING=mock python -m backend.foundation.api.http_app
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
```

> `/memory/query`、`/memory/flow/promote`、`/sync/*` 当前返回
> `{"status":"not_implemented"}`，待 retrieval/flow/sync 阶段实现。

## 运行测试

```bash
# 全部 foundation 测试（仓库根目录运行）
python -m pytest backend/foundation/tests -v
```
