# 后端快速启动指南

后端分为两个子模块，各自可独立开发和测试。

---

## 模块 B（记忆业务引擎）

```bash
cd backend
pip install -r requirements.txt

# 运行引擎单元测试（使用 mock embedding）
PIXIU_EMBEDDING=mock pytest engine/tests/ -v
```

## 模块 C（后台基础设施）

```bash
cd backend

# 启动 API 网关（开发模式，热重载）
PIXIU_EMBEDDING=mock uvicorn foundation.api.http_app:app \
  --host 127.0.0.1 --port 8765 --reload

# 运行基础设施测试
pytest foundation/tests/ -v
```

## 联合启动

```bash
# 终端 1：基础设施
PIXIU_EMBEDDING=mock python -m foundation.api.http_app

# 终端 2：手动测试
curl http://127.0.0.1:8765/memory/query -X POST \
  -H "Content-Type: application/json" \
  -d '{"text":"水电燃气花费","context_hint":{}}'
```

详细开发说明见 `backend/engine/docs/QUICK_START.md` 和 `backend/foundation/docs/QUICK_START.md`。
