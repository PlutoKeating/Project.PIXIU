"""Authenticated Runtime entrypoint for background document tasks."""
from urllib.parse import urlsplit

import httpx

from ..dreaming.runner import run_documents
from ..dreaming.runner import content_blocks, wire_content
from ..mcp.documents import build_server
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


async def prepare_document_attachment(model, payload, *, endpoint="http://127.0.0.1:8765"):
    """Read all attachment blocks through the same MCP adapter, without memory writes."""
    api = MemoryApi(endpoint)
    registered = await api("POST", "/documents", {
        "filename": payload.get("filename") or "attachment.png",
        "file_base64": payload.get("file_base64") or payload.get("image_base64"),
    })
    reference = registered["document_id"]
    try:
        server = build_server(endpoint, frozenset([reference]), api=api)
        vision = input_capabilities(model)["images"]
        parts = []
        unread = []
        for cursor, entry in enumerate(registered["blocks"]):
            if entry["kind"] == "image" and not vision:
                unread.append(entry["location"])
                continue
            result = await server.call_tool("document_read", {"document_id": reference, "cursor": cursor})
            parts.extend(wire_content(content_blocks(result)))
        if not parts:
            raise ValueError("当前模型无法读取这份资料，详情见设置。")
        warnings = list(registered.get("warnings", []))
        if unread:
            warnings.append("当前模型无法读取以下图片内容：" + "、".join(unread))
        if warnings:
            parts.insert(0, {"type": "text", "text": "资料尚未完整读取：" + "；".join(warnings)})
        return {"content": parts, "kind": "document", "warnings": warnings,
                "read_blocks": len(registered["blocks"]) - len(unread),
                "total_blocks": len(registered["blocks"])}
    finally:
        await api("DELETE", "/documents/" + reference, None)
