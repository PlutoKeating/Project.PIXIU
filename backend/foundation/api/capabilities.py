"""Sanitized runtime capability reporting for contest acceptance evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from backend.engine.kylin.embedding import TextEmbedder

from ..core.vector_store import VectorStore


def _read_os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    """Read public OS identity fields without returning machine-specific data."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    values: dict[str, str] = {}
    for line in lines:
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def platform_capability(os_release: Mapping[str, str] | None = None) -> dict:
    """Return only acceptance-relevant platform identity, never host details."""
    values = dict(os_release) if os_release is not None else _read_os_release()
    identity = " ".join(
        values.get(key, "") for key in ("ID", "ID_LIKE", "NAME")
    ).casefold()
    version = values.get("VERSION_ID", "")
    normalized_version = version.lstrip("vV")
    major = normalized_version.split(".", 1)[0] if normalized_version else "unknown"
    family = "kylin" if "kylin" in identity else "other"
    return {
        "family": family,
        "version_major": major,
        "v11": family == "kylin" and major == "11",
    }


def capability_report(
    *,
    embedding_configured: str,
    embedder: TextEmbedder,
    vector_store_configured: str,
    vector_store: VectorStore,
    os_release: Mapping[str, str] | None = None,
) -> dict:
    """Build an evidence-safe report from actual instantiated implementations."""
    platform = platform_capability(os_release)
    embedding_runtime = embedder.runtime
    vector_runtime = vector_store.runtime
    embedding_ok = embedding_runtime == "kylin"
    vector_ok = vector_runtime == "kylin"
    return {
        "platform": platform,
        "embedding": {
            "configured": embedding_configured,
            "runtime": embedding_runtime,
            "compliant": embedding_ok,
        },
        "vector_store": {
            "configured": vector_store_configured,
            "runtime": vector_runtime,
            "compliant": vector_ok,
        },
        "contest_ready": platform["v11"] and embedding_ok and vector_ok,
    }


__all__ = ["capability_report", "platform_capability"]
