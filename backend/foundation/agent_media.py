"""Public Runtime API client for automatic document capture."""
from __future__ import annotations

import base64
import os
from pathlib import Path

import httpx
from dotenv import dotenv_values


class AgentMediaClient:
    def _connection(self):
        home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".kylin-agent-runtime")))
        env = dotenv_values(home / ".env")
        port = str(env.get("API_SERVER_PORT") or os.environ.get("API_SERVER_PORT", "8642"))
        key = str(env.get("API_SERVER_KEY") or os.environ.get("API_SERVER_KEY", ""))
        return "http://127.0.0.1:" + str(int(port)), {"Authorization": "Bearer " + key} if key else {}

    async def capabilities(self):
        try:
            base, headers = self._connection()
            async with httpx.AsyncClient(timeout=15) as client:
                result = await client.get(base + "/api/memory/input-capabilities", headers=headers)
                result.raise_for_status()
                return result.json()
        except (OSError, ValueError, httpx.HTTPError):
            return {"images": False, "scanned_pdf": False, "message": "当前资料读取不可用。"}

    async def understand(self, path: str):
        file = Path(path)
        if file.stat().st_size > 6 * 1024 * 1024:
            return None
        base, headers = self._connection()
        async with httpx.AsyncClient(timeout=100) as client:
            result = await client.post(base + "/api/memory/image-draft", headers=headers,
                json={"filename": file.name, "file_base64": base64.b64encode(file.read_bytes()).decode()})
            if result.status_code == 422:
                return None
            result.raise_for_status()
            return result.json()
