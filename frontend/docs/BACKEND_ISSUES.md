# Module A → Module C 后端问题交接记录

> **来源**：Module A 在实现并本地验收 `WebSocketClient`
> （`frontend/src/services/WebSocketClient.{h,cpp}`）时，结合后端代码审查与联调准备
> 发现的后端问题。
> **边界**：本文件仅为问题记录，Module A 未修改任何 `backend/` 文件；修复由
> Module C 负责人执行。
> **状态**：✅ 已由 Module C 修复（2026-08-20）。
> **复核（2026-08-11）**：`feat/foundation` 合入 main 后两项问题仍存在
> （`http_app.py` 未导入 `ws.py`、`ws.py` 未导入 `fastapi.WebSocket`）；
> 前端已具备退避重连与事件路由，修复后无需改前端。
> **修复验证（2026-08-20）**：`http_app.py` 在 `app` 建立后加载 WS 路由，
> `ws.py` 补齐 `WebSocket` 导入；TestClient 握手测试通过，麒麟 V11 安装包中的
> 真实前端已连接 `ws://127.0.0.1:8765/events`，不再返回 403。
>
> 下文的问题现象、根因和修复建议均为历史审计记录，不是当前阻塞清单。当前状态
> 以 `docs/API.md` 和 Module C 任务书为准。

---

## 问题 1：`/events` WebSocket 路由未被实际启动入口注册

- **涉及文件**
  - `backend/foundation/api/ws.py`（路由定义所在）
  - `backend/foundation/api/http_app.py`（实际启动入口）
  - `backend/foundation/api/__init__.py`（包导出）
- **复现方式**
  1. 按 `backend/foundation/docs/QUICK_START.md` 启动后端：
     `python -m backend.foundation.api.http_app`
     （或 `uvicorn backend.foundation.api.http_app:app`）。
  2. 列出已注册路由，确认 `/events` 缺失：
     `python -c "from backend.foundation.api import app; print([r.path for r in app.routes])"`
  3. 用任意 WebSocket 客户端连接 `ws://127.0.0.1:8765/events`。
- **现象**
  - 后端启动成功、REST 端点可用，但 `/events` 不在 `app.routes` 中；
  - WebSocket 连接被拒绝/404，收不到 `connected`/`ping`；
  - 前端 `WebSocketClient` 将按指数退避策略无限重连，连接状态始终无法建立。
- **根因**
  - `/events` 通过 `ws.py` 的模块级副作用 `@app.websocket("/events")` 注册，
    但所有真实启动路径都未导入 `ws.py`：`http_app.py` 只导入 `ws_manager`，
    `api/__init__.py` 也只导出 `http_app` + `ws_manager`，因此注册代码从未执行。
- **建议修复方案**
  1. 在 `backend/foundation/api/http_app.py` 末尾（`app` 创建之后）追加
     `from . import ws  # noqa: E402,F401`，强制在启动时完成路由注册；
     或
  2. 将 `@app.websocket("/events")` 端点直接移入 `http_app.py`，移除 `ws.py`；
     或
  3. 将 `/events` 端点移入 `APIRouter`，通过 `app.include_router(router)` 显式装配
     （或使用 `app.add_api_websocket_route("/events", events_endpoint)`）。
  - 注意：`ws.py` 顶部 `from .http_app import app` 与方案 1 组合不会产生循环导入
    （`ws` 在 `http_app` 定义完成后才被导入），但不要在 `http_app.py` 顶部导入 `ws`。
- **验收建议**：启动后 `app.routes` 包含 `/events`；用 TestClient 或真实客户端完成
  一次 WS 连接 + `connected` + `ping` 冒烟。

---

## 问题 2：`ws.py` 使用 `WebSocket` 类型标注但未导入，注册时触发导入错误

- **涉及文件**
  - `backend/foundation/api/ws.py`
- **复现方式**
  1. 安装依赖后执行：`python -c "import backend.foundation.api.ws"`；
  2. 或按「问题 1」修复方案接入 `ws.py` 后启动后端。
- **现象**
  - 导入 `backend.foundation.api.ws` 时抛出
    `NameError: name 'WebSocket' is not defined`；
  - 一旦问题 1 修复（启动时导入 `ws.py`），后端会在注册 `/events` 的瞬间启动失败。
- **根因**
  - `ws.py` 仅 `from fastapi import WebSocketDisconnect`，却以 `ws: WebSocket` 作为
    端点参数标注，`WebSocket` 从未导入；
  - 文件启用了 `from __future__ import annotations`，注解以字符串保存，FastAPI 在构造
    WebSocket 路由时解析签名并求值该字符串，因而触发 `NameError`。
- **建议修复方案**
  - 将 `ws.py` 的导入改为：`from fastapi import WebSocket, WebSocketDisconnect`。
- **验收建议**：`python -c "import backend.foundation.api.ws"` 通过；随后完成问题 1
  的 WS 冒烟验证。

---

## 备注

- 两项问题相互叠加：只修问题 2 不修问题 1，`/events` 仍不可用；只修问题 1 不修
  问题 2，后端会在导入 `ws.py` 时启动失败。建议两项一并修复。
- Module A 侧 `WebSocketClient` 已完成真实环境复测；原“待修复后复测”状态已关闭。
- 复现说明：本记录基于代码路径静态确认（开发机未安装 fastapi/uvicorn，未做运行时
  复现）；建议 Module C 在已安装依赖的环境执行上述命令复核。
- 补充（2026-08-08）：Module A 已用测试专用 WS 桩（`frontend/scripts/ws_smoke_server.py`，
  仅 UI 冒烟、不参与生产路径）在真实 UKUI 会话完成 `memory_ready` → 通知弹窗
  UI 链路冒烟（`kysdk notification sent, id: 5`），确认前端事件分发可用；
  后端 `/events` 修复后已按问题 1/2 的验收建议完成真实连接复测。
