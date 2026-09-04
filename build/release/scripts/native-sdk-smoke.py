#!/usr/bin/env python3
"""Strict Kylin SDK API smoke test that emits only sanitized evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


PRODUCT_PYTHON = Path("/usr/lib/pixiu/venv/bin/python")


def ensure_product_interpreter() -> None:
    """Run installed-release probes with the product's locked dependencies."""
    if not PRODUCT_PYTHON.is_file():
        return
    if Path(sys.executable).resolve() == PRODUCT_PYTHON.resolve():
        return
    os.execv(
        str(PRODUCT_PYTHON),
        [str(PRODUCT_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]],
    )


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


def validate_base_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("native evidence endpoint must be an HTTP loopback URL")
    return base_url.rstrip("/")


def command_output(command: list[str]) -> str:
    try:
        return subprocess.check_output(
            command, text=True, stderr=subprocess.STDOUT
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"required command failed: {command[0]}") from exc


def package_version(package: str) -> str:
    version = command_output(["dpkg-query", "-W", "-f=${Version}", package])
    if not version:
        raise RuntimeError(f"installed package version is empty: {package}")
    return version


def collect_installed_components() -> dict:
    runtime_path = shutil.which("kylin-agent-runtime") or shutil.which("hermes")
    host_path = shutil.which("kylin-agent")
    if not host_path:
        raise RuntimeError("openKylin Agent desktop host is not available")
    if not runtime_path:
        raise RuntimeError("openKylin Agent runtime is not available")
    runtime_output = command_output([runtime_path, "--version"])
    versions = re.findall(r"(?<![0-9])0\.9\.[0-9]+(?![0-9])", runtime_output)
    if len(versions) != 1:
        raise RuntimeError("Agent runtime must report exactly one 0.9.x version")
    packages = {
        package: package_version(package)
        for package in (
            "pixiu",
            "libkylin-coreai-embedding",
            "libkysdk-vector-engine-client",
        )
    }
    return {
        "architecture": command_output(["dpkg", "--print-architecture"]),
        "packages": packages,
        "agent_runtime": {
            "command": Path(runtime_path).name,
            "version": versions[0],
        },
        "agent_host": {"command": Path(host_path).name, "available": True},
    }


