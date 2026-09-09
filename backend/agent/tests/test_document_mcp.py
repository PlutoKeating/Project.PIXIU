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
