# 模块 B · 记忆业务引擎 —— 快速启动

> 当前命令验证五类 Connector，包括 `CONVERSATION` 与增强 `TOOL_RESULT`
> provenance 基础契约；幂等、生命周期和 Module E 尚未完成，测试通过不等于完整
> Agent 闭环通过。

---

## 环境

```bash
cd /path/to/Project.PIXIU
git submodule update --init --recursive   # 初始化麒麟 SDK submodule
pip install -r backend/requirements.txt
```

## 运行测试

```bash
# 全部引擎测试（仓库根目录运行；无麒麟 SDK 时 embedding 测试走测试桩）
python -m pytest backend/engine/tests -v

# 单模块测试
python -m pytest backend/engine/tests/test_ingest.py -v
python -m pytest backend/engine/tests/test_knowledge.py -v
```

## 麒麟 SDK 绑定构建（银河麒麟系统）

麒麟原生 embedding 与向量库调用依赖 pybind11 绑定，详见
`backend/engine/kylin/cpp/README.md`：

```bash
cd backend/engine/kylin/cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
cmake --install build
```

构建产物安装到 `backend/engine/kylin/`。默认 `PIXIU_EMBEDDING=auto`：优先调用
真实 SDK，缺失时使用可移植软件向量器；`PIXIU_EMBEDDING=kylin` 为严格麒麟验收
模式并在 SDK 不可用时抛出 `KylinSDKUnavailableError`，`portable` 可用于通用
Debian 验证。向量存储同样使用 `PIXIU_VECTOR_STORE=auto|kylin|portable`；
`kylin` 模式连接或 SDK 不可用时依赖装配立即失败，只有 `auto` 允许记录告警后
降级。

## 依赖关系

引擎通过 `backend/foundation/core/` 契约消费存储层：

| 文件 | 内容 |
|------|------|
| `foundation/core/models.py` | Pydantic 数据模型（Evidence, KnowledgeItem, Preference...） |
| `foundation/core/repository.py` | Repository ABC 接口 |

## 麒麟 SDK submodule

- `third_party/kylin-coreai-embedding` —— 文本向量化（C API）
- `third_party/libkysdk-vector-engine-client` —— 向量数据库客户端（C++/gRPC）
