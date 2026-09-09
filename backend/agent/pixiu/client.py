"""Small dependency-free client for the public PIXIU REST API."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_SAFE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class PixiuApiError(RuntimeError):
    """A sanitized backend failure safe to expose to the Agent runtime."""

    def __init__(self, code: str, *, status: int = 0, retryable: bool = False):
        super().__init__(code)
        self.code = code
        self.status = status
        self.retryable = retryable


class PixiuApiClient:
    def __init__(self, base_url: str, timeout: float = 2.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None
        # Product version lives in the package manifest and is checked against
        # the release version; avoid introducing another hidden version source.
        headers = {"Accept": "application/json", "User-Agent": "PIXIU-Agent"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self._base_url}{path}", data=body, headers=headers, method=method
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            code = f"HTTP_{exc.code}"
            try:
                payload = json.loads(exc.read().decode("utf-8"))
                detail = payload.get("error") or payload.get("detail")
                if isinstance(detail, str) and _SAFE_ERROR_CODE.fullmatch(detail):
                    code = detail
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                pass
            raise PixiuApiError(
                code, status=exc.code, retryable=exc.code >= 500 or exc.code == 429
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise PixiuApiError("BACKEND_UNAVAILABLE", retryable=True) from exc

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PixiuApiError("INVALID_BACKEND_RESPONSE") from exc
        if not isinstance(decoded, dict):
            raise PixiuApiError("INVALID_BACKEND_RESPONSE")
        return decoded
