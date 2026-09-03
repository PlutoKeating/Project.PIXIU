#!/usr/bin/env python3
"""Capture and validate sanitized three-device PIXIU topology/scenario evidence.

Each node runs ``capture`` locally against the loopback API after the strict
native SDK smoke test.  ``validate`` combines exactly three node manifests.
The topology report proves release identity and full-mesh readiness.  The
concurrency commands additionally prove one real-device scenario through nine
checkpoints.  Every report deliberately remains ``final_device_evidence=false``
until all required scenarios are implemented and collected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


SCHEMA_VERSION = 1
NODE_EVIDENCE_CLASS = "kylin-v11-sync-node"
CLUSTER_EVIDENCE_CLASS = "kylin-v11-three-device-topology"
CONCURRENCY_EVIDENCE_CLASS = "kylin-v11-concurrent-update-checkpoint"
CONCURRENCY_REPORT_CLASS = "kylin-v11-concurrent-update-scenario"
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{7,63}")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
DEVICE_ID_PATTERN = re.compile(r"dev_[A-Za-z0-9_-]{8,128}")
MAX_CAPTURE_SKEW_SECONDS = 300


class EvidenceError(RuntimeError):
    """Raised when evidence does not satisfy the public acceptance contract."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError("evidence input is not readable JSON") from exc
    if not isinstance(value, dict):
        raise EvidenceError("evidence input must be a JSON object")
    return value


