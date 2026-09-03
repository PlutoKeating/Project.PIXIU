"""Version checks for the packaged Provider, backend, and Agent host."""

from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path

EXPECTED_AGENT_MEMORY_API = 1
EXPECTED_BACKEND_COMPONENT = "pixiu-memory-backend"
EXPECTED_HTTP_API = (0, 3)

_SEMVER = re.compile(r"^([0-9]+)\.([0-9]+)\.([0-9]+)(?:[-+][0-9A-Za-z.-]+)?$")
_MANIFEST_VERSION = re.compile(r"^version:\s*([^\s]+)\s*$", re.MULTILINE)


def provider_version() -> str:
    package_dir = Path(__file__).resolve().parent
    manifest_path = package_dir / "plugin.yaml"
    if manifest_path.is_file():
        manifest = manifest_path.read_text(encoding="utf-8")
        match = _MANIFEST_VERSION.search(manifest)
        if match and _SEMVER.fullmatch(match.group(1)):
            return match.group(1)

    # Source checkouts retain only a template; release packaging renders the
    # installed plugin.yaml from the repository's canonical VERSION file.
    template_path = package_dir / "plugin.yaml.in"
    repository_version = package_dir.parents[2] / "VERSION"
    if template_path.is_file() and repository_version.is_file():
        template = template_path.read_text(encoding="utf-8")
        version = repository_version.read_text(encoding="utf-8").strip()
        if "version: @VERSION@" in template and _SEMVER.fullmatch(version):
            return version

    raise RuntimeError("PIXIU_PROVIDER_VERSION_INVALID")


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


def http_api_supported(version: str) -> bool:
    match = _SEMVER.fullmatch(version)
    if not match:
        return False
    major, minor, _patch = (int(part) for part in match.groups())
    return (major, minor) == EXPECTED_HTTP_API
