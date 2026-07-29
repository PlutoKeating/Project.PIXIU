"""PIXIU Foundation — WebSocket 事件推送

提供 /events 端点和 WsManager 单例，
各模块通过 ws_manager.broadcast(event, data) 向所有前端连接推送事件。
"""

from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect

from .http_app import app


class WsManager:
    """WebSocket 连接管理器（单例）。"""

    def __init__(self):
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def broadcast(self, event: str, data: dict) -> None:
        """向所有已连接的前端推送事件。"""
        payload = json.dumps({"event": event, "data": data}, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

    @property
    def online_count(self) -> int:
        return len(self._connections)


ws_manager = WsManager()


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
