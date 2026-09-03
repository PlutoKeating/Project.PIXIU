"""Post-install component health verification tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.foundation.api.install_health import InstallHealthError, verify_install


def _manifest(path: Path, version: str = "0.1.7") -> Path:
    path.write_text(f"name: pixiu\nversion: {version}\n", encoding="utf-8")
    return path


def test_verify_install_accepts_matching_ready_components(tmp_path):
    responses = {
        "/version": {
            "product_version": "0.1.7",
            "component": "pixiu-memory-backend",
            "agent_memory_api": 1,
            "schema_version": 12,
        },
        "/health": {
            "status": "ready",
            "product_version": "0.1.7",
            "component": "pixiu-memory-backend",
            "database": "ok",
            "schema_version": 12,
        },
    }

    result = verify_install(
        "0.1.7",
        _manifest(tmp_path / "plugin.yaml"),
        fetch_json=lambda path: responses[path],
        attempts=1,
    )

    assert result == {"product_version": "0.1.7", "schema_version": 12}


def test_verify_install_retries_transient_unready_backend(tmp_path):
    calls = 0

    def fetch(path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("service starting")
        if path == "/version":
            return {
                "product_version": "0.1.7",
                "component": "pixiu-memory-backend",
                "agent_memory_api": 1,
                "schema_version": 12,
            }
        return {
            "status": "ready",
            "product_version": "0.1.7",
            "component": "pixiu-memory-backend",
            "database": "ok",
            "schema_version": 12,
        }

    verify_install(
        "0.1.7",
        _manifest(tmp_path / "plugin.yaml"),
        fetch_json=fetch,
        attempts=2,
        retry_delay=0,
    )

    assert calls == 3


@pytest.mark.parametrize(
    ("version_overrides", "health_overrides", "provider_version", "error"),
    [
        ({"product_version": "0.1.6"}, {}, "0.1.7", "BACKEND_VERSION_MISMATCH"),
        ({"agent_memory_api": 2}, {}, "0.1.7", "AGENT_MEMORY_API_MISMATCH"),
        ({}, {"status": "starting"}, "0.1.7", "BACKEND_NOT_READY"),
        ({}, {"schema_version": 11}, "0.1.7", "SCHEMA_VERSION_MISMATCH"),
        ({}, {}, "0.1.6", "PROVIDER_VERSION_MISMATCH"),
    ],
)
def test_verify_install_rejects_mixed_or_unready_components(
    tmp_path,
    version_overrides,
    health_overrides,
    provider_version,
    error,
):
    version = {
        "product_version": "0.1.7",
        "component": "pixiu-memory-backend",
        "agent_memory_api": 1,
        "schema_version": 12,
        **version_overrides,
    }
    health = {
        "status": "ready",
        "product_version": "0.1.7",
        "component": "pixiu-memory-backend",
        "database": "ok",
        "schema_version": 12,
        **health_overrides,
    }

    with pytest.raises(InstallHealthError, match=error):
        verify_install(
            "0.1.7",
            _manifest(tmp_path / "plugin.yaml", provider_version),
            fetch_json=lambda path: version if path == "/version" else health,
            attempts=1,
        )
