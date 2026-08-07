"""PIXIU Foundation — WebSocket 连接管理器（单例）。"""

from __future__ import annotations

import json

from fastapi import WebSocket


class WsManager:
    """WebSocket 连接管理器（单例）。"""

    def __init__(self) -> None:
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
