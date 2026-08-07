# 模块 B · 记忆业务引擎 —— 快速启动

---

## 环境

```bash
pip install -r backend/requirements.txt
```

## 运行测试

```bash
# 全部引擎测试（mock embedding，仓库根目录运行）
PIXIU_EMBEDDING=mock python -m pytest backend/engine/tests -v

# 单模块测试
PIXIU_EMBEDDING=mock python -m pytest backend/engine/tests/test_ingest.py -v
PIXIU_EMBEDDING=mock python -m pytest backend/engine/tests/test_knowledge.py -v
```

## 运行端到端 demo

```bash
# 仓库根目录运行（Mock 仓储 + Mock embedding）
PIXIU_EMBEDDING=mock python -m backend.engine.demos.run_write_pipeline
```

## 依赖关系

引擎需要 `backend/foundation/core/` 中的两个文件：

| 文件 | 内容 |
|------|------|
| `foundation/core/models.py` | Pydantic 数据模型（Evidence, KnowledgeItem, Preference...） |
| `foundation/core/repository.py` | Repository ABC 接口 |

确认这两个文件存在后即可独立开发。

## 降级模式

非麒麟开发机上设置环境变量即可完全离线开发：

```bash
export PIXIU_EMBEDDING=mock
```
