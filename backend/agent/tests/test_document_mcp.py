"""Exercise real stdio MCP transport and task grants with a local API fixture."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from backend.agent.dreaming.session import DreamingSession
from backend.agent.mcp.documents import build_server
from backend.agent.dreaming.runner import content_blocks


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["update", "merge"])
async def test_proposal_reaches_review_without_a_second_model_apply(operation):
    reference = "a" * 64
    identifiers = ["knw_" + "A" * 26, "knw_" + "B" * 26]
    queued = []

    class Api:
        endpoint = "http://127.0.0.1:8765"

        async def __call__(self, method, path, payload):
            assert method == "POST" and path == "/dreaming/plans"
            queued.append(payload)
            return {"plan_id": "persisted-review", "status": "awaiting_approval"}

    session = DreamingSession(Api(), document_ids=[reference], scope="user:local",
                              approved=True, queue_reviews=True)
    session.record_description({"document_id": reference, "version": "v1",
                                "blocks": [{"id": "block-1"}], "decoding_complete": True})
    session.record_delivery({"document_id": reference, "version": "v1",
                             "block": {"id": "block-1", "kind": "text", "text": "New meeting date"}})
    for identifier in identifiers:
        session.memory_snapshots[identifier] = {"version": 1, "scope": "user:local"}
    server = build_server(Api.endpoint, frozenset([reference]), dreaming=session, api=session.api)
    output = await server.call_tool("memory_plan", {
        "title": "Meeting", "text": "New meeting date", "operation": operation,
        "knowledge_id": identifiers[0], "merge_ids": identifiers if operation == "merge" else [],
        "source_refs": [{"document_id": reference, "version": "v1", "block_id": "block-1"}],
    })
    plan = json.loads(content_blocks(output)[0].text)
    assert plan["review"]["plan_id"] == "persisted-review"
    assert session.report("Waiting")["status"] == "awaiting_approval"
    assert not session.results
    await server.call_tool("memory_apply", {"plan_id": plan["plan_id"]})
    assert len(queued) == 1


@pytest.mark.asyncio
async def test_stdio_document_tools_enforce_grants_and_deliver_images():
    reference = "a" * 64
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            requests.append(self.path)
            if "/read?" in self.path:
                body = {"document_id": reference, "version": "v1", "next_cursor": None,
                        "block": {"id": "block-1", "kind": "image", "location": "page 1",
                                  "mime_type": "image/png", "data_base64": "aW1hZ2U="}}
            else:
                body = {"document_id": reference, "name": "test.png", "warnings": [],
                        "blocks": [{"id": "block-1", "kind": "image", "location": "page 1"}]}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "backend.agent.mcp.documents"],
            cwd=str(Path(__file__).resolve().parents[3]),
            env={**os.environ, "PIXIU_DOCUMENT_GRANTS": json.dumps([reference]),
                 "PIXIU_AGENT_ENDPOINT": f"http://127.0.0.1:{http.server_port}"},
        )
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                listing = await session.list_tools()
                assert {tool.name for tool in listing.tools} == {"document_describe", "document_read"}
                rejected = await session.call_tool("document_read", {"document_id": "b" * 64})
                assert rejected.isError and not requests
                result = await session.call_tool("document_read", {"document_id": reference})
                assert not result.isError
                assert [block.type for block in result.content] == ["text", "image"]
                assert result.content[1].mimeType == "image/png"
                metadata = json.loads(result.content[0].text)
                assert metadata["block"]["location"] == "page 1"
                assert "data_base64" not in metadata["block"]
                assert metadata["next_cursor"] is None
    finally:
        http.shutdown()
        http.server_close()
        thread.join()
