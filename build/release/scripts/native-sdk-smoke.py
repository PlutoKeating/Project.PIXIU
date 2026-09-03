#!/usr/bin/env python3
"""Strict Kylin SDK API smoke test that emits only sanitized evidence."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path


def request_json(url: str, *, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method="POST" if body else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def wait_for_capabilities(base_url: str, timeout_seconds: int = 30) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return request_json(f"{base_url}/capabilities")
        except Exception as exc:  # service activation may still be in progress
            last_error = exc
            time.sleep(1)
    raise RuntimeError("PIXIU backend did not become ready") from last_error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    capabilities = wait_for_capabilities(args.base_url)
    if not capabilities.get("contest_ready"):
        raise RuntimeError("strict Kylin SDK capabilities are not ready")

    marker = f"PIXIU native acceptance {time.time_ns()}"
    written = request_json(
        f"{args.base_url}/memory/write",
        payload={
            "source_type": "MANUAL_CONFIG",
            "raw": {"title": marker, "body": {"text": "native sdk retrieval"}},
            "scope": "user:acceptance",
        },
    )
    queried = request_json(
        f"{args.base_url}/memory/query",
        payload={"text": marker, "context_hint": {"top_k": 1}},
    )
    if written.get("status") != "accepted" or not queried.get("source_knowledge"):
        raise RuntimeError("strict SDK memory write/query did not complete")

    evidence = {
        "platform": capabilities["platform"],
        "embedding": capabilities["embedding"],
        "vector_store": capabilities["vector_store"],
        "contest_ready": True,
        "memory_write": "passed",
        "memory_query": "passed",
    }
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
