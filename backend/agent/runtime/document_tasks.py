"""Authenticated Runtime entrypoint for background document tasks."""
from urllib.parse import urlsplit

import httpx

from ..dreaming.runner import run_documents
from .image_draft import input_capabilities


class MemoryApi:
    def __init__(self, endpoint="http://127.0.0.1:8765"):
        parsed = urlsplit(endpoint)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.query or parsed.fragment:
            raise ValueError("Document tasks require the local memory API")
        self.endpoint = endpoint.rstrip("/")

    async def __call__(self, method, path, payload):
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
            result = await client.request(method, self.endpoint + path, json=payload)
            result.raise_for_status()
            return result.json()


async def dream_documents(model, document_ids, *, endpoint="http://127.0.0.1:8765", scope="user:local"):
    if not model:
        raise ValueError("当前资料整理不可用。")
    base = str(model.get("baseUrl") or "").rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
        raise ValueError("当前模型连接不可用。")
    headers = {"Authorization": "Bearer " + str(model.get("apiKey") or "")}

    async def model_turn(messages, tools):
        async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
            response = await client.post(base + "/chat/completions", headers=headers, json={
                "model": model["model"], "messages": messages, "tools": tools, "stream": False})
            response.raise_for_status()
            return response.json()["choices"][0]["message"]

    return await run_documents(api=MemoryApi(endpoint), model_turn=model_turn,
        document_ids=document_ids, scope=scope, vision=input_capabilities(model)["images"], approved=True)
