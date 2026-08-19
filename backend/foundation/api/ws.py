"""PIXIU Foundation — WebSocket 事件推送

提供 /events 端点和 WsManager 单例，
各模块通过 ws_manager.broadcast(event, data) 向所有前端连接推送事件。
"""

from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect

from .http_app import app
from .ws_manager import ws_manager


@app.websocket("/events")
async def events_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    await ws.send_text(json.dumps({"event": "connected", "data": {}}))
    try:
        while True:
            # 心跳：每 30 秒 ping
            await asyncio.sleep(30)
            try:
                await ws.send_text(json.dumps({"event": "ping", "data": {}}))
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(ws)
