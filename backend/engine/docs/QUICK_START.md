# 模块 B · 记忆业务引擎 —— 快速启动

---

## 环境

```bash
cd backend
pip install -r requirements.txt
```

## 运行测试

```bash
# 全部引擎测试（mock embedding）
PIXIU_EMBEDDING=mock pytest engine/tests/ -v

# 单模块测试
PIXIU_EMBEDDING=mock pytest engine/tests/test_ingest.py -v
PIXIU_EMBEDDING=mock pytest engine/tests/test_knowledge.py -v
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
