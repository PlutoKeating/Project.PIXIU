#!/usr/bin/env python3
"""Capture and validate sanitized three-device PIXIU topology/scenario evidence.

Each node runs ``capture`` locally against the loopback API after the strict
native SDK smoke test.  ``validate`` combines exactly three node manifests.
The topology report proves release identity and full-mesh readiness.  Scenario
commands cover concurrent updates, offline reconnect, and private-scope
non-propagation plus tombstone no-resurrection through privacy-preserving
checkpoints.  Every report remains
``final_device_evidence=false`` until all required scenarios are implemented and
collected.
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
OFFLINE_EVIDENCE_CLASS = "kylin-v11-offline-reconnect-checkpoint"
OFFLINE_REPORT_CLASS = "kylin-v11-offline-reconnect-scenario"
PRIVACY_EVIDENCE_CLASS = "kylin-v11-private-scope-checkpoint"
PRIVACY_REPORT_CLASS = "kylin-v11-private-scope-scenario"
TOMBSTONE_EVIDENCE_CLASS = "kylin-v11-tombstone-checkpoint"
TOMBSTONE_REPORT_CLASS = "kylin-v11-tombstone-no-resurrection-scenario"
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


def _capture_memory_checkpoint(
    *,
    topology_path: Path,
    node_path: Path,
    base_url: str,
    checkpoint: str,
    role: str,
    query: str,
    scope: str,
    evidence_class: str,
    scenario: str,
    digest_namespace: str,
    allowed_roles: dict[str, set[str]],
    paused_roles: set[str],
    captured_at: tuple[str, int] | None = None,
) -> dict[str, Any]:
    """Capture one privacy-preserving shared-memory scenario checkpoint."""
    if checkpoint not in {"baseline", "diverged", "converged"}:
        raise EvidenceError("memory scenario checkpoint is invalid")
    if role not in allowed_roles[checkpoint]:
        raise EvidenceError("memory scenario checkpoint role is invalid")
    query = query.strip()
    if not query or len(query) > 512:
        raise EvidenceError("scenario query must contain 1-512 characters")
    if not re.fullmatch(r"shared:[A-Za-z0-9._-]+", scope):
        raise EvidenceError("memory scenario requires a shared scope")

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
            "turn_id": f"{digest_namespace}-{checkpoint}",
            "top_k": 1,
            "max_chars": 4096,
        },
    )
    status = request_json(f"{base_url}/sync/status")
    conflicts_payload = request_json(f"{base_url}/conflicts")
    items = context.get("items")
    conflicts = conflicts_payload.get("conflicts")
    if not isinstance(items, list) or len(items) != 1:
        raise EvidenceError("memory checkpoint must resolve exactly one knowledge item")
    if not isinstance(conflicts, list):
        raise EvidenceError("conflict endpoint returned an invalid response")
    item = items[0]
    if not isinstance(item, dict):
        raise EvidenceError("memory checkpoint item is invalid")
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
        raise EvidenceError("memory checkpoint knowledge metadata is invalid")
    if not (
        status.get("enabled") is True
        and isinstance(status.get("paused"), bool)
        and isinstance(status.get("peers_online"), int)
        and not isinstance(status.get("peers_online"), bool)
        and 0 <= status["peers_online"] <= 3
        and isinstance(status.get("pending_outgoing_ops"), int)
        and not isinstance(status.get("pending_outgoing_ops"), bool)
        and status["pending_outgoing_ops"] >= 0
    ):
        raise EvidenceError("memory checkpoint sync status is invalid")
    if checkpoint in {"baseline", "converged"} and not (
        status["paused"] is False
        and status["peers_online"] == 3
        and status["pending_outgoing_ops"] == 0
    ):
        raise EvidenceError("stable memory checkpoint is not online and quiescent")
    if checkpoint == "diverged" and status["paused"] != (role in paused_roles):
        raise EvidenceError("divergent checkpoint pause state does not match its role")

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
        "evidence_class": evidence_class,
        "real_device_evidence": True,
        "final_device_evidence": False,
        "run_id": run_id,
        "captured_at_utc": generated_at_utc,
        "captured_at_epoch": generated_at_epoch,
        "release": topology["release"],
        "topology_evidence_sha256": _sha256_file(topology_path),
        "node_manifest_sha256": _sha256_file(node_path),
        "node_identity_digest": identity,
        "scenario": scenario,
        "checkpoint": checkpoint,
        "role": role,
        "query_digest": _digest(run_id, f"{digest_namespace}-query", query),
        "scope_digest": _digest(run_id, f"{digest_namespace}-scope", scope),
        "knowledge_digest": _digest(run_id, "knowledge", knowledge_id),
        "logical_view_digest": _digest(
            run_id,
            f"{digest_namespace}-view",
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
    """Capture one checkpoint of a concurrent two-branch update."""
    return _capture_memory_checkpoint(
        topology_path=topology_path,
        node_path=node_path,
        base_url=base_url,
        checkpoint=checkpoint,
        role=role,
        query=query,
        scope=scope,
        evidence_class=CONCURRENCY_EVIDENCE_CLASS,
        scenario="concurrent-update-and-conflict-resolution",
        digest_namespace="concurrency",
        allowed_roles={
            "baseline": {"baseline"},
            "diverged": {"branch-a", "branch-b", "observer"},
            "converged": {"converged"},
        },
        paused_roles={"branch-a", "branch-b"},
        captured_at=captured_at,
    )


def capture_offline_checkpoint(
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
    """Capture one checkpoint of an isolated-node reconnect scenario."""
    return _capture_memory_checkpoint(
        topology_path=topology_path,
        node_path=node_path,
        base_url=base_url,
        checkpoint=checkpoint,
        role=role,
        query=query,
        scope=scope,
        evidence_class=OFFLINE_EVIDENCE_CLASS,
        scenario="offline-write-and-reconnect",
        digest_namespace="offline-reconnect",
        allowed_roles={
            "baseline": {"baseline"},
            "diverged": {"isolated", "writer", "online-observer"},
            "converged": {"converged"},
        },
        paused_roles={"isolated"},
        captured_at=captured_at,
    )


def _validate_memory_checkpoint(
    value: dict[str, Any],
    *,
    evidence_class: str,
    scenario: str,
    allowed_roles: dict[str, set[str]],
) -> None:
    sync = value.get("sync")
    release = value.get("release")
    checkpoint = value.get("checkpoint")
    role = value.get("role")
    if not (
        value.get("evidence_schema") == SCHEMA_VERSION
        and value.get("evidence_class") == evidence_class
        and value.get("real_device_evidence") is True
        and value.get("final_device_evidence") is False
        and value.get("scenario") == scenario
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
        and 0 <= sync["peers_online"] <= 3
        and isinstance(sync.get("pending_outgoing_ops"), int)
        and not isinstance(sync.get("pending_outgoing_ops"), bool)
        and sync["pending_outgoing_ops"] >= 0
    ):
        raise EvidenceError("memory checkpoint manifest is invalid")
    _validate_timestamp(value.get("captured_at_utc"), value["captured_at_epoch"])
    if checkpoint in {"baseline", "converged"} and not (
        sync["paused"] is False
        and sync["peers_online"] == 3
        and sync["pending_outgoing_ops"] == 0
    ):
        raise EvidenceError("stable memory checkpoint is not online and quiescent")


def _validate_concurrency_checkpoint(value: dict[str, Any]) -> None:
    _validate_memory_checkpoint(
        value,
        evidence_class=CONCURRENCY_EVIDENCE_CLASS,
        scenario="concurrent-update-and-conflict-resolution",
        allowed_roles={
            "baseline": {"baseline"},
            "diverged": {"branch-a", "branch-b", "observer"},
            "converged": {"converged"},
        },
    )
    if value["sync"]["peers_online"] != 3:
        raise EvidenceError("concurrency checkpoint must keep three peers online")


def _validate_offline_checkpoint(value: dict[str, Any]) -> None:
    _validate_memory_checkpoint(
        value,
        evidence_class=OFFLINE_EVIDENCE_CLASS,
        scenario="offline-write-and-reconnect",
        allowed_roles={
            "baseline": {"baseline"},
            "diverged": {"isolated", "writer", "online-observer"},
            "converged": {"converged"},
        },
    )


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


def validate_offline_scenario(
    *, topology_path: Path, checkpoint_paths: list[Path]
) -> dict[str, Any]:
    """Validate one isolated node, online propagation, and reconnect catch-up."""
    topology = _require_topology(_read_json(topology_path))
    if len(checkpoint_paths) != 9 or len({path.resolve() for path in checkpoint_paths}) != 9:
        raise EvidenceError("exactly nine distinct offline checkpoints are required")
    values = [_read_json(path) for path in checkpoint_paths]
    for value in values:
        _validate_offline_checkpoint(value)
    topology_hash = _sha256_file(topology_path)
    identities = set(topology["topology"]["member_identity_digests"])
    if any(
        value["run_id"] != topology["run_id"]
        or value["release"] != topology["release"]
        or value["topology_evidence_sha256"] != topology_hash
        for value in values
    ):
        raise EvidenceError("offline checkpoints do not bind the topology release")
    if {value["node_identity_digest"] for value in values} != identities:
        raise EvidenceError("offline checkpoints do not cover the topology devices")
    if {
        value["node_manifest_sha256"] for value in values
    } != set(topology["source_node_manifest_sha256"]):
        raise EvidenceError("offline checkpoints do not bind the topology nodes")
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
        raise EvidenceError("offline checkpoints did not use one scenario query")
    if len({value["scope_digest"] for value in values}) != 1:
        raise EvidenceError("offline checkpoints did not use one shared scope")
    if len({value["knowledge_digest"] for value in values}) != 1:
        raise EvidenceError("offline checkpoints do not track one knowledge entity")

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
            "each offline checkpoint must cover all three devices within the time window"
        )
    baseline = grouped["baseline"]
    diverged = grouped["diverged"]
    converged = grouped["converged"]
    if len({value["logical_view_digest"] for value in baseline}) != 1 or len(
        {value["version"] for value in baseline}
    ) != 1:
        raise EvidenceError("offline baseline logical views are not converged")
    baseline_digest = baseline[0]["logical_view_digest"]
    baseline_version = baseline[0]["version"]
    roles = {value["role"]: value for value in diverged}
    if set(roles) != {"isolated", "writer", "online-observer"}:
        raise EvidenceError("offline checkpoint roles are incomplete")
    isolated = roles["isolated"]
    writer = roles["writer"]
    observer = roles["online-observer"]
    if not (
        isolated["sync"]["paused"] is True
        and isolated["sync"]["peers_online"] <= 2
        and isolated["version"] == baseline_version
        and isolated["logical_view_digest"] == baseline_digest
        and writer["sync"]["paused"] is False
        and observer["sync"]["paused"] is False
        and writer["sync"]["peers_online"] == 2
        and observer["sync"]["peers_online"] == 2
        and writer["sync"]["pending_outgoing_ops"] == 0
        and observer["sync"]["pending_outgoing_ops"] == 0
        and writer["version"] == baseline_version + 1
        and observer["version"] == baseline_version + 1
        and writer["logical_view_digest"] == observer["logical_view_digest"]
        and writer["logical_view_digest"] != baseline_digest
    ):
        raise EvidenceError(
            "offline divergence does not prove isolated baseline and online propagation"
        )
    final_digest = writer["logical_view_digest"]
    if not (
        len({value["logical_view_digest"] for value in converged}) == 1
        and converged[0]["logical_view_digest"] == final_digest
        and {value["version"] for value in converged} == {baseline_version + 1}
        and all(
            value["sync"]["paused"] is False
            and value["sync"]["peers_online"] == 3
            and value["sync"]["pending_outgoing_ops"] == 0
            for value in converged
        )
    ):
        raise EvidenceError("offline node did not catch up to the final logical view")
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
        raise EvidenceError("offline checkpoint times are out of order")

    generated_at_utc, generated_at_epoch = _utc_now()
    return {
        "evidence_schema": SCHEMA_VERSION,
        "evidence_class": OFFLINE_REPORT_CLASS,
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
        "scenario": "offline-write-and-reconnect",
        "checks": {
            "same_shared_knowledge_entity": "passed",
            "baseline_three_device_convergence": "passed",
            "one_node_isolated_with_baseline_preserved": "passed",
            "remaining_nodes_write_and_propagate": "passed",
            "isolated_node_reconnect_catch_up": "passed",
            "online_quiescent_final_state": "passed",
        },
        "remaining_required_scenarios": [
            "concurrent-update-and-conflict-resolution",
            "tombstone-propagation-and-no-resurrection",
            "private-scope-non-propagation",
            "final-logical-view-convergence",
        ],
    }


def capture_privacy_checkpoint(
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
    """Capture one private-scope non-propagation checkpoint."""
    allowed_roles = {
        "baseline": {"baseline"},
        "post-write": {"writer", "observer"},
    }
    if checkpoint not in allowed_roles or role not in allowed_roles[checkpoint]:
        raise EvidenceError("privacy checkpoint role is invalid")
    query = query.strip()
    if not query or len(query) > 512:
        raise EvidenceError("scenario query must contain 1-512 characters")
    if not re.fullmatch(r"user:[A-Za-z0-9._-]+", scope):
        raise EvidenceError("privacy scenario requires a private user scope")

    topology = _require_topology(_read_json(topology_path))
    node_manifest = _read_json(node_path)
    _validate_node_manifest(node_manifest)
    identity = node_manifest["node"]["identity_digest"]
    if not (
        node_manifest["run_id"] == topology["run_id"]
        and node_manifest["release"] == topology["release"]
        and identity in topology["topology"]["member_identity_digests"]
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
            "turn_id": f"private-scope-{checkpoint}",
            "top_k": 1,
            "max_chars": 4096,
        },
    )
    status = request_json(f"{base_url}/sync/status")
    items = context.get("items")
    expected_count = 1 if checkpoint == "post-write" and role == "writer" else 0
    if not isinstance(items, list) or len(items) != expected_count:
        raise EvidenceError("privacy checkpoint has an unexpected local result count")
    normalized_items: list[dict[str, Any]] = []
    for item in items:
        if not (
            isinstance(item, dict)
            and isinstance(item.get("knowledge_id"), str)
            and re.fullmatch(r"knw_[A-Za-z0-9_-]{8,128}", item["knowledge_id"])
            and isinstance(item.get("version"), int)
            and not isinstance(item.get("version"), bool)
            and item["version"] >= 1
            and item.get("scope") == scope
            and isinstance(item.get("title"), str)
            and isinstance(item.get("evidence_ids"), list)
            and all(
                isinstance(evidence_id, str)
                and re.fullmatch(r"evd_[A-Za-z0-9_-]{8,128}", evidence_id)
                for evidence_id in item["evidence_ids"]
            )
        ):
            raise EvidenceError("privacy checkpoint knowledge metadata is invalid")
        normalized_items.append(
            {
                "knowledge_id": item["knowledge_id"],
                "version": item["version"],
                "title": item["title"],
                "scope": item["scope"],
                "evidence_ids": sorted(item["evidence_ids"]),
            }
        )
    if not (
        status.get("enabled") is True
        and status.get("paused") is False
        and status.get("peers_online") == 3
        and status.get("pending_outgoing_ops") == 0
        and isinstance(status.get("total_ops_synced"), int)
        and not isinstance(status.get("total_ops_synced"), bool)
        and status["total_ops_synced"] >= 0
    ):
        raise EvidenceError("privacy checkpoint sync status is not online and quiescent")
    generated_at_utc, generated_at_epoch = captured_at or _utc_now()
    _validate_timestamp(generated_at_utc, generated_at_epoch)
    run_id = topology["run_id"]
    return {
        "evidence_schema": SCHEMA_VERSION,
        "evidence_class": PRIVACY_EVIDENCE_CLASS,
        "real_device_evidence": True,
        "final_device_evidence": False,
        "run_id": run_id,
        "captured_at_utc": generated_at_utc,
        "captured_at_epoch": generated_at_epoch,
        "release": topology["release"],
        "topology_evidence_sha256": _sha256_file(topology_path),
        "node_manifest_sha256": _sha256_file(node_path),
        "node_identity_digest": identity,
        "scenario": "private-scope-non-propagation",
        "checkpoint": checkpoint,
        "role": role,
        "query_digest": _digest(run_id, "private-scope-query", query),
        "scope_digest": _digest(run_id, "private-scope", scope),
        "local_result_count": len(normalized_items),
        "local_view_digest": _digest(
            run_id,
            "private-scope-view",
            json.dumps(normalized_items, ensure_ascii=False, sort_keys=True),
        ),
        "sync": {
            "enabled": True,
            "paused": False,
            "peers_online": 3,
            "pending_outgoing_ops": 0,
            "total_ops_synced": status["total_ops_synced"],
        },
    }


def _validate_privacy_checkpoint(value: dict[str, Any]) -> None:
    sync = value.get("sync")
    checkpoint = value.get("checkpoint")
    role = value.get("role")
    allowed_roles = {
        "baseline": {"baseline"},
        "post-write": {"writer", "observer"},
    }
    if not (
        value.get("evidence_schema") == SCHEMA_VERSION
        and value.get("evidence_class") == PRIVACY_EVIDENCE_CLASS
        and value.get("real_device_evidence") is True
        and value.get("final_device_evidence") is False
        and value.get("scenario") == "private-scope-non-propagation"
        and checkpoint in allowed_roles
        and role in allowed_roles[checkpoint]
        and isinstance(value.get("release"), dict)
        and isinstance(value.get("run_id"), str)
        and RUN_ID_PATTERN.fullmatch(value["run_id"])
        and isinstance(value.get("captured_at_epoch"), int)
        and not isinstance(value.get("captured_at_epoch"), bool)
        and isinstance(value.get("local_result_count"), int)
        and not isinstance(value.get("local_result_count"), bool)
        and value["local_result_count"] in {0, 1}
        and all(
            isinstance(value.get(field), str) and SHA256_PATTERN.fullmatch(value[field])
            for field in (
                "topology_evidence_sha256",
                "node_manifest_sha256",
                "node_identity_digest",
                "query_digest",
                "scope_digest",
                "local_view_digest",
            )
        )
        and isinstance(sync, dict)
        and sync.get("enabled") is True
        and sync.get("paused") is False
        and sync.get("peers_online") == 3
        and sync.get("pending_outgoing_ops") == 0
        and isinstance(sync.get("total_ops_synced"), int)
        and not isinstance(sync.get("total_ops_synced"), bool)
        and sync["total_ops_synced"] >= 0
    ):
        raise EvidenceError("privacy checkpoint manifest is invalid")
    _validate_timestamp(value.get("captured_at_utc"), value["captured_at_epoch"])


def validate_privacy_scenario(
    *, topology_path: Path, checkpoint_paths: list[Path]
) -> dict[str, Any]:
    """Validate private local visibility and zero synchronization activity."""
    topology = _require_topology(_read_json(topology_path))
    if len(checkpoint_paths) != 6 or len({path.resolve() for path in checkpoint_paths}) != 6:
        raise EvidenceError("exactly six distinct privacy checkpoints are required")
    values = [_read_json(path) for path in checkpoint_paths]
    for value in values:
        _validate_privacy_checkpoint(value)
    topology_hash = _sha256_file(topology_path)
    identities = set(topology["topology"]["member_identity_digests"])
    if any(
        value["run_id"] != topology["run_id"]
        or value["release"] != topology["release"]
        or value["topology_evidence_sha256"] != topology_hash
        for value in values
    ):
        raise EvidenceError("privacy checkpoints do not bind the topology release")
    if {value["node_identity_digest"] for value in values} != identities:
        raise EvidenceError("privacy checkpoints do not cover the topology devices")
    if {
        value["node_manifest_sha256"] for value in values
    } != set(topology["source_node_manifest_sha256"]):
        raise EvidenceError("privacy checkpoints do not bind the topology nodes")
    if len({value["query_digest"] for value in values}) != 1 or len(
        {value["scope_digest"] for value in values}
    ) != 1:
        raise EvidenceError("privacy checkpoints do not share one query and scope")

    grouped = {
        phase: [value for value in values if value["checkpoint"] == phase]
        for phase in ("baseline", "post-write")
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
            "each privacy checkpoint must cover all three devices within the time window"
        )
    baseline = grouped["baseline"]
    post_write = grouped["post-write"]
    if any(value["local_result_count"] != 0 for value in baseline) or len(
        {value["local_view_digest"] for value in baseline}
    ) != 1:
        raise EvidenceError("privacy baseline already contains the scenario memory")
    empty_view_digest = baseline[0]["local_view_digest"]
    roles = [value["role"] for value in post_write]
    if roles.count("writer") != 1 or roles.count("observer") != 2:
        raise EvidenceError("privacy post-write roles are incomplete")
    writer = next(value for value in post_write if value["role"] == "writer")
    observers = [value for value in post_write if value["role"] == "observer"]
    if writer["local_result_count"] != 1 or any(
        value["local_result_count"] != 0 for value in observers
    ) or writer["local_view_digest"] == empty_view_digest or any(
        value["local_view_digest"] != empty_view_digest for value in observers
    ):
        raise EvidenceError("private memory visibility escaped the writer device")
    by_identity = {
        identity: sorted(
            (value for value in values if value["node_identity_digest"] == identity),
            key=lambda value: 0 if value["checkpoint"] == "baseline" else 1,
        )
        for identity in identities
    }
    for series in by_identity.values():
        if len(series) != 2 or series[0]["captured_at_epoch"] > series[1]["captured_at_epoch"]:
            raise EvidenceError("privacy checkpoint times are out of order")
        if series[0]["node_manifest_sha256"] != series[1]["node_manifest_sha256"]:
            raise EvidenceError("one device used inconsistent node manifests")
        if series[0]["sync"]["total_ops_synced"] != series[1]["sync"]["total_ops_synced"]:
            raise EvidenceError("private write changed synchronization acknowledgements")

    generated_at_utc, generated_at_epoch = _utc_now()
    return {
        "evidence_schema": SCHEMA_VERSION,
        "evidence_class": PRIVACY_REPORT_CLASS,
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
        "scenario": "private-scope-non-propagation",
        "checks": {
            "clean_three_device_baseline": "passed",
            "private_memory_visible_on_writer_only": "passed",
            "private_memory_absent_on_two_observers": "passed",
            "zero_pending_sync_operations": "passed",
            "unchanged_sync_acknowledgements": "passed",
        },
        "remaining_required_scenarios": [
            "offline-write-and-reconnect",
            "concurrent-update-and-conflict-resolution",
            "tombstone-propagation-and-no-resurrection",
            "final-logical-view-convergence",
        ],
    }


def capture_tombstone_checkpoint(
    *,
    topology_path: Path,
    node_path: Path,
    base_url: str,
    checkpoint: str,
    role: str,
    query: str,
    scope: str,
    knowledge_id: str,
    captured_at: tuple[str, int] | None = None,
) -> dict[str, Any]:
    """Capture visible knowledge and payload-free CRDT deletion state."""
    allowed_roles = {
        "baseline": {"baseline"},
        "deleted": {"deleter", "online-observer", "isolated"},
        "reconnected": {"converged"},
        "stable": {"stable"},
    }
    if checkpoint not in allowed_roles or role not in allowed_roles[checkpoint]:
        raise EvidenceError("tombstone checkpoint role is invalid")
    query = query.strip()
    if not query or len(query) > 512:
        raise EvidenceError("scenario query must contain 1-512 characters")
    if not re.fullmatch(r"shared:[A-Za-z0-9._-]+", scope):
        raise EvidenceError("tombstone scenario requires a shared scope")
    if not re.fullmatch(r"knw_[A-Za-z0-9_-]{8,128}", knowledge_id):
        raise EvidenceError("tombstone scenario knowledge id is invalid")

    topology = _require_topology(_read_json(topology_path))
    node_manifest = _read_json(node_path)
    _validate_node_manifest(node_manifest)
    identity = node_manifest["node"]["identity_digest"]
    if not (
        node_manifest["run_id"] == topology["run_id"]
        and node_manifest["release"] == topology["release"]
        and identity in topology["topology"]["member_identity_digests"]
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
            "turn_id": f"tombstone-{checkpoint}",
            "top_k": 1,
            "max_chars": 4096,
        },
    )
    state = request_json(f"{base_url}/sync/state/knowledge/{knowledge_id}")
    status = request_json(f"{base_url}/sync/status")
    items = context.get("items")
    should_be_visible = checkpoint == "baseline" or (
        checkpoint == "deleted" and role == "isolated"
    )
    if not isinstance(items, list) or len(items) != int(should_be_visible):
        raise EvidenceError("tombstone checkpoint visibility does not match its role")
    if items:
        item = items[0]
        if not (
            isinstance(item, dict)
            and item.get("knowledge_id") == knowledge_id
            and item.get("scope") == scope
        ):
            raise EvidenceError("tombstone checkpoint resolved the wrong knowledge")
    operation_digest = state.get("operation_digest")
    if not (
        state.get("present") is True
        and isinstance(state.get("tombstone"), bool)
        and isinstance(state.get("clock_entries"), int)
        and not isinstance(state.get("clock_entries"), bool)
        and state["clock_entries"] >= 1
        and isinstance(state.get("clock_total"), int)
        and not isinstance(state.get("clock_total"), bool)
        and state["clock_total"] >= 1
        and isinstance(operation_digest, str)
        and SHA256_PATTERN.fullmatch(operation_digest)
        and isinstance(state.get("updated_at"), int)
        and not isinstance(state.get("updated_at"), bool)
        and state["updated_at"] >= 0
    ):
        raise EvidenceError("tombstone checkpoint CRDT state is invalid")
    expected_tombstone = not should_be_visible
    if state["tombstone"] is not expected_tombstone:
        raise EvidenceError("tombstone checkpoint state disagrees with visibility")
    if not (
        status.get("enabled") is True
        and isinstance(status.get("paused"), bool)
        and isinstance(status.get("peers_online"), int)
        and not isinstance(status.get("peers_online"), bool)
        and 0 <= status["peers_online"] <= 3
        and status.get("pending_outgoing_ops") == 0
    ):
        raise EvidenceError("tombstone checkpoint sync status is invalid")
    stable = checkpoint in {"baseline", "reconnected", "stable"}
    if stable and not (status["paused"] is False and status["peers_online"] == 3):
        raise EvidenceError("stable tombstone checkpoint is not fully online")
    if checkpoint == "deleted":
        if role == "isolated" and not (
            status["paused"] is True and status["peers_online"] <= 2
        ):
            raise EvidenceError("isolated tombstone node is not isolated")
        if role != "isolated" and not (
            status["paused"] is False and status["peers_online"] == 2
        ):
            raise EvidenceError("online tombstone nodes do not form a two-node view")

    generated_at_utc, generated_at_epoch = captured_at or _utc_now()
    _validate_timestamp(generated_at_utc, generated_at_epoch)
    run_id = topology["run_id"]
    state_summary = {
        "tombstone": state["tombstone"],
        "clock_entries": state["clock_entries"],
        "clock_total": state["clock_total"],
        "operation_digest": operation_digest,
    }
    return {
        "evidence_schema": SCHEMA_VERSION,
        "evidence_class": TOMBSTONE_EVIDENCE_CLASS,
        "real_device_evidence": True,
        "final_device_evidence": False,
        "run_id": run_id,
        "captured_at_utc": generated_at_utc,
        "captured_at_epoch": generated_at_epoch,
        "release": topology["release"],
        "topology_evidence_sha256": _sha256_file(topology_path),
        "node_manifest_sha256": _sha256_file(node_path),
        "node_identity_digest": identity,
        "scenario": "tombstone-propagation-and-no-resurrection",
        "checkpoint": checkpoint,
        "role": role,
        "query_digest": _digest(run_id, "tombstone-query", query),
        "scope_digest": _digest(run_id, "tombstone-scope", scope),
        "knowledge_digest": _digest(run_id, "knowledge", knowledge_id),
        "visible": should_be_visible,
        "tombstone": state["tombstone"],
        "clock_entries": state["clock_entries"],
        "clock_total": state["clock_total"],
        "state_digest": _digest(
            run_id,
            "tombstone-state",
            json.dumps(state_summary, sort_keys=True),
        ),
        "sync": {
            "enabled": True,
            "paused": status["paused"],
            "peers_online": status["peers_online"],
            "pending_outgoing_ops": 0,
        },
    }


def _validate_tombstone_checkpoint(value: dict[str, Any]) -> None:
    sync = value.get("sync")
    checkpoint = value.get("checkpoint")
    role = value.get("role")
    allowed_roles = {
        "baseline": {"baseline"},
        "deleted": {"deleter", "online-observer", "isolated"},
        "reconnected": {"converged"},
        "stable": {"stable"},
    }
    if not (
        value.get("evidence_schema") == SCHEMA_VERSION
        and value.get("evidence_class") == TOMBSTONE_EVIDENCE_CLASS
        and value.get("real_device_evidence") is True
        and value.get("final_device_evidence") is False
        and value.get("scenario") == "tombstone-propagation-and-no-resurrection"
        and checkpoint in allowed_roles
        and role in allowed_roles[checkpoint]
        and isinstance(value.get("release"), dict)
        and isinstance(value.get("run_id"), str)
        and RUN_ID_PATTERN.fullmatch(value["run_id"])
        and isinstance(value.get("captured_at_epoch"), int)
        and not isinstance(value.get("captured_at_epoch"), bool)
        and isinstance(value.get("visible"), bool)
        and isinstance(value.get("tombstone"), bool)
        and value["visible"] is not value["tombstone"]
        and isinstance(value.get("clock_entries"), int)
        and value["clock_entries"] >= 1
        and isinstance(value.get("clock_total"), int)
        and value["clock_total"] >= 1
        and all(
            isinstance(value.get(field), str) and SHA256_PATTERN.fullmatch(value[field])
            for field in (
                "topology_evidence_sha256",
                "node_manifest_sha256",
                "node_identity_digest",
                "query_digest",
                "scope_digest",
                "knowledge_digest",
                "state_digest",
            )
        )
        and isinstance(sync, dict)
        and sync.get("enabled") is True
        and isinstance(sync.get("paused"), bool)
        and isinstance(sync.get("peers_online"), int)
        and not isinstance(sync.get("peers_online"), bool)
        and 0 <= sync["peers_online"] <= 3
        and sync.get("pending_outgoing_ops") == 0
    ):
        raise EvidenceError("tombstone checkpoint manifest is invalid")
    _validate_timestamp(value.get("captured_at_utc"), value["captured_at_epoch"])


def validate_tombstone_scenario(
    *, topology_path: Path, checkpoint_paths: list[Path]
) -> dict[str, Any]:
    """Validate tombstone spread, old-copy reconnect, and stable non-resurrection."""
    topology = _require_topology(_read_json(topology_path))
    if len(checkpoint_paths) != 12 or len({path.resolve() for path in checkpoint_paths}) != 12:
        raise EvidenceError("exactly twelve distinct tombstone checkpoints are required")
    values = [_read_json(path) for path in checkpoint_paths]
    for value in values:
        _validate_tombstone_checkpoint(value)
    topology_hash = _sha256_file(topology_path)
    identities = set(topology["topology"]["member_identity_digests"])
    if any(
        value["run_id"] != topology["run_id"]
        or value["release"] != topology["release"]
        or value["topology_evidence_sha256"] != topology_hash
        for value in values
    ):
        raise EvidenceError("tombstone checkpoints do not bind the topology release")
    if {value["node_identity_digest"] for value in values} != identities:
        raise EvidenceError("tombstone checkpoints do not cover the topology devices")
    if {
        value["node_manifest_sha256"] for value in values
    } != set(topology["source_node_manifest_sha256"]):
        raise EvidenceError("tombstone checkpoints do not bind the topology nodes")
    for field in ("query_digest", "scope_digest", "knowledge_digest"):
        if len({value[field] for value in values}) != 1:
            raise EvidenceError("tombstone checkpoints do not track one shared memory")

    phases = ("baseline", "deleted", "reconnected", "stable")
    grouped = {
        phase: [value for value in values if value["checkpoint"] == phase]
        for phase in phases
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
            "each tombstone checkpoint must cover all devices within the time window"
        )
    baseline = grouped["baseline"]
    deleted = grouped["deleted"]
    reconnected = grouped["reconnected"]
    stable = grouped["stable"]
    if not (
        all(value["visible"] and not value["tombstone"] for value in baseline)
        and len({value["state_digest"] for value in baseline}) == 1
        and len({value["clock_total"] for value in baseline}) == 1
    ):
        raise EvidenceError("tombstone baseline is not a shared visible state")
    baseline_digest = baseline[0]["state_digest"]
    baseline_clock = baseline[0]["clock_total"]
    roles = {value["role"]: value for value in deleted}
    if set(roles) != {"deleter", "online-observer", "isolated"}:
        raise EvidenceError("tombstone deletion roles are incomplete")
    isolated = roles["isolated"]
    online = [roles["deleter"], roles["online-observer"]]
    if not (
        isolated["visible"]
        and not isolated["tombstone"]
        and isolated["state_digest"] == baseline_digest
        and isolated["clock_total"] == baseline_clock
        and isolated["sync"]["paused"] is True
        and isolated["sync"]["peers_online"] <= 2
        and all(not value["visible"] and value["tombstone"] for value in online)
        and len({value["state_digest"] for value in online}) == 1
        and {value["clock_total"] for value in online} == {baseline_clock + 1}
        and all(
            value["sync"]["paused"] is False
            and value["sync"]["peers_online"] == 2
            for value in online
        )
    ):
        raise EvidenceError("tombstone did not propagate while one old copy was isolated")
    deleted_digest = online[0]["state_digest"]
    for phase, group in (("reconnected", reconnected), ("stable", stable)):
        if not (
            all(not value["visible"] and value["tombstone"] for value in group)
            and {value["state_digest"] for value in group} == {deleted_digest}
            and {value["clock_total"] for value in group} == {baseline_clock + 1}
            and all(
                value["sync"]["paused"] is False
                and value["sync"]["peers_online"] == 3
                for value in group
            )
        ):
            raise EvidenceError(f"tombstone {phase} state is not stable and converged")
    phase_order = {phase: index for index, phase in enumerate(phases)}
    for identity in identities:
        series = sorted(
            (value for value in values if value["node_identity_digest"] == identity),
            key=lambda value: phase_order[value["checkpoint"]],
        )
        if len({value["node_manifest_sha256"] for value in series}) != 1 or [
            value["captured_at_epoch"] for value in series
        ] != sorted(value["captured_at_epoch"] for value in series):
            raise EvidenceError("tombstone node manifests or times are inconsistent")

    generated_at_utc, generated_at_epoch = _utc_now()
    return {
        "evidence_schema": SCHEMA_VERSION,
        "evidence_class": TOMBSTONE_REPORT_CLASS,
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
        "scenario": "tombstone-propagation-and-no-resurrection",
        "checks": {
            "shared_visible_baseline": "passed",
            "two_node_tombstone_propagation": "passed",
            "isolated_old_copy_preserved_before_reconnect": "passed",
            "old_copy_reconnect_did_not_resurrect": "passed",
            "second_reconciliation_remained_deleted": "passed",
            "online_quiescent_final_state": "passed",
        },
        "remaining_required_scenarios": [
            "offline-write-and-reconnect",
            "concurrent-update-and-conflict-resolution",
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
    offline_checkpoint = subparsers.add_parser("capture-offline")
    offline_checkpoint.add_argument("--topology", required=True, type=Path)
    offline_checkpoint.add_argument("--node", required=True, type=Path)
    offline_checkpoint.add_argument("--base-url", default="http://127.0.0.1:8765")
    offline_checkpoint.add_argument("--scope", required=True)
    offline_checkpoint.add_argument(
        "--checkpoint", required=True, choices=("baseline", "diverged", "converged")
    )
    offline_checkpoint.add_argument(
        "--role",
        required=True,
        choices=("baseline", "isolated", "writer", "online-observer", "converged"),
    )
    offline_checkpoint.add_argument("--query-file", required=True, type=Path)
    offline_checkpoint.add_argument("--output", required=True, type=Path)
    offline_checkpoint.add_argument("--overwrite", action="store_true")
    offline_scenario = subparsers.add_parser("validate-offline")
    offline_scenario.add_argument("--topology", required=True, type=Path)
    offline_scenario.add_argument(
        "--checkpoint", required=True, action="append", type=Path
    )
    offline_scenario.add_argument("--output", required=True, type=Path)
    offline_scenario.add_argument("--overwrite", action="store_true")
    privacy_checkpoint = subparsers.add_parser("capture-privacy")
    privacy_checkpoint.add_argument("--topology", required=True, type=Path)
    privacy_checkpoint.add_argument("--node", required=True, type=Path)
    privacy_checkpoint.add_argument("--base-url", default="http://127.0.0.1:8765")
    privacy_checkpoint.add_argument("--scope", required=True)
    privacy_checkpoint.add_argument(
        "--checkpoint", required=True, choices=("baseline", "post-write")
    )
    privacy_checkpoint.add_argument(
        "--role", required=True, choices=("baseline", "writer", "observer")
    )
    privacy_checkpoint.add_argument("--query-file", required=True, type=Path)
    privacy_checkpoint.add_argument("--output", required=True, type=Path)
    privacy_checkpoint.add_argument("--overwrite", action="store_true")
    privacy_scenario = subparsers.add_parser("validate-privacy")
    privacy_scenario.add_argument("--topology", required=True, type=Path)
    privacy_scenario.add_argument(
        "--checkpoint", required=True, action="append", type=Path
    )
    privacy_scenario.add_argument("--output", required=True, type=Path)
    privacy_scenario.add_argument("--overwrite", action="store_true")
    tombstone_checkpoint = subparsers.add_parser("capture-tombstone")
    tombstone_checkpoint.add_argument("--topology", required=True, type=Path)
    tombstone_checkpoint.add_argument("--node", required=True, type=Path)
    tombstone_checkpoint.add_argument("--base-url", default="http://127.0.0.1:8765")
    tombstone_checkpoint.add_argument("--scope", required=True)
    tombstone_checkpoint.add_argument(
        "--checkpoint",
        required=True,
        choices=("baseline", "deleted", "reconnected", "stable"),
    )
    tombstone_checkpoint.add_argument(
        "--role",
        required=True,
        choices=(
            "baseline",
            "deleter",
            "online-observer",
            "isolated",
            "converged",
            "stable",
        ),
    )
    tombstone_checkpoint.add_argument("--query-file", required=True, type=Path)
    tombstone_checkpoint.add_argument("--knowledge-id-file", required=True, type=Path)
    tombstone_checkpoint.add_argument("--output", required=True, type=Path)
    tombstone_checkpoint.add_argument("--overwrite", action="store_true")
    tombstone_scenario = subparsers.add_parser("validate-tombstone")
    tombstone_scenario.add_argument("--topology", required=True, type=Path)
    tombstone_scenario.add_argument(
        "--checkpoint", required=True, action="append", type=Path
    )
    tombstone_scenario.add_argument("--output", required=True, type=Path)
    tombstone_scenario.add_argument("--overwrite", action="store_true")
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
        elif args.command == "validate-concurrency":
            output = args.output.resolve()
            inputs = {args.topology.resolve(), *(path.resolve() for path in args.checkpoint)}
            if output in inputs:
                raise EvidenceError("scenario output must not overwrite an input")
            report = validate_concurrency_scenario(
                topology_path=args.topology.resolve(),
                checkpoint_paths=args.checkpoint,
            )
        elif args.command == "capture-offline":
            output = args.output.resolve()
            inputs = {args.topology.resolve(), args.node.resolve(), args.query_file.resolve()}
            if output in inputs:
                raise EvidenceError("checkpoint output must not overwrite an input")
            try:
                query = args.query_file.read_text(encoding="utf-8")
            except OSError as exc:
                raise EvidenceError("scenario query file is not readable") from exc
            report = capture_offline_checkpoint(
                topology_path=args.topology.resolve(),
                node_path=args.node.resolve(),
                base_url=args.base_url,
                checkpoint=args.checkpoint,
                role=args.role,
                query=query,
                scope=args.scope,
            )
        elif args.command == "validate-offline":
            output = args.output.resolve()
            inputs = {args.topology.resolve(), *(path.resolve() for path in args.checkpoint)}
            if output in inputs:
                raise EvidenceError("scenario output must not overwrite an input")
            report = validate_offline_scenario(
                topology_path=args.topology.resolve(),
                checkpoint_paths=args.checkpoint,
            )
        elif args.command == "capture-privacy":
            output = args.output.resolve()
            inputs = {args.topology.resolve(), args.node.resolve(), args.query_file.resolve()}
            if output in inputs:
                raise EvidenceError("checkpoint output must not overwrite an input")
            try:
                query = args.query_file.read_text(encoding="utf-8")
            except OSError as exc:
                raise EvidenceError("scenario query file is not readable") from exc
            report = capture_privacy_checkpoint(
                topology_path=args.topology.resolve(),
                node_path=args.node.resolve(),
                base_url=args.base_url,
                checkpoint=args.checkpoint,
                role=args.role,
                query=query,
                scope=args.scope,
            )
        elif args.command == "validate-privacy":
            output = args.output.resolve()
            inputs = {args.topology.resolve(), *(path.resolve() for path in args.checkpoint)}
            if output in inputs:
                raise EvidenceError("scenario output must not overwrite an input")
            report = validate_privacy_scenario(
                topology_path=args.topology.resolve(),
                checkpoint_paths=args.checkpoint,
            )
        elif args.command == "capture-tombstone":
            output = args.output.resolve()
            inputs = {
                args.topology.resolve(),
                args.node.resolve(),
                args.query_file.resolve(),
                args.knowledge_id_file.resolve(),
            }
            if output in inputs:
                raise EvidenceError("checkpoint output must not overwrite an input")
            try:
                query = args.query_file.read_text(encoding="utf-8")
                knowledge_id = args.knowledge_id_file.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise EvidenceError("scenario input file is not readable") from exc
            report = capture_tombstone_checkpoint(
                topology_path=args.topology.resolve(),
                node_path=args.node.resolve(),
                base_url=args.base_url,
                checkpoint=args.checkpoint,
                role=args.role,
                query=query,
                scope=args.scope,
                knowledge_id=knowledge_id,
            )
        else:
            output = args.output.resolve()
            inputs = {args.topology.resolve(), *(path.resolve() for path in args.checkpoint)}
            if output in inputs:
                raise EvidenceError("scenario output must not overwrite an input")
            report = validate_tombstone_scenario(
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