def _write_json(path: Path, value: dict[str, Any], *, overwrite: bool) -> None:
    path = path.resolve()
    if path.exists() and not overwrite:
        raise EvidenceError("evidence output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise EvidenceError("evidence input is not readable") from exc
    return digest.hexdigest()


def _digest(run_id: str, kind: str, value: str) -> str:
    return hashlib.sha256(f"{run_id}\0{kind}\0{value}".encode("utf-8")).hexdigest()


def _utc_now() -> tuple[str, int]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ"), int(now.timestamp())


def _validate_timestamp(text: object, epoch: object) -> None:
    if not isinstance(text, str) or not isinstance(epoch, int) or isinstance(epoch, bool):
        raise EvidenceError("node manifest capture time is invalid")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise EvidenceError("node manifest capture time is invalid") from exc
    if int(parsed.timestamp()) != epoch:
        raise EvidenceError("node manifest capture timestamps disagree")


def _optional_nonnegative_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise EvidenceError(f"sync {field} is invalid")
    return value


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
        raise EvidenceError("node evidence endpoint must be an HTTP loopback URL")
    return base_url.rstrip("/")


def request_json(
    url: str, *, method: str = "GET", payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.load(response)
    except Exception as exc:
        raise EvidenceError("node evidence endpoint request failed") from exc
    if not isinstance(value, dict):
        raise EvidenceError("node evidence endpoint returned a non-object")
    return value


def _require_topology(value: dict[str, Any]) -> dict[str, Any]:
    topology = value.get("topology")
    release = value.get("release")
    if not (
        value.get("evidence_schema") == SCHEMA_VERSION
        and value.get("evidence_class") == CLUSTER_EVIDENCE_CLASS
        and value.get("real_device_evidence") is True
        and value.get("final_device_evidence") is False
        and value.get("status") == "pass"
        and isinstance(value.get("run_id"), str)
        and RUN_ID_PATTERN.fullmatch(value["run_id"])
        and isinstance(topology, dict)
        and topology.get("node_count") == 3
        and topology.get("trust_edges") == 3
        and topology.get("full_mesh") is True
        and topology.get("all_nodes_online") is True
        and topology.get("all_nodes_quiescent") is True
        and isinstance(topology.get("member_identity_digests"), list)
        and len(topology["member_identity_digests"]) == 3
        and all(
            isinstance(identity, str) and SHA256_PATTERN.fullmatch(identity)
            for identity in topology["member_identity_digests"]
        )
        and len(set(topology["member_identity_digests"])) == 3
        and isinstance(value.get("source_node_manifest_sha256"), list)
        and len(value["source_node_manifest_sha256"]) == 3
        and all(
            isinstance(digest, str) and SHA256_PATTERN.fullmatch(digest)
            for digest in value["source_node_manifest_sha256"]
        )
        and len(set(value["source_node_manifest_sha256"])) == 3
        and isinstance(release, dict)
    ):
        raise EvidenceError("topology evidence is not a passing three-device report")
    return value


def _require_native_evidence(native: dict[str, Any]) -> dict[str, str]:
    release = native.get("release")
    candidate = native.get("candidate_package")
    capabilities = native.get("capabilities")
    checks = native.get("checks")
    agent_host = native.get("agent_host")
    agent_runtime = native.get("agent_runtime")
    if not all(
        isinstance(value, dict)
        for value in (release, candidate, capabilities, checks, agent_host, agent_runtime)
    ):
        raise EvidenceError("native evidence is missing required sections")
    assert isinstance(release, dict)
    assert isinstance(candidate, dict)
    assert isinstance(capabilities, dict)
    assert isinstance(checks, dict)
    assert isinstance(agent_host, dict)
    assert isinstance(agent_runtime, dict)
    platform = capabilities.get("platform")
    embedding = capabilities.get("embedding")
    vector_store = capabilities.get("vector_store")
    if not all(isinstance(value, dict) for value in (platform, embedding, vector_store)):
        raise EvidenceError("native evidence capability sections are incomplete")
    assert isinstance(platform, dict)
    assert isinstance(embedding, dict)
    assert isinstance(vector_store, dict)

    commit = release.get("git_commit")
    package_sha256 = candidate.get("sha256")
    runtime_version = agent_runtime.get("version")
    required_checks = {
        "contest_ready",
        "memory_write",
        "vector_search",
        "vector_delete",
        "deleted_memory_hidden",
    }
    strict_runtimes = (embedding, vector_store)
    if not (
        native.get("evidence_schema") == 1
        and isinstance(commit, str)
        and COMMIT_PATTERN.fullmatch(commit)
        and isinstance(package_sha256, str)
        and SHA256_PATTERN.fullmatch(package_sha256)
        and release.get("profile") == "kylin-v11-native-x86_64"
        and release.get("kysdk") == "ON"
        and release.get("install_strict") is True
        and platform.get("family") == "kylin"
        and platform.get("version_major") == "11"
        and platform.get("v11") is True
        and capabilities.get("contest_ready") is True
        and all(
            runtime.get("configured") == "kylin"
            and runtime.get("runtime") == "kylin"
            and runtime.get("compliant") is True
            for runtime in strict_runtimes
        )
        and required_checks.issubset(checks)
        and all(checks[key] == "passed" for key in required_checks)
        and agent_host.get("available") is True
        and isinstance(runtime_version, str)
        and re.fullmatch(r"0\.9\.[0-9]+", runtime_version)
    ):
        raise EvidenceError("native evidence is not a passing strict Kylin V11 run")
    product_version = release.get("product_version")
    debian_version = release.get("debian_version")
    architecture = release.get("architecture")
    if not all(
        isinstance(value, str) and value
        for value in (product_version, debian_version, architecture)
    ) or architecture != "amd64":
        raise EvidenceError("native evidence release identity is incomplete")
    return {
        "product_version": product_version,
        "debian_version": debian_version,
        "git_commit": commit,
        "architecture": architecture,
        "profile": release["profile"],
        "candidate_package_sha256": package_sha256,
        "agent_runtime_version": runtime_version,
    }


def capture_node(
    *, run_id: str, native_path: Path, base_url: str, captured_at: tuple[str, int] | None = None
) -> dict[str, Any]:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise EvidenceError("run id must be 8-64 safe characters")
    native = _read_json(native_path)
    release = _require_native_evidence(native)
    base_url = validate_base_url(base_url)
    peers_payload = request_json(f"{base_url}/sync/peers")
    status = request_json(f"{base_url}/sync/status")
    peers = peers_payload.get("peers")
    if not isinstance(peers, list) or len(peers) != 3:
        raise EvidenceError("node must report exactly three topology members")
    if not isinstance(status.get("domain"), str) or not status["domain"].startswith("shared:"):
        raise EvidenceError("node must report a shared sync domain")

    normalized: list[dict[str, Any]] = []
    raw_ids: set[str] = set()
    self_ids: list[str] = []
    for peer in peers:
        if not isinstance(peer, dict):
            raise EvidenceError("sync peer entry must be an object")
        peer_id = peer.get("id")
        if not isinstance(peer_id, str) or not DEVICE_ID_PATTERN.fullmatch(peer_id):
            raise EvidenceError("sync peer identity is invalid")
        if peer_id in raw_ids:
            raise EvidenceError("sync peer identities must be unique")
        raw_ids.add(peer_id)
        is_self = peer.get("is_self") is True
        if is_self:
            self_ids.append(peer_id)
        pending = peer.get("pending_ops")
        if not isinstance(pending, int) or isinstance(pending, bool) or pending < 0:
            raise EvidenceError("sync peer pending count is invalid")
        normalized.append(
            {
                "identity_digest": _digest(run_id, "device", peer_id),
                "is_self": is_self,
                "status": peer.get("status"),
                "pending_ops": pending,
            }
        )
    if len(self_ids) != 1:
        raise EvidenceError("node topology must contain exactly one self identity")
    if not (
        status.get("peers_total") == 3
        and status.get("peers_online") == 3
        and status.get("pending_outgoing_ops") == 0
        and status.get("enabled") is True
        and status.get("paused") is False
        and all(peer["status"] == "ONLINE" for peer in normalized)
        and all(peer["pending_ops"] == 0 for peer in normalized)
    ):
        raise EvidenceError("node topology is not online, enabled, and quiescent")
    generated_at_utc, generated_at_epoch = captured_at or _utc_now()
    _validate_timestamp(generated_at_utc, generated_at_epoch)
    last_anti_entropy_ts = _optional_nonnegative_int(
        status.get("last_anti_entropy_ts"), "anti-entropy timestamp"
    )
    total_ops_synced = _optional_nonnegative_int(
        status.get("total_ops_synced"), "synchronized operation count"
    )
    self_digest = _digest(run_id, "device", self_ids[0])
    return {
        "evidence_schema": SCHEMA_VERSION,
        "evidence_class": NODE_EVIDENCE_CLASS,
        "real_device_evidence": True,
        "final_device_evidence": False,
        "run_id": run_id,
        "captured_at_utc": generated_at_utc,
        "captured_at_epoch": generated_at_epoch,
        "release": release,
        "native_evidence_sha256": _sha256_file(native_path),
        "node": {
            "identity_digest": self_digest,
            "domain_digest": _digest(run_id, "domain", status["domain"]),
            "members": sorted(normalized, key=lambda item: item["identity_digest"]),
            "peers_total": status["peers_total"],
            "peers_online": status["peers_online"],
            "pending_outgoing_ops": status["pending_outgoing_ops"],
            "enabled": status["enabled"],
            "paused": status["paused"],
            "last_anti_entropy_ts": last_anti_entropy_ts,
            "total_ops_synced": total_ops_synced,
        },
    }


def _validate_node_manifest(value: dict[str, Any]) -> None:
    node = value.get("node")
    release = value.get("release")
    if not (
        value.get("evidence_schema") == SCHEMA_VERSION
        and value.get("evidence_class") == NODE_EVIDENCE_CLASS
        and value.get("real_device_evidence") is True
        and value.get("final_device_evidence") is False
        and isinstance(value.get("run_id"), str)
        and RUN_ID_PATTERN.fullmatch(value["run_id"])
        and isinstance(value.get("captured_at_epoch"), int)
        and not isinstance(value.get("captured_at_epoch"), bool)
        and isinstance(value.get("native_evidence_sha256"), str)
        and SHA256_PATTERN.fullmatch(value["native_evidence_sha256"])
        and isinstance(node, dict)
        and isinstance(release, dict)
    ):
        raise EvidenceError("node manifest header is invalid")
    assert isinstance(node, dict)
    assert isinstance(release, dict)
    _validate_timestamp(value.get("captured_at_utc"), value["captured_at_epoch"])
    identity = node.get("identity_digest")
    domain = node.get("domain_digest")
    members = node.get("members")
    if not (
        isinstance(identity, str)
        and SHA256_PATTERN.fullmatch(identity)
        and isinstance(domain, str)
        and SHA256_PATTERN.fullmatch(domain)
        and isinstance(members, list)
        and len(members) == 3
        and node.get("peers_total") == 3
        and node.get("peers_online") == 3
        and node.get("pending_outgoing_ops") == 0
        and node.get("enabled") is True
        and node.get("paused") is False
    ):
        raise EvidenceError("node manifest topology is invalid")
    member_ids: set[str] = set()
    self_count = 0
    for member in members:
        if not isinstance(member, dict):
            raise EvidenceError("node manifest member is invalid")
        member_id = member.get("identity_digest")
        if not isinstance(member_id, str) or not SHA256_PATTERN.fullmatch(member_id):
            raise EvidenceError("node manifest member identity is invalid")
        member_ids.add(member_id)
        self_count += member.get("is_self") is True
        if member.get("status") != "ONLINE" or member.get("pending_ops") != 0:
            raise EvidenceError("node manifest member is not online and quiescent")
    if len(member_ids) != 3 or self_count != 1 or identity not in member_ids:
        raise EvidenceError("node manifest membership is inconsistent")
    required_release = {
        "product_version",
        "debian_version",
        "git_commit",
        "architecture",
        "profile",
        "candidate_package_sha256",
        "agent_runtime_version",
    }
    if not (
        set(release) == required_release
        and isinstance(release.get("product_version"), str)
        and bool(release["product_version"])
        and isinstance(release.get("debian_version"), str)
        and bool(release["debian_version"])
        and isinstance(release.get("git_commit"), str)
        and COMMIT_PATTERN.fullmatch(release["git_commit"])
        and release.get("architecture") == "amd64"
        and release.get("profile") == "kylin-v11-native-x86_64"
        and isinstance(release.get("candidate_package_sha256"), str)
        and SHA256_PATTERN.fullmatch(release["candidate_package_sha256"])
        and isinstance(release.get("agent_runtime_version"), str)
        and re.fullmatch(r"0\.9\.[0-9]+", release["agent_runtime_version"])
    ):
        raise EvidenceError("node manifest release identity is invalid")


def validate_cluster(node_paths: list[Path]) -> dict[str, Any]:
    if len(node_paths) != 3 or len({path.resolve() for path in node_paths}) != 3:
        raise EvidenceError("exactly three distinct node manifests are required")
    manifests = [_read_json(path) for path in node_paths]
    for manifest in manifests:
        _validate_node_manifest(manifest)
    run_ids = {manifest["run_id"] for manifest in manifests}
    releases = {
        json.dumps(manifest["release"], sort_keys=True, separators=(",", ":"))
        for manifest in manifests
    }
    domains = {manifest["node"]["domain_digest"] for manifest in manifests}
    identities = {manifest["node"]["identity_digest"] for manifest in manifests}
    native_evidence_hashes = {
        manifest["native_evidence_sha256"] for manifest in manifests
    }
    if len(run_ids) != 1:
        raise EvidenceError("node manifests belong to different runs")
    if len(releases) != 1:
        raise EvidenceError("node manifests do not share one release identity")
    if len(domains) != 1:
        raise EvidenceError("node manifests do not share one sync domain")
    if len(identities) != 3:
        raise EvidenceError("node manifests do not represent three distinct devices")
    if len(native_evidence_hashes) != 3:
        raise EvidenceError("node manifests must bind three independent native runs")
    for manifest in manifests:
        member_ids = {
            member["identity_digest"] for member in manifest["node"]["members"]
        }
        if member_ids != identities:
            raise EvidenceError("node manifests do not prove a full-mesh topology")
    capture_times = [manifest["captured_at_epoch"] for manifest in manifests]
    skew = max(capture_times) - min(capture_times)
    if skew > MAX_CAPTURE_SKEW_SECONDS:
        raise EvidenceError("node manifests exceed the allowed capture time window")
    generated_at_utc, generated_at_epoch = _utc_now()
    release = manifests[0]["release"]
    return {
        "evidence_schema": SCHEMA_VERSION,
        "evidence_class": CLUSTER_EVIDENCE_CLASS,
        "real_device_evidence": True,
        "final_device_evidence": False,
        "status": "pass",
        "run_id": manifests[0]["run_id"],
        "generated_at_utc": generated_at_utc,
        "generated_at_epoch": generated_at_epoch,
        "release": release,
        "source_node_manifest_sha256": sorted(
            _sha256_file(path) for path in node_paths
        ),
        "topology": {
            "node_count": 3,
            "trust_edges": 3,
            "member_identity_digests": sorted(identities),
            "domain_digest": next(iter(domains)),
            "capture_skew_seconds": skew,
            "all_nodes_online": True,
            "all_nodes_quiescent": True,
            "full_mesh": True,
        },
        "checks": {
            "strict_kylin_v11_native_evidence": "passed",
            "same_release_identity": "passed",
            "three_distinct_devices": "passed",
            "three_independent_native_runs": "passed",
            "same_sync_domain": "passed",
            "full_mesh_membership": "passed",
            "all_online_and_quiescent": "passed",
            "bounded_capture_skew": "passed",
        },
        "remaining_required_scenarios": [
            "offline-write-and-reconnect",
            "concurrent-update-and-conflict-resolution",
            "tombstone-propagation-and-no-resurrection",
            "private-scope-non-propagation",
            "final-logical-view-convergence",
        ],
    }


def capture_concurrency_checkpoint(
    *,
    topology_path: Path,
    node_path: Path,
    base_url: str,
    checkpoint: str,
    role: str,
    query: str,
    scope: str,
    captured_at: tuple[str, int] | None = None,
) -> dict[str, Any]:
    """Capture one privacy-preserving checkpoint of the concurrent-update run."""
    if checkpoint not in {"baseline", "diverged", "converged"}:
        raise EvidenceError("concurrency checkpoint is invalid")
    allowed_roles = {
        "baseline": {"baseline"},
        "diverged": {"branch-a", "branch-b", "observer"},
        "converged": {"converged"},
    }
    if role not in allowed_roles[checkpoint]:
        raise EvidenceError("concurrency checkpoint role is invalid")
    query = query.strip()
    if not query or len(query) > 512:
        raise EvidenceError("scenario query must contain 1-512 characters")
    if not re.fullmatch(r"shared:[A-Za-z0-9._-]+", scope):
        raise EvidenceError("concurrency scenario requires a shared scope")

    topology = _require_topology(_read_json(topology_path))
    node_manifest = _read_json(node_path)
    _validate_node_manifest(node_manifest)
    identity = node_manifest["node"]["identity_digest"]
    members = topology["topology"]["member_identity_digests"]
    if not (
        node_manifest["run_id"] == topology["run_id"]
        and node_manifest["release"] == topology["release"]
        and identity in members
    ):
        raise EvidenceError("node checkpoint does not belong to the topology report")

    base_url = validate_base_url(base_url)
    context = request_json(
        f"{base_url}/agent/context",
        method="POST",
        payload={
            "query": query,
            "scope": scope,
            "session_id": f"evidence-{topology['run_id']}",
            "turn_id": f"concurrency-{checkpoint}",
            "top_k": 1,
            "max_chars": 4096,
        },
    )
    status = request_json(f"{base_url}/sync/status")
    conflicts_payload = request_json(f"{base_url}/conflicts")
    items = context.get("items")
    conflicts = conflicts_payload.get("conflicts")
    if not isinstance(items, list) or len(items) != 1:
        raise EvidenceError("concurrency checkpoint must resolve exactly one knowledge item")
    if not isinstance(conflicts, list):
        raise EvidenceError("conflict endpoint returned an invalid response")
    item = items[0]
    if not isinstance(item, dict):
        raise EvidenceError("concurrency checkpoint item is invalid")
    knowledge_id = item.get("knowledge_id")
    version = item.get("version")
    evidence_ids = item.get("evidence_ids")
    if not (
        isinstance(knowledge_id, str)
        and re.fullmatch(r"knw_[A-Za-z0-9_-]{8,128}", knowledge_id)
        and isinstance(version, int)
        and not isinstance(version, bool)
        and version >= 1
        and item.get("scope") == scope
        and isinstance(item.get("title"), str)
        and isinstance(evidence_ids, list)
        and all(
            isinstance(evidence_id, str)
            and re.fullmatch(r"evd_[A-Za-z0-9_-]{8,128}", evidence_id)
            for evidence_id in evidence_ids
        )
        and item.get("conflict_status") in {"none", "resolved", "manual"}
        and isinstance(context.get("context"), str)
    ):
        raise EvidenceError("concurrency checkpoint knowledge metadata is invalid")
    if not (
        status.get("enabled") is True
        and isinstance(status.get("paused"), bool)
        and isinstance(status.get("peers_online"), int)
        and not isinstance(status.get("peers_online"), bool)
        and status["peers_online"] == 3
        and isinstance(status.get("pending_outgoing_ops"), int)
        and not isinstance(status.get("pending_outgoing_ops"), bool)
        and status["pending_outgoing_ops"] >= 0
    ):
        raise EvidenceError("concurrency checkpoint sync status is invalid")
    if checkpoint in {"baseline", "converged"} and not (
        status["paused"] is False
        and status["peers_online"] == 3
        and status["pending_outgoing_ops"] == 0
    ):
        raise EvidenceError("stable concurrency checkpoint is not online and quiescent")
    if checkpoint == "diverged" and role.startswith("branch-") and not status["paused"]:
        raise EvidenceError("divergent update branches must be captured while paused")
    if checkpoint == "diverged" and role == "observer" and status["paused"]:
        raise EvidenceError("divergent observer must remain unpaused")

    normalized_item = {
        "knowledge_id": knowledge_id,
        "version": version,
        "title": item.get("title"),
        "scope": item.get("scope"),
        "evidence_ids": sorted(evidence_ids),
        "conflict_status": item.get("conflict_status"),
        "context": context["context"],
    }
    matching_conflicts = [
        record
        for record in conflicts
        if isinstance(record, dict) and record.get("target_knowledge") == knowledge_id
    ]
    generated_at_utc, generated_at_epoch = captured_at or _utc_now()
    _validate_timestamp(generated_at_utc, generated_at_epoch)
    run_id = topology["run_id"]
    return {
        "evidence_schema": SCHEMA_VERSION,
        "evidence_class": CONCURRENCY_EVIDENCE_CLASS,
        "real_device_evidence": True,
        "final_device_evidence": False,
        "run_id": run_id,
        "captured_at_utc": generated_at_utc,
        "captured_at_epoch": generated_at_epoch,
        "release": topology["release"],
        "topology_evidence_sha256": _sha256_file(topology_path),
        "node_manifest_sha256": _sha256_file(node_path),
        "node_identity_digest": identity,
        "scenario": "concurrent-update-and-conflict-resolution",
        "checkpoint": checkpoint,
        "role": role,
        "query_digest": _digest(run_id, "concurrency-query", query),
        "scope_digest": _digest(run_id, "concurrency-scope", scope),
        "knowledge_digest": _digest(run_id, "knowledge", knowledge_id),
        "logical_view_digest": _digest(
            run_id,
            "concurrency-view",
            json.dumps(normalized_item, ensure_ascii=False, sort_keys=True),
        ),
        "version": version,
        "matching_conflict_count": len(matching_conflicts),
        "sync": {
            "enabled": status["enabled"],
            "paused": status["paused"],
            "peers_online": status["peers_online"],
            "pending_outgoing_ops": status["pending_outgoing_ops"],
        },
    }


def _validate_concurrency_checkpoint(value: dict[str, Any]) -> None:
    sync = value.get("sync")
    release = value.get("release")
    checkpoint = value.get("checkpoint")
    role = value.get("role")
    allowed_roles = {
        "baseline": {"baseline"},
        "diverged": {"branch-a", "branch-b", "observer"},
        "converged": {"converged"},
    }
    if not (
        value.get("evidence_schema") == SCHEMA_VERSION
        and value.get("evidence_class") == CONCURRENCY_EVIDENCE_CLASS
        and value.get("real_device_evidence") is True
        and value.get("final_device_evidence") is False
        and value.get("scenario") == "concurrent-update-and-conflict-resolution"
        and checkpoint in allowed_roles
        and role in allowed_roles[checkpoint]
        and isinstance(value.get("run_id"), str)
        and RUN_ID_PATTERN.fullmatch(value["run_id"])
        and isinstance(value.get("captured_at_epoch"), int)
        and not isinstance(value.get("captured_at_epoch"), bool)
        and isinstance(release, dict)
        and isinstance(sync, dict)
        and isinstance(value.get("version"), int)
        and not isinstance(value.get("version"), bool)
        and value["version"] >= 1
        and isinstance(value.get("matching_conflict_count"), int)
        and value["matching_conflict_count"] >= 0
        and all(
            isinstance(value.get(field), str) and SHA256_PATTERN.fullmatch(value[field])
            for field in (
                "topology_evidence_sha256",
                "node_manifest_sha256",
                "node_identity_digest",
                "query_digest",
                "scope_digest",
                "knowledge_digest",
                "logical_view_digest",
            )
        )
        and sync.get("enabled") is True
        and isinstance(sync.get("paused"), bool)
        and isinstance(sync.get("peers_online"), int)
        and not isinstance(sync.get("peers_online"), bool)
        and sync["peers_online"] == 3
        and isinstance(sync.get("pending_outgoing_ops"), int)
        and not isinstance(sync.get("pending_outgoing_ops"), bool)
        and sync["pending_outgoing_ops"] >= 0
    ):
        raise EvidenceError("concurrency checkpoint manifest is invalid")
    _validate_timestamp(value.get("captured_at_utc"), value["captured_at_epoch"])


def validate_concurrency_scenario(
    *, topology_path: Path, checkpoint_paths: list[Path]
) -> dict[str, Any]:
    """Validate three real devices across baseline, divergence, and convergence."""
    topology = _require_topology(_read_json(topology_path))
    if len(checkpoint_paths) != 9 or len({path.resolve() for path in checkpoint_paths}) != 9:
        raise EvidenceError("exactly nine distinct concurrency checkpoints are required")
    values = [_read_json(path) for path in checkpoint_paths]
    for value in values:
        _validate_concurrency_checkpoint(value)
    topology_hash = _sha256_file(topology_path)
    identities = set(topology["topology"]["member_identity_digests"])
    if any(
        value["run_id"] != topology["run_id"]
        or value["release"] != topology["release"]
        or value["topology_evidence_sha256"] != topology_hash
        for value in values
    ):
        raise EvidenceError("concurrency checkpoints do not bind the topology release")
    if {value["node_identity_digest"] for value in values} != identities:
        raise EvidenceError("concurrency checkpoints do not cover the topology devices")
    if {
        value["node_manifest_sha256"] for value in values
    } != set(topology["source_node_manifest_sha256"]):
        raise EvidenceError("concurrency checkpoints do not bind the topology nodes")
    for identity in identities:
        if len(
            {
                value["node_manifest_sha256"]
                for value in values
                if value["node_identity_digest"] == identity
            }
        ) != 1:
            raise EvidenceError("one device used inconsistent node manifests")
    if len({value["query_digest"] for value in values}) != 1:
        raise EvidenceError("concurrency checkpoints did not use one scenario query")
    if len({value["scope_digest"] for value in values}) != 1:
        raise EvidenceError("concurrency checkpoints did not use one shared scope")
    if len({value["knowledge_digest"] for value in values}) != 1:
        raise EvidenceError("concurrency checkpoints do not track one knowledge entity")

    grouped = {
        phase: [value for value in values if value["checkpoint"] == phase]
        for phase in ("baseline", "diverged", "converged")
    }
    if any(
        len(group) != 3
        or {value["node_identity_digest"] for value in group} != identities
        or max(value["captured_at_epoch"] for value in group)
        - min(value["captured_at_epoch"] for value in group)
        > MAX_CAPTURE_SKEW_SECONDS
        for group in grouped.values()
    ):
        raise EvidenceError(
            "each concurrency checkpoint must cover all three devices within the time window"
        )
    baseline = grouped["baseline"]
    diverged = grouped["diverged"]
    converged = grouped["converged"]
    if len({value["logical_view_digest"] for value in baseline}) != 1 or len(
        {value["version"] for value in baseline}
    ) != 1:
        raise EvidenceError("baseline logical views are not converged")
    baseline_digest = baseline[0]["logical_view_digest"]
    baseline_version = baseline[0]["version"]
    roles = {value["role"]: value for value in diverged}
    if set(roles) != {"branch-a", "branch-b", "observer"}:
        raise EvidenceError("divergent checkpoint roles are incomplete")
    branches = [roles["branch-a"], roles["branch-b"]]
    if not (
        all(branch["sync"]["paused"] is True for branch in branches)
        and roles["observer"]["sync"]["paused"] is False
        and all(branch["version"] == baseline_version + 1 for branch in branches)
        and roles["observer"]["version"] == baseline_version
        and len({branch["logical_view_digest"] for branch in branches}) == 2
        and all(branch["logical_view_digest"] != baseline_digest for branch in branches)
        and roles["observer"]["logical_view_digest"] == baseline_digest
    ):
        raise EvidenceError("divergent checkpoint does not prove two offline branches")
    if not (
        len({value["logical_view_digest"] for value in converged}) == 1
        and len({value["version"] for value in converged}) == 1
        and converged[0]["version"] >= baseline_version + 1
        and converged[0]["logical_view_digest"] != baseline_digest
        and all(
            value["sync"]["paused"] is False
            and value["sync"]["peers_online"] == 3
            and value["sync"]["pending_outgoing_ops"] == 0
            for value in converged
        )
    ):
        raise EvidenceError("final concurrent-update views are not converged")
    by_identity = {
        identity: sorted(
            (value for value in values if value["node_identity_digest"] == identity),
            key=lambda value: {"baseline": 0, "diverged": 1, "converged": 2}[
                value["checkpoint"]
            ],
        )
        for identity in identities
    }
    if any(
        [value["captured_at_epoch"] for value in series]
        != sorted(value["captured_at_epoch"] for value in series)
        for series in by_identity.values()
    ):
        raise EvidenceError("concurrency checkpoint times are out of order")

    generated_at_utc, generated_at_epoch = _utc_now()
    return {
        "evidence_schema": SCHEMA_VERSION,
        "evidence_class": CONCURRENCY_REPORT_CLASS,
        "real_device_evidence": True,
        "final_device_evidence": False,
        "status": "pass",
        "run_id": topology["run_id"],
        "generated_at_utc": generated_at_utc,
        "generated_at_epoch": generated_at_epoch,
        "release": topology["release"],
        "topology_evidence_sha256": topology_hash,
        "source_checkpoint_sha256": sorted(
            _sha256_file(path) for path in checkpoint_paths
        ),
        "scenario": "concurrent-update-and-conflict-resolution",
        "checks": {
            "same_shared_knowledge_entity": "passed",
            "baseline_three_device_convergence": "passed",
            "two_distinct_paused_update_branches": "passed",
            "uninvolved_observer_preserved_baseline": "passed",
            "three_device_reconnect_convergence": "passed",
            "online_quiescent_final_state": "passed",
        },
        "remaining_required_scenarios": [
            "offline-write-and-reconnect",
            "tombstone-propagation-and-no-resurrection",
            "private-scope-non-propagation",
            "final-logical-view-convergence",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture = subparsers.add_parser("capture")
    capture.add_argument("--run-id", required=True)
    capture.add_argument("--native-evidence", required=True, type=Path)
    capture.add_argument("--base-url", default="http://127.0.0.1:8765")
    capture.add_argument("--output", required=True, type=Path)
    capture.add_argument("--overwrite", action="store_true")
    validate = subparsers.add_parser("validate")
    validate.add_argument("--node", required=True, action="append", type=Path)
    validate.add_argument("--output", required=True, type=Path)
    validate.add_argument("--overwrite", action="store_true")
    checkpoint = subparsers.add_parser("capture-concurrency")
    checkpoint.add_argument("--topology", required=True, type=Path)
    checkpoint.add_argument("--node", required=True, type=Path)
    checkpoint.add_argument("--base-url", default="http://127.0.0.1:8765")
    checkpoint.add_argument("--scope", required=True)
    checkpoint.add_argument(
        "--checkpoint", required=True, choices=("baseline", "diverged", "converged")
    )
    checkpoint.add_argument(
        "--role",
        required=True,
        choices=("baseline", "branch-a", "branch-b", "observer", "converged"),
    )
    checkpoint.add_argument("--query-file", required=True, type=Path)
    checkpoint.add_argument("--output", required=True, type=Path)
    checkpoint.add_argument("--overwrite", action="store_true")
    scenario = subparsers.add_parser("validate-concurrency")
    scenario.add_argument("--topology", required=True, type=Path)
    scenario.add_argument("--checkpoint", required=True, action="append", type=Path)
    scenario.add_argument("--output", required=True, type=Path)
    scenario.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "capture":
            output = args.output.resolve()
            if output == args.native_evidence.resolve():
                raise EvidenceError("node output must not overwrite native evidence")
            report = capture_node(
                run_id=args.run_id,
                native_path=args.native_evidence.resolve(),
                base_url=args.base_url,
            )
        elif args.command == "validate":
            output = args.output.resolve()
            if output in {path.resolve() for path in args.node}:
                raise EvidenceError("cluster output must not overwrite node evidence")
            report = validate_cluster(args.node)
        elif args.command == "capture-concurrency":
            output = args.output.resolve()
            inputs = {args.topology.resolve(), args.node.resolve(), args.query_file.resolve()}
            if output in inputs:
                raise EvidenceError("checkpoint output must not overwrite an input")
            try:
                query = args.query_file.read_text(encoding="utf-8")
            except OSError as exc:
                raise EvidenceError("scenario query file is not readable") from exc
            report = capture_concurrency_checkpoint(
                topology_path=args.topology.resolve(),
                node_path=args.node.resolve(),
                base_url=args.base_url,
                checkpoint=args.checkpoint,
                role=args.role,
                query=query,
                scope=args.scope,
            )
        else:
            output = args.output.resolve()
            inputs = {args.topology.resolve(), *(path.resolve() for path in args.checkpoint)}
            if output in inputs:
                raise EvidenceError("scenario output must not overwrite an input")
            report = validate_concurrency_scenario(
                topology_path=args.topology.resolve(),
                checkpoint_paths=args.checkpoint,
            )
        _write_json(output, report, overwrite=args.overwrite)
    except EvidenceError as exc:
        print(f"three-device evidence error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
