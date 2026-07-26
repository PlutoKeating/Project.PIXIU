# 模块 C · 后台基础设施 —— 快速启动

---

## 环境

```bash
cd backend
pip install -r requirements.txt
```

## 初始化数据库

```bash
python -c "from foundation.storage.schema import init_db; init_db('pixiu.db')"
```

## 启动 API 网关

```bash
# 开发模式（hot reload）
PIXIU_EMBEDDING=mock uvicorn foundation.api.http_app:app \
  --host 127.0.0.1 --port 8765 --reload

# 或直接运行
PIXIU_EMBEDDING=mock python -m foundation.api.http_app
```

## 验证启动

```bash
curl http://127.0.0.1:8765/sync/status
# → {"peers_online":0,"peers_total":1,...}
```

## 运行测试

```bash
# 全部 foundation 测试
pytest foundation/tests/ -v

# 检索专项
pytest foundation/tests/test_retrieval.py -v
```
