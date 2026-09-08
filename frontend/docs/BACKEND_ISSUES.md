# Module A → Module C 后端问题交接记录

> **状态**：本文件两项问题均已修复；下文记录当前代码和复核入口，不是待实现清单。
> **范围**：本轮仅更新 Module A 文档，不修改后端实现。
> **事实来源**：`backend/foundation/api/http_app.py`、`ws.py`、
> `ws_manager.py`、`test_api.py` 和 `test_monitor_api.py`。
> **正式前端**：`frontend/management/BackendEventStatus` 复用
> `frontend/src/services/WebSocketClient`，不使用旧小窗口的事件装配层。

---

## 问题 1：`/events` WebSocket 路由未被实际启动入口注册

当前 `http_app.py` 在应用及 HTTP 路由创建后执行
`from . import ws as _ws`，使 `ws.py` 中的
`@app.websocket("/events")` 完成注册。`api/__init__.py` 导出同一应用对象。
不需要另建 WS 进程、重复注册端点或将端点移入其他模块。

`WsManager.connect` 接受连接，端点随后发送
`{"event":"connected","data":{}}`；业务推送使用 `event/data` 信封。
端点代码每 30 秒发送应用层 `ping`，不是 WebSocket 控制帧。
连接异常时从管理器移除，广播发送失败的连接也会被移除。

现有验证入口：

```bash
python -m pytest \
  backend/foundation/tests/test_api.py::test_events_websocket_is_registered \
  backend/foundation/tests/test_monitor_api.py::test_put_broadcasts_capture_event_state_changed -q
```

第一项验证实际应用注册与 `connected` 消息；第二项通过测试配置写入验证
`capture_event` 及其字段。测试使用临时 SQLite、替身设置并关闭采集运行时及同步
网络，不操作用户实际采集授权。两项不验证 30 秒心跳、网络恢复或 SDK 通知。

---

## 问题 2：`ws.py` 使用 `WebSocket` 类型标注但未导入，注册时触发导入错误

当前导入为 `from fastapi import WebSocket, WebSocketDisconnect`，
`events_endpoint(ws: WebSocket)` 的注解依赖已提供，无需再补导入。
上述实际应用握手测试同时覆盖路由模块成功加载和端点注册，不能仅以语法检查
替代运行时验证。若后续出现导入错误，应保留实际 traceback 并核对已安装包与
源码提交，不直接套用已失效的修复建议。

---

## 备注

- 正式宿主中的事件连接状态与后端健康状态分开显示；WS 连接成功不证明数据库、
  模型、SDK 或所有业务页面可用。
- `BackendEventStatus` 将已知业务事件映射为页面失效提示；广播不是写入、配对
  或遗忘授权，不弹出旧式确认执行窗口。未知事件不触发业务动作。
- 事件协议没有重放游标；重连要求重新读取实际状态，不能假定离线期间事件完整。
- 高严重度冲突可触发固定脱敏通知，通知不携带事件正文或操作凭证；
  完整原生通知、断线恢复和跨设备矩阵见 `docs/UNIFIED_FRONTEND_PLAN.md`。
- API 契约以 `docs/API.md` 为准；正式前端的页面和生命周期以
  `frontend/docs/ARCHITECTURE.md` 为准。旧窗口或测试桩画面不作为当前产品证据。