def validate_release_identity(manifest: dict, installed: dict, version: dict) -> dict:
    product = manifest.get("product", {})
    build = manifest.get("build", {})
    if (
        product.get("name") != "pixiu"
        or build.get("kysdk") != "ON"
        or build.get("install_strict") is not True
        or build.get("profile") != "kylin-v11-native-x86_64"
        or build.get("source_tree_clean") is not True
    ):
        raise RuntimeError("installed release is not a strict native PIXIU package")
    if installed.get("architecture") != build.get("architecture"):
        raise RuntimeError("installed architecture does not match release manifest")
    if installed.get("packages", {}).get("pixiu") != product.get("debian_version"):
        raise RuntimeError("installed PIXIU package version does not match release manifest")
    if version.get("product_version") != product.get("version"):
        raise RuntimeError("running backend version does not match release manifest")
    return {
        "product_version": product["version"],
        "debian_version": product["debian_version"],
        "git_commit": build["git_commit"],
        "architecture": build["architecture"],
        "profile": build["profile"],
        "kysdk": build["kysdk"],
        "install_strict": build["install_strict"],
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_candidate_package(
    deb: Path,
    installed_manifest: Path,
    manifest: dict,
    expected_commit: str,
) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise RuntimeError("expected release commit must be a full lowercase SHA-1")
    checksum_path = Path(f"{deb}.sha256")
    if not deb.is_file() or not checksum_path.is_file():
        raise RuntimeError("candidate package and checksum must both exist")
    checksum_fields = checksum_path.read_text(encoding="utf-8").split()
    actual_sha = file_sha256(deb)
    if (
        len(checksum_fields) != 2
        or checksum_fields[0] != actual_sha
        or Path(checksum_fields[1]).name != deb.name
    ):
        raise RuntimeError("candidate package checksum does not match")

    package = command_output(["dpkg-deb", "-f", str(deb), "Package"])
    debian_version = command_output(["dpkg-deb", "-f", str(deb), "Version"])
    architecture = command_output(["dpkg-deb", "-f", str(deb), "Architecture"])
    if package != "pixiu":
        raise RuntimeError("candidate Debian package identity is not pixiu")
    if manifest.get("build", {}).get("git_commit") != expected_commit:
        raise RuntimeError("candidate manifest commit does not match workflow commit")
    if debian_version != manifest.get("product", {}).get("debian_version"):
        raise RuntimeError("candidate package version does not match manifest")
    if architecture != manifest.get("build", {}).get("architecture"):
        raise RuntimeError("candidate package architecture does not match manifest")

    with tempfile.TemporaryDirectory() as directory:
        subprocess.run(
            ["dpkg-deb", "-x", str(deb), directory],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        embedded = Path(directory) / "usr/share/pixiu/release-manifest.json"
        if not embedded.is_file() or embedded.read_bytes() != installed_manifest.read_bytes():
            raise RuntimeError("candidate and installed release manifests differ")
    return {
        "filename": deb.name,
        "size": deb.stat().st_size,
        "sha256": actual_sha,
        "checksum_filename": checksum_path.name,
    }


def validate_runtime_reports(
    capabilities: dict, version: dict, health: dict, manifest: dict
) -> None:
    platform = capabilities.get("platform", {})
    embedding = capabilities.get("embedding", {})
    vector_store = capabilities.get("vector_store", {})
    for runtime in (embedding, vector_store):
        if not (
            runtime.get("configured") == "kylin"
            and runtime.get("runtime") == "kylin"
            and runtime.get("compliant") is True
        ):
            raise RuntimeError("strict Kylin SDK capability fields are inconsistent")
    if not (
        capabilities.get("contest_ready") is True
        and platform.get("family") == "kylin"
        and platform.get("version_major") == "11"
        and platform.get("v11") is True
    ):
        raise RuntimeError("Kylin V11 capability fields are inconsistent")

    product = manifest.get("product", {})
    interfaces = manifest.get("interfaces", {})
    expected_version = {
        "product_version": product.get("version"),
        "component": "pixiu-memory-backend",
        "api_version": interfaces.get("http_api"),
        "agent_memory_api": interfaces.get("agent_memory_api"),
        "schema_version": interfaces.get("database_schema"),
    }
    if any(version.get(key) != value for key, value in expected_version.items()):
        raise RuntimeError("version endpoint does not match release manifest")
    if not (
        health.get("status") == "ready"
        and health.get("database") == "ok"
        and health.get("product_version") == product.get("version")
        and health.get("component") == "pixiu-memory-backend"
        and health.get("schema_version") == interfaces.get("database_schema")
    ):
        raise RuntimeError("health endpoint does not match release manifest")


def prioritize_installed_root(installed_root: Path = Path("/usr/lib/pixiu")) -> None:
    installed_path = str(installed_root)
    while installed_path in sys.path:
        sys.path.remove(installed_path)
    sys.path.insert(0, installed_path)


def run_direct_sdk_lifecycle(
    *, embedder_factory=None, client_factory=None
) -> dict[str, str]:
    if embedder_factory is None or client_factory is None:
        prioritize_installed_root()
        from backend.engine.kylin.embedding import KylinTextEmbedding
        from backend.engine.kylin.vector import VectorEngineClient

        embedder_factory = embedder_factory or KylinTextEmbedding
        client_factory = client_factory or VectorEngineClient

    marker = f"PIXIU-NATIVE-SDK-{time.time_ns()}"
    collection = f"pixiu_acceptance_{time.time_ns()}"
    vector_id = time.time_ns() % (2**62)
    vector = list(embedder_factory().embed(marker))
    if not vector:
        raise RuntimeError("Kylin Embedding SDK returned an empty vector")
    # The vector daemon isolates loaded database state by application id.
    # Reusing the product id here would switch the live backend's SDK session
    # to this temporary database and invalidate its active collection.
    client = client_factory(app_id="pixiu-native-acceptance")
    database_dir = Path(tempfile.mkdtemp(prefix="pixiu-vector-acceptance-"))
    database_path = database_dir / "acceptance.db"
    create_attempted = False
    failure: Exception | None = None
    cleanup_failures: list[Exception] = []
    try:
        client.load_db_file(str(database_path))
        if client.has_collection(collection):
            raise RuntimeError("isolated acceptance collection already exists")
        create_attempted = True
        client.create_collection(collection, len(vector), False, True)
        client.load_collection(collection)
        if client.upsert(collection, [vector], [vector_id]) != 1:
            raise RuntimeError("Vector Engine direct upsert did not affect one row")
        matches: list[dict] = []
        for _ in range(30):
            matches = client.search(collection, vector, 1)
            if matches and int(matches[0].get("id", -1)) == vector_id:
                break
            time.sleep(0.2)
        if not matches or int(matches[0].get("id", -1)) != vector_id:
            raise RuntimeError("Vector Engine direct search did not return the probe")
        deleted_count = client.delete(collection, [vector_id])
        if deleted_count != 1:
            raise RuntimeError("Vector Engine direct delete did not affect one row")
        remaining: list[dict] = []
        for _ in range(30):
            remaining = client.search(collection, vector, 1)
            if not any(int(row.get("id", -1)) == vector_id for row in remaining):
                break
            time.sleep(0.2)
        if any(int(row.get("id", -1)) == vector_id for row in remaining):
            raise RuntimeError("Vector Engine direct delete left the probe searchable")
    except Exception as exc:
        failure = exc
    finally:
        if create_attempted:
            try:
                if client.has_collection(collection):
                    client.drop_collection(collection)
                if client.has_collection(collection):
                    raise RuntimeError("acceptance collection cleanup was not confirmed")
            except Exception as exc:
                cleanup_failures.append(exc)
        try:
            client.disconnect()
        except Exception as exc:
            cleanup_failures.append(exc)
        try:
            shutil.rmtree(database_dir)
        except Exception as exc:
            cleanup_failures.append(exc)
    if failure is not None and cleanup_failures:
        raise RuntimeError(
            f"direct SDK lifecycle failed and cleanup also failed: {cleanup_failures[0]}"
        ) from failure
    if failure is not None:
        raise failure
    if cleanup_failures:
        raise cleanup_failures[0]
    return {
        "embedding": "passed",
        "database_load": "passed",
        "collection_create": "passed",
        "collection_load": "passed",
        "vector_upsert": "passed",
        "vector_search": "passed",
        "vector_delete": "passed",
        "deleted_vector_hidden": "passed",
        "collection_drop": "passed",
        "disconnect": "passed",
    }


def run_memory_lifecycle(base_url: str) -> tuple[dict, dict]:
    marker = f"PIXIU-NATIVE-{time.time_ns()}"
    written: dict = {}
    queried: dict = {}
    deleted = False
    failure: Exception | None = None
    cleanup_failure: Exception | None = None
    try:
        written = request_json(
            f"{base_url}/memory/write",
            payload={
                "source_type": "MANUAL_CONFIG",
                "raw": {"title": marker, "body": {"text": marker}},
                "scope": "user:acceptance",
            },
        )
        if written.get("status") != "accepted" or not written.get("evidence_id"):
            raise RuntimeError("strict SDK memory write did not complete")

        queried = request_json(
            f"{base_url}/memory/query",
            payload={"text": marker, "context_hint": {"top_k": 1}},
        )
        knowledge_id = queried.get("source_knowledge")
        if not knowledge_id:
            raise RuntimeError("strict SDK retrieval did not find the written memory")

        preview = request_json(
            f"{base_url}/forget",
            payload={"command": f"forget {marker}", "confirm": False},
        )
        target_ids = {target.get("id") for target in preview.get("targets", [])}
        if knowledge_id not in target_ids:
            raise RuntimeError("forget preview did not resolve the retrieved knowledge")
        forgotten = request_json(
            f"{base_url}/forget",
            payload={"command": f"forget {marker}", "confirm": True},
        )
        if (
            forgotten.get("status") != "forgotten"
            or knowledge_id not in forgotten.get("forgotten_ids", [])
        ):
            raise RuntimeError("strict SDK-backed memory delete did not complete")
        deleted = True
        after_delete = request_json(
            f"{base_url}/memory/query",
            payload={"text": marker, "context_hint": {"top_k": 1}},
        )
        if after_delete.get("source_knowledge") == knowledge_id:
            raise RuntimeError("forgotten memory remained retrievable")
    except Exception as exc:
        failure = exc
    finally:
        if not deleted:
            try:
                cleanup = request_json(
                    f"{base_url}/forget",
                    payload={"command": f"forget {marker}", "confirm": True},
                )
                if cleanup.get("status") != "forgotten":
                    raise RuntimeError("memory cleanup did not report forgotten")
            except Exception as exc:
                cleanup_failure = exc
    if failure is not None and cleanup_failure is not None:
        raise RuntimeError(
            f"memory lifecycle failed and cleanup also failed: {cleanup_failure}"
        ) from failure
    if failure is not None:
        raise failure
    if cleanup_failure is not None:
        raise cleanup_failure
    return written, queried


def validate_evidence(evidence: dict) -> None:
    release = evidence.get("release")
    candidate = evidence.get("candidate_package")
    installed = evidence.get("installed")
    agent_host = evidence.get("agent_host")
    agent_runtime = evidence.get("agent_runtime")
    version = evidence.get("version")
    health = evidence.get("health")
    capabilities = evidence.get("capabilities")
    direct_sdk = evidence.get("direct_sdk")
    checks = evidence.get("checks")
    operation_ids = evidence.get("operation_ids")
    sections = (
        release, candidate, installed, agent_host, agent_runtime, version,
        health, capabilities, direct_sdk, checks, operation_ids,
    )
    if not all(isinstance(section, dict) for section in sections):
        raise RuntimeError("native evidence is missing required sections")
    platform = capabilities.get("platform")
    embedding = capabilities.get("embedding")
    vector_store = capabilities.get("vector_store")
    packages = installed.get("packages")
    required_direct = {
        "embedding", "database_load", "collection_create", "collection_load",
        "vector_upsert", "vector_search", "vector_delete",
        "deleted_vector_hidden", "collection_drop", "disconnect",
    }
    required_checks = {
        "contest_ready", "memory_write", "vector_search", "vector_delete",
        "deleted_memory_hidden",
    }
    if not (
        evidence.get("evidence_schema") == 1
        and evidence.get("evidence_class") == "kylin-v11-native-sdk-product-lifecycle"
        and evidence.get("real_device_evidence") is True
        and evidence.get("status") == "pass"
        and re.fullmatch(r"[0-9a-f]{40}", str(release.get("git_commit", "")))
        and release.get("profile") == "kylin-v11-native-x86_64"
        and release.get("architecture") == "amd64"
        and release.get("kysdk") == "ON"
        and release.get("install_strict") is True
        and re.fullmatch(r"[0-9a-f]{64}", str(candidate.get("sha256", "")))
        and isinstance(candidate.get("size"), int) and candidate["size"] > 0
        and isinstance(candidate.get("filename"), str) and candidate["filename"].endswith("_amd64.deb")
        and installed.get("architecture") == "amd64"
        and isinstance(packages, dict)
        and packages.get("pixiu") == release.get("debian_version")
        and all(isinstance(packages.get(name), str) and packages[name] for name in (
            "libkylin-coreai-embedding", "libkysdk-vector-engine-client"
        ))
        and agent_host.get("available") is True
        and re.fullmatch(r"0\.9\.[0-9]+", str(agent_runtime.get("version", "")))
        and version.get("product_version") == release.get("product_version")
        and health.get("status") == "ready"
        and health.get("database") == "ok"
        and isinstance(platform, dict)
        and platform.get("family") == "kylin"
        and platform.get("version_major") == "11"
        and platform.get("v11") is True
        and capabilities.get("contest_ready") is True
        and all(
            isinstance(runtime, dict)
            and runtime.get("configured") == "kylin"
            and runtime.get("runtime") == "kylin"
            and runtime.get("compliant") is True
            for runtime in (embedding, vector_store)
        )
        and set(direct_sdk) == required_direct
        and all(direct_sdk[name] == "passed" for name in required_direct)
        and set(checks) == required_checks
        and all(checks[name] == "passed" for name in required_checks)
        and re.fullmatch(r"evd_[A-Za-z0-9_-]+", str(operation_ids.get("evidence_id", "")))
        and re.fullmatch(r"knw_[A-Za-z0-9_-]+", str(operation_ids.get("knowledge_id", "")))
    ):
        raise RuntimeError("native evidence does not pass the strict public contract")


def main() -> int:
    ensure_product_interpreter()
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--deb", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument(
        "--release-manifest",
        type=Path,
        default=Path("/usr/share/pixiu/release-manifest.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base_url = validate_base_url(args.base_url)
    output = args.output.resolve()
    release_manifest = args.release_manifest.resolve()
    protected = {
        args.deb.resolve(),
        Path(f"{args.deb.resolve()}.sha256"),
        release_manifest,
    }
    if output in protected:
        raise RuntimeError("evidence output must not overwrite package inputs")

    capabilities = wait_for_capabilities(base_url)
    version = request_json(f"{base_url}/version")
    health = request_json(f"{base_url}/health")
    manifest = json.loads(release_manifest.read_text(encoding="utf-8"))
    installed = collect_installed_components()
    release = validate_release_identity(manifest, installed, version)
    validate_runtime_reports(capabilities, version, health, manifest)
    candidate = verify_candidate_package(
        args.deb.resolve(), release_manifest, manifest, args.expected_commit
    )
    direct_sdk = run_direct_sdk_lifecycle()
    written, queried = run_memory_lifecycle(base_url)

    evidence = {
        "evidence_schema": 1,
        "evidence_class": "kylin-v11-native-sdk-product-lifecycle",
        "real_device_evidence": True,
        "status": "pass",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "release": release,
        "candidate_package": candidate,
        "installed": {
            "architecture": installed["architecture"],
            "packages": installed["packages"],
        },
        "agent_host": installed["agent_host"],
        "agent_runtime": installed["agent_runtime"],
        "version": version,
        "health": health,
        "capabilities": capabilities,
        "direct_sdk": direct_sdk,
        "checks": {
            "contest_ready": "passed",
            "memory_write": "passed",
            "vector_search": "passed",
            "vector_delete": "passed",
            "deleted_memory_hidden": "passed",
        },
        "operation_ids": {
            "evidence_id": written["evidence_id"],
            "knowledge_id": queried["source_knowledge"],
        },
    }
    validate_evidence(evidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=output.parent, delete=False
    ) as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(output)
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
