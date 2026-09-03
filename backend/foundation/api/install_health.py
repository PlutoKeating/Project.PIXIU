"""Post-install verification for the backend, schema, and packaged Provider."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.request import urlopen

_COMPONENT = "pixiu-memory-backend"
_AGENT_MEMORY_API = 1
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
_MANIFEST_VERSION = re.compile(r"^version:\s*([^\s]+)\s*$", re.MULTILINE)


class InstallHealthError(RuntimeError):
    """A stable, non-sensitive post-install verification failure."""


def _provider_version(path: Path) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InstallHealthError("PROVIDER_MANIFEST_UNAVAILABLE") from exc
    match = _MANIFEST_VERSION.search(content)
    if not match or not _SEMVER.fullmatch(match.group(1)):
        raise InstallHealthError("PROVIDER_VERSION_INVALID")
    return match.group(1)


def _check_once(
    expected_version: str,
    provider_manifest: Path,
    fetch_json: Callable[[str], dict[str, Any]],
) -> dict[str, str | int]:
    version = fetch_json("/version")
    if version.get("component") != _COMPONENT:
        raise InstallHealthError("BACKEND_COMPONENT_MISMATCH")
    if version.get("product_version") != expected_version:
        raise InstallHealthError("BACKEND_VERSION_MISMATCH")
    if version.get("agent_memory_api") != _AGENT_MEMORY_API:
        raise InstallHealthError("AGENT_MEMORY_API_MISMATCH")
    schema_version = version.get("schema_version")
    if not isinstance(schema_version, int) or schema_version < 1:
        raise InstallHealthError("SCHEMA_VERSION_INVALID")

    health = fetch_json("/health")
    if (
        health.get("status") != "ready"
        or health.get("database") != "ok"
        or health.get("component") != _COMPONENT
    ):
        raise InstallHealthError("BACKEND_NOT_READY")
    if health.get("product_version") != expected_version:
        raise InstallHealthError("HEALTH_VERSION_MISMATCH")
    if health.get("schema_version") != schema_version:
        raise InstallHealthError("SCHEMA_VERSION_MISMATCH")
    if _provider_version(provider_manifest) != expected_version:
        raise InstallHealthError("PROVIDER_VERSION_MISMATCH")
    return {
        "product_version": expected_version,
        "schema_version": schema_version,
    }


def verify_install(
    expected_version: str,
    provider_manifest: Path,
    *,
    fetch_json: Callable[[str], dict[str, Any]],
    attempts: int = 30,
    retry_delay: float = 1.0,
) -> dict[str, str | int]:
    if not _SEMVER.fullmatch(expected_version):
        raise InstallHealthError("EXPECTED_VERSION_INVALID")
    last_error = "BACKEND_NOT_READY"
    for attempt in range(max(1, attempts)):
        try:
            return _check_once(expected_version, provider_manifest, fetch_json)
        except (
            InstallHealthError,
            OSError,
            TimeoutError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            last_error = str(exc) if isinstance(exc, InstallHealthError) else "BACKEND_UNAVAILABLE"
            if attempt + 1 < max(1, attempts) and retry_delay:
                time.sleep(retry_delay)
    raise InstallHealthError(last_error)


def _http_fetch(endpoint: str) -> Callable[[str], dict[str, Any]]:
    def fetch(path: str) -> dict[str, Any]:
        with urlopen(f"{endpoint}{path}", timeout=2.0) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("response too large")
        decoded = json.loads(raw.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("response is not an object")
        return decoded

    return fetch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--provider-manifest", required=True, type=Path)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8765")
    parser.add_argument("--attempts", type=int, default=30)
    args = parser.parse_args(argv)
    try:
        result = verify_install(
            args.expected_version,
            args.provider_manifest,
            fetch_json=_http_fetch(args.endpoint.rstrip("/")),
            attempts=min(60, max(1, args.attempts)),
        )
    except InstallHealthError as exc:
        print(f"pixiu install health: {exc}")
        return 1
    print(
        "pixiu install health: ready "
        f"version={result['product_version']} schema={result['schema_version']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
