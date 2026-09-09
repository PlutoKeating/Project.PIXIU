"""Public Runtime API client for automatic document capture."""
from __future__ import annotations

import base64
import os
from pathlib import Path

import httpx
from dotenv import dotenv_values


class AgentMediaClient:
    def __init__(self, authorize_source=lambda path: False):
        self.authorize_source = authorize_source

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

    async def capture(self, path: str):
        from .monitor.ingest_bridge import CaptureResult, STATUS_INGESTED, STATUS_IGNORED
        import time
        file = Path(path)
        if not self.authorize_source(str(file.absolute())):
            return CaptureResult(STATUS_IGNORED, f"目录授权已取消，未读取：{file.name}", ts=int(time.time()))
        if file.stat().st_size > 30 * 1024 * 1024:
            return CaptureResult(STATUS_IGNORED, f"文件过大，尚未整理：{file.name}", ts=int(time.time()))
        base, headers = self._connection()
        endpoint = os.environ.get("PIXIU_AGENT_ENDPOINT", "http://127.0.0.1:8765").rstrip("/")
        reference = None
        async with httpx.AsyncClient(timeout=1800, follow_redirects=False) as client:
            try:
                registered = await client.post(endpoint + "/documents", json={"filename": file.name,
                    "source_path": str(file.absolute()), "file_base64": base64.b64encode(file.read_bytes()).decode()})
                registered.raise_for_status()
                reference = registered.json()["document_id"]
                response = await client.post(base + "/api/memory/dreaming", headers=headers,
                                             json={"document_ids": [reference]})
                response.raise_for_status()
                result = response.json()
                complete = result.get("status") == "completed"
                summary = (f"已整理 {file.name}，保存 {result.get('saved_count', 0)} 条记忆" if complete
                           else f"{file.name} 尚未完整整理，已保存 {result.get('saved_count', 0)} 条记忆")
                return CaptureResult(STATUS_INGESTED if complete else STATUS_IGNORED, summary, ts=int(time.time()))
            finally:
                if reference:
                    await client.delete(endpoint + "/documents/" + reference)
