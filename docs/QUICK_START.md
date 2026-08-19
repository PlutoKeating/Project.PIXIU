# PIXIU 快速启动指南

> 本文档帮助开发人员在本地快速搭建 PIXIU 开发环境并运行，也覆盖"打包安装
> 整个软件"的快速路径。各模块详细启动文档见各自 `docs/QUICK_START.md`；
> 打包/CICD 细节见 `build/release/README.md`。

---

## 环境要求

- **操作系统**：Linux（Ubuntu 22.04+ / 银河麒麟 V10+）
- **Python**：3.10+（麒麟 V11 实测 3.12.3）
- **C++ 编译器**：GCC 9+ / Clang 12+（C++17）
- **CMake**：≥ 3.5（建议 3.20+）
- **Qt5**：Widgets / Network / WebSockets（前端构建必需）

## 各模块快速启动

| 模块 | 快速命令 | 详细文档 |
|------|----------|----------|
| 模块 A（前端） | `cmake -S frontend -B build/frontend -DPIXIU_HAVE_KYSDK=OFF && cmake --build build/frontend` | `frontend/docs/QUICK_START.md` |
| 模块 B（引擎） | `pip install -r backend/requirements.txt && python -m pytest backend/engine/tests -q` | `backend/engine/docs/QUICK_START.md` |
| 模块 C（基础设施） | `python -m backend.foundation.api.http_app`（默认 127.0.0.1:8765） | `backend/foundation/docs/QUICK_START.md` |

## 开发模式运行

```bash
# 1) 初始化麒麟 SDK submodule（依赖 SDK 的构建/测试前必做）
git submodule update --init --recursive

# 2) 后端依赖与启动（无麒麟 SDK 绑定时写入/检索会如实报错）
pip install -r backend/requirements.txt
python -m backend.foundation.api.http_app

# 3) 写入一条记忆（真实链路：ingest → knowledge → preference → conflict）
curl -X POST http://127.0.0.1:8765/memory/write \
  -H "Content-Type: application/json" \
  -d '{"source_type":"MANUAL_CONFIG","raw":{"title":"测试"},"scope":"user:test"}'

# 4) 混合检索（BM25+ANN+Graph，真实麒麟 SDK 环境下可用）
curl -X POST http://127.0.0.1:8765/memory/query \
  -H "Content-Type: application/json" \
  -d '{"text":"测试","context_hint":{"top_k":5}}'

# 5) 前端（KYSDK=OFF 降级构建；麒麟机器可用 KYSDK=ON）
cmake -S frontend -B build/frontend -DPIXIU_HAVE_KYSDK=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build/frontend -j
PIXIU_BACKEND_URL=http://127.0.0.1:8765 ./build/frontend/pixiu-frontend
```

## 打包并安装整个软件（生产路径）

```bash
# 一键构建整包 .deb（前端+后端+本地 SQLite 记忆/同步库 + systemd 服务）
PIXIU_PROFILE=kylin-v11-x86_64 make -C build/release deb

# 全新麒麟机安装
sudo bash build/release/scripts/provision-target.sh kylin-v11-x86_64
sudo apt-get install -y ./build/release/out/pixiu_0.1.0-1_amd64.deb
```

安装后后端以 `pixiu-backend.service` 常驻，SQLite 数据库自动创建于
`/var/lib/pixiu/pixiu.db`；桌面菜单/`pixiu` 命令打开前端。详见
`build/release/README.md` 与 `frontend/docs/DEMO_GUIDE.md`。

## 开发降级

非麒麟开发机上：

- 前端：`cmake -DPIXIU_HAVE_KYSDK=OFF` 降级构建（`QShortcut`/`QSystemTrayIcon`
  替代 kysdk 快捷键/通知）；
- 后端：默认 `PIXIU_EMBEDDING=auto` 优先调用麒麟 SDK；无 SDK 时切换到本地
  特征哈希向量器，核心端点保持可用。`kylin` 为严格验收模式，`portable` 为
  Debian 通用验证模式；测试桩仅用于隔离单元测试；
- 演示 UI：`python3 frontend/scripts/demo_stub_server.py --port 8877` +
  `PIXIU_BACKEND_URL=http://127.0.0.1:8877` 可无后端完整演示前端（见
  `frontend/docs/DEMO_GUIDE.md` §5）。
