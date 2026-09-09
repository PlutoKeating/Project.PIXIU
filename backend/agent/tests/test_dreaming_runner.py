import json

import pytest

from backend.agent.dreaming.runner import run_documents


@pytest.mark.asyncio
async def test_model_uses_fixed_tools_for_every_source_block_and_cannot_run_shell():
    reference = "a" * 64
    written = []
    model_inputs = []
    tool_names = []

    class Api:
        endpoint = "http://127.0.0.1:8765"

        async def __call__(self, method, path, payload):
            if path.endswith("/read?cursor=0"):
                return {"document_id": reference, "version": "v1", "next_cursor": None,
                        "block": {"id": "block-1", "kind": "text", "text": "电费50元"}}
            if path.startswith("/documents/"):
                return {"document_id": reference, "version": "v1", "name": "账单.txt",
                        "blocks": [{"id": "block-1", "kind": "text"}],
                        "warnings": [], "decoding_complete": True}
            assert method == "POST" and path == "/memory/write"
            written.append(payload)
            return {"knowledge_id": "knw_created"}

    def call(name, arguments):
        return {"content": None, "tool_calls": [{"id": "call-1", "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)}}]}

    async def model_turn(messages, tools):
        model_inputs.append(json.loads(json.dumps(messages)))
        tool_names.extend(tool["function"]["name"] for tool in tools)
        count = len(model_inputs)
        if count == 1:
            return call("shell", {"command": "delete everything"})
        if count == 2:
            assert json.loads(messages[-1]["content"])["error"] == "TOOL_NOT_ALLOWED"
            return call("memory_plan", {"title": "电费", "text": "电费50元", "source_refs": [
                {"document_id": reference, "version": "v1", "block_id": "block-1"}]})
        if count == 3:
            content = json.loads(messages[-1]["content"])
            plan_id = json.loads(content[0]["text"])["plan_id"]
            return call("memory_apply", {"plan_id": plan_id})
        return {"content": "已记住"}

    updates = []

    async def progress(event):
        updates.append(event)

    result = await run_documents(api=Api(), model_turn=model_turn,
        document_ids=[reference], scope="user:local", vision=False, approved=True, progress=progress)
    assert result["status"] == "completed" and result["saved_count"] == 1
    assert len(written) == 1
    assert written[0]["raw"]["body"]["document_sources"][0]["block"]["text"] == "电费50元"
    assert "电费50元" in model_inputs[0][1]["content"][0]["text"]
    assert set(tool_names) == {"memory_search", "memory_plan", "memory_apply", "dreaming_report"}

    assert [event["processed_blocks"] for event in updates] == [0, 1]
    assert [event["saved_count"] for event in updates] == [0, 1]
