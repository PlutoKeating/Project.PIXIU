"""Public API client error-contract tests."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "third_party" / "kylin-agent-runtime"))

import integrations.kylin_agent.pixiu.client as client_module
from integrations.kylin_agent.pixiu.client import PixiuApiClient, PixiuApiError


def test_http_error_preserves_backend_stable_error_code(monkeypatch):
    def fail(*args, **kwargs):
        raise HTTPError(
            url="http://127.0.0.1:8765/memory/write",
            code=409,
            msg="Conflict",
            hdrs=None,
            fp=BytesIO(
                b'{"error":"IDEMPOTENCY_FAILED","message":"redacted",'
                b'"request_id":"req_1"}'
            ),
        )

    monkeypatch.setattr(client_module, "urlopen", fail)

    with pytest.raises(PixiuApiError) as caught:
        PixiuApiClient("http://127.0.0.1:8765").request(
            "POST", "/memory/write", {"value": "not logged"}
        )

    assert caught.value.code == "IDEMPOTENCY_FAILED"
    assert caught.value.status == 409
    assert caught.value.retryable is False
