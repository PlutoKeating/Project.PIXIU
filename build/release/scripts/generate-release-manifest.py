#!/usr/bin/env python3
"""Generate the auditable component manifest embedded in a PIXIU package."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


SEMVER = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


def read_match(path: Path, pattern: str, label: str) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise SystemExit(f"pixiu-manifest: cannot read {label}")
    return match.group(1)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True, stderr=subprocess.DEVNULL
    ).strip()


def source_pin(
    root: Path,
    relative_path: str,
    license_family: str,
    license_spdx: str | None,
    license_review_status: str = "confirmed",
) -> dict[str, object]:
    path = root / relative_path
    gitlink_commit = git(root, "rev-parse", f"HEAD:{relative_path}")
    checkout_commit = git(path, "rev-parse", "HEAD")
    checkout_dirty = bool(git(path, "status", "--porcelain"))
    if gitlink_commit != checkout_commit or checkout_dirty:
        raise SystemExit(
            "pixiu-manifest: submodule checkout does not match clean gitlink: "
            f"{relative_path}"
        )
    return {
        "source_commit": checkout_commit,
        "gitlink_commit": gitlink_commit,
        "source_ref": git(path, "describe", "--tags", "--always"),
        "source_tree_clean": True,
        "license": {
            "family": license_family,
            "spdx_expression": license_spdx,
            "review_status": license_review_status,
        },
    }


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"pixiu-manifest: {name} is required")
    return value


def utc_timestamp() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    instant = (
        datetime.fromtimestamp(int(epoch), tz=timezone.utc)
        if epoch is not None
        else datetime.now(tz=timezone.utc)
    )
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_manifest(root: Path) -> dict[str, object]:
    version = required_env("PIXIU_VERSION")
    revision = required_env("PIXIU_REVISION")
    architecture = required_env("PIXIU_ARCH")
    profile = required_env("PIXIU_PROFILE")
    kysdk = required_env("PIXIU_KYSDK")
    python_abi = required_env("PIXIU_PYTHON_VERSION")
    if not SEMVER.fullmatch(version):
        raise SystemExit("pixiu-manifest: PIXIU_VERSION must be MAJOR.MINOR.PATCH")
    if not re.fullmatch(r"[0-9A-Za-z.+~]+", revision):
        raise SystemExit("pixiu-manifest: invalid PIXIU_REVISION")
    if kysdk not in {"ON", "OFF"}:
        raise SystemExit("pixiu-manifest: PIXIU_KYSDK must be ON or OFF")

    cmake_version = read_match(
        root / "frontend/CMakeLists.txt",
        r"project\(pixiu-frontend VERSION ([0-9]+\.[0-9]+\.[0-9]+)",
        "frontend version",
    )
    canonical_version = (root / "VERSION").read_text(encoding="utf-8").strip()
    provider_version = read_match(
        root / "integrations/kylin_agent/pixiu/plugin.yaml",
        r"^version:\s*([^\s]+)\s*$",
        "provider version",
    )
    versions = {version, canonical_version, cmake_version, provider_version}
    if len(versions) != 1:
        raise SystemExit(
            "pixiu-manifest: product version mismatch: "
            f"build={version}, canonical={canonical_version}, "
            f"frontend={cmake_version}, provider={provider_version}"
        )

    api_file = root / "backend/foundation/api/version.py"
    schema_file = root / "backend/foundation/storage/schema.py"
    agent_runtime = source_pin(
        root, "third_party/kylin-agent-runtime", "MIT License", "MIT"
    )
    agent_runtime.update(
        {
            "supported": "0.9.x",
            "declared_versions": {
                "package_metadata": read_match(
                    root / "third_party/kylin-agent-runtime/pyproject.toml",
                    r'^version\s*=\s*"([^"]+)"',
                    "agent runtime package version",
                ),
                "version_file": (
                    root / "third_party/kylin-agent-runtime/version"
                ).read_text(encoding="utf-8").strip(),
            },
        }
    )
    kylin_agent = source_pin(
        root,
        "third_party/kylin-agent",
        "GNU Affero General Public License v3",
        None,
        "pending-only-or-later-review",
    )
    kylin_agent["declared_version"] = read_match(
        root / "third_party/kylin-agent/CMakeLists.txt",
        r"project\(KylinAgent VERSION ([^ )]+)",
        "kylin-agent version",
    )

    return {
        "manifest_schema": 1,
        "product": {
            "name": "pixiu",
            "version": version,
            "revision": revision,
            "debian_version": f"{version}-{revision}",
        },
        "build": {
            "git_commit": git(root, "rev-parse", "HEAD"),
            "source_tree_clean": not bool(git(root, "status", "--porcelain")),
            "built_at_utc": utc_timestamp(),
            "architecture": architecture,
            "profile": profile,
            "kysdk": kysdk,
            "python_abi": python_abi,
        },
        "interfaces": {
            "http_api": read_match(
                api_file, r'^API_VERSION\s*=\s*"([^"]+)"', "HTTP API version"
            ),
            "agent_memory_api": int(
                read_match(
                    api_file,
                    r"^AGENT_MEMORY_API_VERSION\s*=\s*([0-9]+)",
                    "Agent Memory API version",
                )
            ),
            "database_schema": int(
                read_match(
                    schema_file,
                    r"^SCHEMA_VERSION\s*=\s*([0-9]+)",
                    "database schema version",
                )
            ),
        },
        "provider": {"name": "pixiu", "version": provider_version},
        "host_compatibility": {
            "kylin_agent": kylin_agent,
            "agent_runtime": agent_runtime,
        },
        "sdk_sources": {
            "embedding": {
                **source_pin(
                    root,
                    "third_party/kylin-coreai-embedding",
                    "GNU General Public License v3 or later",
                    "GPL-3.0-or-later",
                ),
                "runtime_package": "libkylin-coreai-embedding",
                "required_in_profile": kysdk == "ON",
            },
            "vector_engine": {
                **source_pin(
                    root,
                    "third_party/libkysdk-vector-engine-client",
                    "Apache License 2.0",
                    "Apache-2.0",
                ),
                "runtime_package": "libkysdk-vector-engine-client",
                "required_in_profile": kysdk == "ON",
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    manifest = build_manifest(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=output.parent, delete=False
    ) as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.chmod(0o644)
    temporary.replace(output)


if __name__ == "__main__":
    main()
