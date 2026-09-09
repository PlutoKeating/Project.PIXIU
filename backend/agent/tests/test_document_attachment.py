import json

import pytest

from backend.agent.runtime import document_tasks


@pytest.mark.asyncio
async def test_attachment_keeps_all_large_text_blocks_and_revokes_staging(monkeypatch):
    reference = "a" * 64
    blocks = [{"id": f"block-{i}", "kind": "text", "location": f"sheet:{i}",
               "text": str(i) + "正文" * 3000} for i in range(30)]
    calls = []

    class Api:
        def __init__(self, endpoint):
            self.endpoint = endpoint

        async def __call__(self, method, path, payload):
            calls.append((method, path))
            if method == "POST":
                return {"document_id": reference, "version": "v1", "blocks": blocks, "warnings": []}
            if method == "DELETE":
                return {"status": "revoked"}
            cursor = int(path.split("cursor=")[1])
            return {"document_id": reference, "version": "v1", "block": dict(blocks[cursor]),
                    "next_cursor": cursor + 1 if cursor < 29 else None}

    monkeypatch.setattr(document_tasks, "MemoryApi", Api)
    monkeypatch.setattr(document_tasks, "input_capabilities", lambda model: {"images": False})
    result = await document_tasks.prepare_document_attachment({}, {"filename": "长文档.docx", "file_base64": "dGVzdA=="})
    recovered = [json.loads(part["text"])["block"]["text"] for part in result["content"]]
    assert recovered == [block["text"] for block in blocks]
    assert result["read_blocks"] == result["total_blocks"] == 30
    assert calls[-1] == ("DELETE", "/documents/" + reference)
