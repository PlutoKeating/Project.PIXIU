# 后端快速启动指南

后端分为两个子模块，各自可独立开发和测试。

---

## 环境准备

```bash
cd /path/to/Project.PIXIU
git submodule update --init --recursive   # 初始化麒麟 SDK submodule
pip install -r backend/requirements.txt
```

## 模块 B（记忆业务引擎）

```bash
# 引擎测试（仓库根目录运行；无麒麟 SDK 时 embedding 测试走测试桩）
python -m pytest backend/engine/tests -v
```

## 模块 C（后台基础设施）

```bash
# 启动 API 网关（开发模式，热重载）
uvicorn backend.foundation.api.http_app:app \
  --host 127.0.0.1 --port 8765 --reload

# 基础设施测试
python -m pytest backend/foundation/tests -v
```

## 麒麟 SDK 绑定构建（银河麒麟系统）

生产 embedding 与向量库调用依赖 pybind11 绑定，详见
`backend/engine/kylin/cpp/README.md`：

```bash
cd backend/engine/kylin/cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
cmake --install build
```

## 冒烟验证

```bash
# 写入一条记忆（真实链路：ingest → knowledge → preference → conflict）
curl -X POST http://127.0.0.1:8765/memory/write \
  -H "Content-Type: application/json" \
  -d '{"source_type":"MANUAL_CONFIG","raw":{"title":"output_style.compact","body":{"key":"output_style.compact","enabled":true}},"scope":"user:test"}'

# 冲突审计
curl http://127.0.0.1:8765/conflicts
```

> 12 个 REST 端点（含 `/memory/query`、`/memory/flow/promote`、`/sync/*`）已全部
> 真实实现（2026-08-10 合入 main）；默认优先麒麟 embedding，无 SDK 绑定的
> Debian 环境自动使用可移植软件向量器。正式麒麟验收使用严格 `kylin` 模式。

## 打包安装

整包 .deb（前端+后端+本地 SQLite 记忆/同步库）构建与麒麟安装见
`build/release/README.md` 与 `docs/QUICK_START.md`。

详细开发说明见 `backend/engine/docs/QUICK_START.md` 与 `backend/foundation/docs/QUICK_START.md`。
