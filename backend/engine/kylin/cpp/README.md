# 麒麟 SDK Python 绑定构建

> [!CAUTION]
> 绑定可编译不等于赛题双 SDK 通过。Vector Engine 已接入生产 Repository/retrieval
> 的严格选择路径，但 H-02 仍须在 V11 严格画像验证实际建库、写入、删除和查询。
> 软件包名还须以目标机 profile 与官方 SDK 源为准，不以本文示例替代环境取证。

本目录包含两个 pybind11 绑定模块，分别封装麒麟官方 SDK：

| 模块 | SDK | 说明 |
|------|-----|------|
| `_kylin_text_embedding` | `libkysdk-coreai-embedding` | 文本向量化（C API），仓库内 submodule：`third_party/kylin-coreai-embedding` |
| `_kylin_vector_client` | `libkysdk-vector-engine-client` | 向量数据库客户端（Milvus 式 gRPC） |

`_kylin_vector_client` 当前封装集合存在/创建/装载/删除与向量
insert/upsert/delete/search。Python 删除接口只接受 `int64` 主键列表，由绑定内部
构造 SDK 表达式；业务层不得传入任意过滤字符串。

## 环境要求（银河麒麟系统）

```bash
# SDK 运行库与开发包
sudo apt install libkylin-coreai-embedding libkylin-coreai-embedding-dev
sudo apt install libkysdk-vector-engine-client libkysdk-vector-engine-client-dev

# 公共依赖
sudo apt install libkylin-ai-proto-dev libkysdk-ai-common-dev \
                 libglib2.0-dev libgio-2.0-dev libsqlite3-dev
sudo apt install python3-pybind11 nlohmann-json3-dev

# 向量客户端额外依赖（gRPC/protobuf/SQLiteCpp/sqlcipher）
sudo apt install libgrpc++-dev protobuf-compiler-grpc \
                 libsqlitecpp-dev libsqlcipher-dev
```

> 向量数据库 SDK 依赖麒麟 AI gRPC 协议包（`KylinAiProto`）与
> `kysdk-ai-common`，如系统未提供请从麒麟软件源或官方仓库安装。

## 构建

```bash
cd backend/engine/kylin/cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
cmake --install build
```

构建产物（`_kylin_text_embedding*.so`、`_kylin_vector_client*.so`）会安装到
`backend/engine/kylin/`，Python 侧即可 `import backend.engine.kylin`。

## 运行前提

- 文本向量化：麒麟 AI 运行时服务（coreai）必须在线，`text_embedding_init_session`
  通过 D-Bus 连接服务并加载端侧模型。
- 向量数据库：向量引擎服务需已启动（默认 `127.0.0.1:19530`），客户端通过 gRPC 连接。

文本 wrapper 在构造任一步失败时销毁 SDK session，拒绝未知或漂移的向量维度；同一
session 的同步调用由互斥锁保护，并在阻塞调用期间释放 Python GIL。该设计允许多个
Python 工作线程安全排队，但是否创建多个 session 以提升吞吐须以 V11 压测结果决定。

## 能力选择说明

`get_embedder("auto")` 优先加载这里构建的真实扩展，缺失时使用独立的 Debian
软件向量器；`get_embedder("kylin")` 与 `VectorEngineClient()` 在 SDK/服务不
可用时抛出 `KylinSDKUnavailableError`。只有严格 `kylin` 路径可用于 SDK 验收。
