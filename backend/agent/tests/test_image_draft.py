"""The model sees the image, while extraction never invokes the Agent tool loop."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from backend.agent.runtime.image_draft import DraftError, image_draft, parse_draft


@pytest.mark.asyncio
async def test_image_understanding_uses_configured_model_and_returns_only_draft():
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            body = json.dumps({"choices": [{"message": {"content": json.dumps({
                "title": "家庭账单", "text": "燃气费用需核对", "items": [
                    {"date": "2026-04-01", "category": "水电燃气", "vendor": "燃气费", "amount": 186}]}, ensure_ascii=False)}}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        result = await image_draft([{"id": "vision", "model": "vision-model", "provider": "custom",
            "baseUrl": f"http://127.0.0.1:{server.server_port}/v1"}], {
            "model_id": "vision", "image_base64": "iVBORw0KGgo="})
    finally:
        server.shutdown(); server.server_close(); thread.join()
    assert result["items"][0]["amount"] == 186
    assert calls[0]["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "tools" not in calls[0]
    assert len(calls) == 1


def test_uncertain_amount_is_not_invented():
    assert parse_draft('{"items":[{"vendor":"模糊项目","amount":null}]}')["items"][0]["amount"] is None
    with pytest.raises(DraftError):
        parse_draft("not a structured draft")


@pytest.mark.asyncio
async def test_text_only_bridge_is_not_used_as_image_model():
    with pytest.raises(DraftError, match="仅支持文本"):
        await image_draft([{"id": "text", "provider": "kylin-genai"}],
                          {"model_id": "text", "image_base64": "iVBORw0KGgo="})
