# 麒麟 SDK Python 绑定构建

本目录包含两个 pybind11 绑定模块，分别封装麒麟官方 SDK：

| 模块 | SDK | 说明 |
|------|-----|------|
| `_kylin_text_embedding` | `libkysdk-coreai-embedding` | 文本向量化（C API），仓库内 submodule：`third_party/kylin-coreai-embedding` |
| `_kylin_vector_client` | `libkysdk-vector-engine-client` | 向量数据库客户端（Milvus 式 gRPC） |

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

## 无 mock 说明

生产代码不包含任何 mock 降级：SDK 缺失或服务不可用时，`get_embedder()` /
`VectorEngineClient()` 会抛出 `KylinSDKUnavailableError`（附构建指引）。
