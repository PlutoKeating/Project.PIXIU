import json

import pytest

from backend.agent.runtime import document_tasks


@pytest.mark.asyncio
async def test_large_text_attachment_defers_reading_and_keeps_original_available(monkeypatch):
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
    guide = json.loads(result["content"][0]["text"].split("\n")[-1])
    assert guide == {"document_id": reference, "version": "v1", "total_blocks": 30, "cursor": 0, "images_available": False, "warnings": []}
    assert result["read_blocks"] == 0 and result["total_blocks"] == 30
    assert len(result["content"][0]["text"]) < 1000
    assert calls == [("POST", "/documents")]


@pytest.mark.asyncio
@pytest.mark.parametrize('vision', [True, False])
async def test_multipage_visual_attachment_is_deferred_or_disabled(monkeypatch, vision):
    calls = []
    class Api:
        def __init__(self, endpoint):
            self.endpoint = endpoint
        async def __call__(self, method, path, payload):
            calls.append(method)
            if method == 'POST':
                return {'document_id': 'a' * 64, 'version': 'b' * 64,
                        'blocks': [{'id': f'block-{i}', 'kind': 'image'} for i in range(10)], 'warnings': []}
            assert method == 'DELETE'
            return {'status': 'revoked'}
    monkeypatch.setattr(document_tasks, 'MemoryApi', Api)
    monkeypatch.setattr(document_tasks, 'input_capabilities', lambda model: {'images': vision})
    if vision:
        result = await document_tasks.prepare_document_attachment({}, {'filename': '扫描.pdf', 'file_base64': 'dGVzdA=='})
        assert result['read_blocks'] == 0 and result['total_blocks'] == 10
        assert len(result['content']) == 1 and calls == ['POST']
        guide = json.loads(result['content'][0]['text'].split('\n')[-1])
        assert guide['images_available'] is True
    else:
        with pytest.raises(ValueError, match='当前模型无法读取'):
            await document_tasks.prepare_document_attachment({}, {'filename': '扫描.pdf', 'file_base64': 'dGVzdA=='})
        assert calls == ['POST', 'DELETE']
