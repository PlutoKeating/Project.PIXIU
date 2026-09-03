"""Version checks for the packaged Provider, backend, and Agent host."""

from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path

EXPECTED_AGENT_MEMORY_API = 1
EXPECTED_BACKEND_COMPONENT = "pixiu-memory-backend"

_SEMVER = re.compile(r"^([0-9]+)\.([0-9]+)\.([0-9]+)(?:[-+][0-9A-Za-z.-]+)?$")
_MANIFEST_VERSION = re.compile(r"^version:\s*([^\s]+)\s*$", re.MULTILINE)


def provider_version() -> str:
    manifest = Path(__file__).with_name("plugin.yaml").read_text(encoding="utf-8")
    match = _MANIFEST_VERSION.search(manifest)
    if not match or not _SEMVER.fullmatch(match.group(1)):
        raise RuntimeError("PIXIU_PROVIDER_VERSION_INVALID")
    return match.group(1)


def detected_runtime_version() -> str:
    try:
        return metadata.version("kylin-agent-runtime")
    except metadata.PackageNotFoundError:
        try:
            from kylin_agent_runtime_cli import __version__
        except (ImportError, AttributeError):
            return "unknown"
        return str(__version__)


def runtime_version_supported(version: str) -> bool:
    match = _SEMVER.fullmatch(version)
    if not match:
        return False
    major, minor, _patch = (int(part) for part in match.groups())
    return (major, minor) == (0, 9)
