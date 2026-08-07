# PIXIU 快速启动指南

> 本文档帮助开发人员在本地快速搭建 PIXIU 开发环境并运行。
> 各模块详细启动文档见各自 `docs/QUICK_START.md`。

---

## 环境要求

- **操作系统**：Linux（Ubuntu 22.04+ / 银河麒麟 V10+）
- **Python**：3.10+
- **C++ 编译器**：GCC 9+ / Clang 12+（C++17）
- **CMake**：≥ 3.5
- **Qt5**：Widgets / Network / WebSockets / DBus

---

## 总览

PIXIU 三个模块可独立开发与测试。

### 各模块快速启动

| 模块 | 快速命令 | 详细文档 |
|------|----------|----------|
| 模块 A（前端） | `cd frontend && cmake -B build && cmake --build build` | `frontend/docs/QUICK_START.md` |
| 模块 B（引擎） | `pip install -r backend/requirements.txt && python -m pytest backend/engine/tests` | `backend/engine/docs/QUICK_START.md` |
| 模块 C（基础设施） | `python -m backend.foundation.api.http_app` | `backend/foundation/docs/QUICK_START.md` |

### 快速验证

```bash
# 启动后端（真实麒麟 SDK，需先构建 kylin 绑定）
python -m backend.foundation.api.http_app

# 写入测试数据
curl -X POST http://127.0.0.1:8765/memory/write \
  -H "Content-Type: application/json" \
  -d '{"source_type":"MANUAL_CONFIG","raw":{"title":"测试"},"scope":"user:test"}'

# 检索（待 retrieval 阶段实现，当前返回 not_implemented）
curl -X POST http://127.0.0.1:8765/memory/query \
  -H "Content-Type: application/json" \
  -d '{"text":"测试","context_hint":{}}'
```

---

## 开发降级

非麒麟开发机上：

- 前端：`cmake -DPIXIU_HAVE_KYSDK=OFF` 启用 Qt 原生桩
- 后端：生产代码无 mock 降级；测试使用 `backend/engine/tests/fakes.py` 测试桩，
  麒麟 SDK 绑定构建见 `backend/engine/kylin/cpp/README.md`
- API 通信：自动回退至 `http://127.0.0.1:8765`
