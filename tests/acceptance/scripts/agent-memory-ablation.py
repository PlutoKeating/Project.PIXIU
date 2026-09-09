#!/usr/bin/env python3
"""Capture and validate a payload-free three-variant Agent memory ablation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


VARIANTS = {"no_memory", "single_device_memory", "distributed_memory"}
SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
PIXIU_TOOLS = {
    "pixiu_memory_search", "pixiu_memory_remember", "pixiu_memory_update",
    "pixiu_memory_forget", "pixiu_sync_status",
}


class EvidenceError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError("input is not readable JSON") from exc
    if not isinstance(value, dict):
        raise EvidenceError("input JSON must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise EvidenceError("input file is not readable") from exc
    return digest.hexdigest()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path: Path, value: dict[str, Any], overwrite: bool) -> None:
    path = path.resolve()
    if path.exists() and not overwrite:
        raise EvidenceError("output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def identity_from_native(value: dict[str, Any]) -> dict[str, str]:
    release = value.get("release")
    candidate = value.get("candidate_package")
    capabilities = value.get("capabilities")
    checks = value.get("checks")
    if not all(isinstance(item, dict) for item in (release, candidate, capabilities, checks)):
        raise EvidenceError("native evidence is incomplete")
    commit = release.get("git_commit")
    package_sha = candidate.get("sha256")
    if not (
        value.get("evidence_class") == "kylin-v11-native-sdk-product-lifecycle"
        and value.get("real_device_evidence") is True
        and value.get("status") == "pass"
        and release.get("profile") == "kylin-v11-native-x86_64"
        and release.get("kysdk") == "ON"
        and release.get("install_strict") is True
        and capabilities.get("contest_ready") is True
        and isinstance(commit, str) and COMMIT.fullmatch(commit)
        and isinstance(package_sha, str) and SHA256.fullmatch(package_sha)
        and all(checks.get(name) == "passed" for name in ("memory_write", "vector_search", "vector_delete"))
    ):
        raise EvidenceError("native evidence is not a passing strict Kylin V11 run")
    return {"git_commit": commit, "candidate_package_sha256": package_sha}


def load_lifecycle_module():
    path = Path(__file__).with_name("agent-lifecycle-evidence.py")
    spec = importlib.util.spec_from_file_location("pixiu_agent_lifecycle_evidence", path)
    if spec is None or spec.loader is None:
        raise EvidenceError("Agent lifecycle client cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_task_set(value: dict[str, Any]) -> list[dict[str, str]]:
    tasks = value.get("tasks")
    if not (
        value.get("schema_version") == 1
        and value.get("suite") == "pixiu-agent-cross-session-recall-v1"
        and isinstance(tasks, list) and len(tasks) >= 30
    ):
        raise EvidenceError("task set must contain at least 30 fixed recall tasks")
    normalized: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_tokens: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict) or set(task) != {"id", "subject", "token"}:
            raise EvidenceError("task set entry has an invalid schema")
        task_id, subject, token = task["id"], task["subject"], task["token"]
        if not (
            isinstance(task_id, str) and re.fullmatch(r"task-[0-9]{2,3}", task_id)
            and isinstance(subject, str) and 4 <= len(subject) <= 80
            and isinstance(token, str) and re.fullmatch(r"PX-[A-Z0-9]{7,24}", token)
            and task_id not in seen_ids and token not in seen_tokens
        ):
            raise EvidenceError("task set entry is invalid or duplicated")
        seen_ids.add(task_id)
        seen_tokens.add(token)
        normalized.append({"id": task_id, "subject": subject, "token": token})
    return normalized


def _explicit_config(config_path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise EvidenceError("Runtime config is not readable YAML") from exc
    if not isinstance(value, dict):
        raise EvidenceError("Runtime config root must be a mapping")
    memory = value.get("memory")
    profile = value.get("user_profile")
    context = value.get("context")
    if not isinstance(memory, dict) or not isinstance(profile, dict) or not isinstance(context, dict):
        raise EvidenceError("ablation requires explicit memory, user_profile, and context config")
    return {
        "provider": memory.get("provider"),
        "memory_enabled": memory.get("memory_enabled"),
        "user_profile_enabled": memory.get("user_profile_enabled"),
        "profile_enabled": profile.get("enabled"),
        "context_engine": context.get("engine"),
    }


def _strict_enabled(env_path: Path) -> bool:
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EvidenceError("Runtime environment file is not readable") from exc
    values = [line.split("=", 1)[1].strip() for line in lines if line.startswith("PIXIU_AGENT_STRICT=")]
    return values == ["1"]


def _validate_node_manifest(value: dict[str, Any], identity: dict[str, str]) -> dict[str, Any]:
    node = value.get("node")
    release = value.get("release")
    if not (
        value.get("evidence_class") == "kylin-v11-sync-node"
        and value.get("real_device_evidence") is True
        and isinstance(node, dict) and isinstance(release, dict)
        and release.get("git_commit") == identity["git_commit"]
        and release.get("candidate_package_sha256") == identity["candidate_package_sha256"]
        and isinstance(node.get("identity_digest"), str) and SHA256.fullmatch(node["identity_digest"])
        and node.get("peers_total") == 3 and node.get("peers_online") == 3
        and node.get("pending_outgoing_ops") == 0
        and node.get("enabled") is True and node.get("paused") is False
    ):
        raise EvidenceError("distributed snapshot lacks a passing three-device node manifest")
    return node


def snapshot(
    *, variant: str, role: str, native_path: Path, config_path: Path, env_path: Path,
    gateway_url: str, backend_url: str, node_path: Path | None,
) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise EvidenceError("unknown ablation variant")
    if role not in {"teach", "recall"}:
        raise EvidenceError("snapshot role must be teach or recall")
    native = read_json(native_path)
    identity = identity_from_native(native)
    lifecycle = load_lifecycle_module()
    client = lifecycle.AgentClient(gateway_url)
    client.validate_capabilities()
    status = lifecycle.AgentClient(backend_url).json("GET", "/sync/status")
    config = _explicit_config(config_path)
    provider = config["provider"]
    if variant == "no_memory":
        if not (provider in {None, ""} and config["memory_enabled"] is False
                and config["user_profile_enabled"] is False and config["profile_enabled"] is False
                and config["context_engine"] == "compressor"):
            raise EvidenceError("no_memory requires every Runtime memory surface explicitly disabled")
        if status.get("enabled") is not False:
            raise EvidenceError("no_memory requires PIXIU synchronization disabled")
    else:
        if provider != "pixiu" or not _strict_enabled(env_path):
            raise EvidenceError("memory variants require the strict PIXIU provider")
        if variant == "single_device_memory" and status.get("enabled") is not False:
            raise EvidenceError("single_device_memory requires synchronization disabled")
        if variant == "distributed_memory" and status.get("enabled") is not True:
            raise EvidenceError("distributed_memory requires synchronization enabled")
    node_identity = None
    topology_run_id = None
    node_sha = None
    if variant == "distributed_memory":
        if node_path is None:
            raise EvidenceError("distributed_memory requires a node manifest")
        manifest = read_json(node_path)
        node = _validate_node_manifest(manifest, identity)
        node_identity = node["identity_digest"]
        topology_run_id = manifest.get("run_id")
        node_sha = sha256_file(node_path)
    elif node_path is not None:
        raise EvidenceError("node manifests are only valid for distributed_memory")
    return {
        "schema_version": 1,
        "evidence_class": "kylin-v11-agent-ablation-runtime-snapshot",
        "real_device_evidence": True,
        "captured_at": utc_now(),
        "variant": variant,
        "snapshot_role": role,
        "release": identity,
        "native_evidence_sha256": sha256_file(native_path),
        "runtime_process_identity_digest": client.runtime_identity(),
        "configuration": config,
        "configuration_sha256": sha256_file(config_path),
        "strict_provider": variant != "no_memory",
        "sync": {
            "enabled": status.get("enabled"),
            "paused": status.get("paused"),
            "peers_total": status.get("peers_total"),
            "peers_online": status.get("peers_online"),
            "pending_outgoing_ops": status.get("pending_outgoing_ops"),
        },
        "node_identity_digest": node_identity,
        "topology_run_id": topology_run_id,
        "node_manifest_sha256": node_sha,
    }


def validate_snapshot(
    value: dict[str, Any], variant: str, identity: dict[str, str], role: str | None = None
) -> None:
    config = value.get("configuration")
    sync = value.get("sync")
    if not (
        value.get("schema_version") == 1
        and value.get("evidence_class") == "kylin-v11-agent-ablation-runtime-snapshot"
        and value.get("real_device_evidence") is True
        and value.get("variant") == variant and value.get("release") == identity
        and value.get("snapshot_role") in {"teach", "recall"}
        and (role is None or value.get("snapshot_role") == role)
        and isinstance(config, dict) and isinstance(sync, dict)
        and SHA256.fullmatch(str(value.get("native_evidence_sha256", "")))
        and SHA256.fullmatch(str(value.get("runtime_process_identity_digest", "")))
        and SHA256.fullmatch(str(value.get("configuration_sha256", "")))
    ):
        raise EvidenceError("runtime snapshot is invalid")
    if variant == "no_memory":
        if not (config.get("provider") in {None, ""} and config.get("memory_enabled") is False
                and config.get("user_profile_enabled") is False and config.get("profile_enabled") is False
                and config.get("context_engine") == "compressor"
                and value.get("strict_provider") is False and sync.get("enabled") is False):
            raise EvidenceError("no-memory snapshot does not prove full memory isolation")
    elif variant == "single_device_memory":
        if not (config.get("provider") == "pixiu" and value.get("strict_provider") is True
                and sync.get("enabled") is False):
            raise EvidenceError("single-device snapshot is not isolated")
    else:
        if not (config.get("provider") == "pixiu" and value.get("strict_provider") is True
                and sync.get("enabled") is True and sync.get("paused") is False
                and sync.get("peers_total") == 3 and sync.get("peers_online") == 3
                and sync.get("pending_outgoing_ops") == 0
                and SHA256.fullmatch(str(value.get("node_identity_digest", "")))
                and SHA256.fullmatch(str(value.get("node_manifest_sha256", "")))
                and isinstance(value.get("topology_run_id"), str)):
            raise EvidenceError("distributed snapshot does not prove a quiescent full mesh")


def capture(
    *, variant: str, native_path: Path, task_path: Path, teach_snapshot_path: Path,
    recall_snapshot_path: Path, teach_url: str, recall_url: str,
) -> dict[str, Any]:
    native = read_json(native_path)
    identity = identity_from_native(native)
    tasks = validate_task_set(read_json(task_path))
    teach_snapshot = read_json(teach_snapshot_path)
    recall_snapshot = read_json(recall_snapshot_path)
    validate_snapshot(teach_snapshot, variant, identity, "teach")
    validate_snapshot(recall_snapshot, variant, identity, "recall")
    if sha256_file(teach_snapshot_path) == sha256_file(recall_snapshot_path):
        raise EvidenceError("teach and recall require distinct runtime snapshots")
    teach_device = teach_snapshot.get("node_identity_digest")
    recall_device = recall_snapshot.get("node_identity_digest")
    if variant == "distributed_memory":
        if teach_device == recall_device or teach_snapshot["topology_run_id"] != recall_snapshot["topology_run_id"]:
            raise EvidenceError("distributed recall must cross two devices in one proven topology")
    lifecycle = load_lifecycle_module()
    teach_client = lifecycle.AgentClient(teach_url)
    recall_client = lifecycle.AgentClient(recall_url)
    teach_client.validate_capabilities()
    recall_client.validate_capabilities()
    if teach_client.runtime_identity() != teach_snapshot["runtime_process_identity_digest"]:
        raise EvidenceError("teach Gateway is not the snapshotted Runtime")
    if recall_client.runtime_identity() != recall_snapshot["runtime_process_identity_digest"]:
        raise EvidenceError("recall Gateway is not the snapshotted Runtime")
    taught: list[dict[str, Any]] = []
    for task in tasks:
        session_id = f"pixiu-ablation-teach-{task['id']}-{os.urandom(6).hex()}"
        teach_client.create_session(session_id)
        prompt = f"请长期记住这条虚构验收事实：{task['subject']} 的代号是 {task['token']}。稍后会在独立会话询问。"
        run = teach_client.run(session_id, prompt, lambda _run_id: False)
        taught.append({"task_id": task["id"], "run_id_digest": run["run_id_digest"], "tools": sorted(run["tools"])})
    outcomes: list[dict[str, Any]] = []
    for task in tasks:
        session_id = f"pixiu-ablation-recall-{task['id']}-{os.urandom(6).hex()}"
        recall_client.create_session(session_id)
        prompt = f"这是独立新会话。请回忆虚构验收事实中“{task['subject']}”对应的代号；不知道就回答 UNKNOWN。"
        run = recall_client.run(session_id, prompt, lambda _run_id: False)
        output = run.pop("output")
        outcomes.append({
            "task_id": task["id"],
            "success": task["token"] in output,
            "turn_count": 2,
            "recall_run_id_digest": run["run_id_digest"],
            "recall_tools": sorted(run["tools"]),
        })
    if variant == "no_memory" and (
        any(PIXIU_TOOLS.intersection(item["tools"]) for item in taught)
        or any(PIXIU_TOOLS.intersection(item["recall_tools"]) for item in outcomes)
    ):
        raise EvidenceError("no-memory Agent unexpectedly exposed PIXIU tools")
    successes = sum(item["success"] for item in outcomes)
    report = {
        "schema_version": 1,
        "evidence_class": "kylin-v11-agent-memory-ablation-variant",
        "real_device_evidence": True,
        "status": "complete",
        "captured_at": utc_now(),
        "variant": variant,
        "release": identity,
        "task_set_sha256": sha256_file(task_path),
        "sample_count": len(outcomes),
        "metrics": {"task_success_rate": successes / len(outcomes), "mean_turns": 2.0},
        "outcomes": outcomes,
        "teach_runs": taught,
        "source_sha256": {
            "native": sha256_file(native_path),
            "teach_snapshot": sha256_file(teach_snapshot_path),
            "recall_snapshot": sha256_file(recall_snapshot_path),
        },
    }
    validate_variant_report(report)
    return report


def validate_variant_report(value: dict[str, Any]) -> None:
    metrics = value.get("metrics")
    outcomes = value.get("outcomes")
    taught = value.get("teach_runs")
    count = value.get("sample_count")
    release = value.get("release")
    if not (
        value.get("schema_version") == 1
        and value.get("evidence_class") == "kylin-v11-agent-memory-ablation-variant"
        and value.get("real_device_evidence") is True and value.get("status") == "complete"
        and value.get("variant") in VARIANTS
        and isinstance(release, dict) and COMMIT.fullmatch(str(release.get("git_commit", "")))
        and SHA256.fullmatch(str(release.get("candidate_package_sha256", "")))
        and SHA256.fullmatch(str(value.get("task_set_sha256", "")))
        and isinstance(count, int) and count >= 30
        and isinstance(outcomes, list) and len(outcomes) == count
        and isinstance(taught, list) and len(taught) == count
        and isinstance(metrics, dict) and set(metrics) == {"task_success_rate", "mean_turns"}
    ):
        raise EvidenceError("variant report is incomplete")
    ids = [item.get("task_id") for item in outcomes if isinstance(item, dict)]
    teach_ids = [item.get("task_id") for item in taught if isinstance(item, dict)]
    if len(set(ids)) != count or set(ids) != set(teach_ids):
        raise EvidenceError("variant tasks are duplicated or unmatched")
    if not all(
        isinstance(item, dict)
        and SHA256.fullmatch(str(item.get("run_id_digest", "")))
        and isinstance(item.get("tools"), list)
        and all(isinstance(tool, str) and tool for tool in item["tools"])
        for item in taught
    ):
        raise EvidenceError("variant teach run is invalid")
    if not all(
        isinstance(item, dict) and isinstance(item.get("success"), bool)
        and item.get("turn_count") == 2
        and SHA256.fullmatch(str(item.get("recall_run_id_digest", "")))
        and isinstance(item.get("recall_tools"), list)
        and all(isinstance(tool, str) and tool for tool in item["recall_tools"])
        for item in outcomes
    ):
        raise EvidenceError("variant outcome is invalid")
    rate = sum(item["success"] for item in outcomes) / count
    if metrics.get("task_success_rate") != rate or metrics.get("mean_turns") != 2.0:
        raise EvidenceError("variant metrics do not reproduce from outcomes")
    if value["variant"] == "no_memory" and (
        any(PIXIU_TOOLS.intersection(item["tools"]) for item in taught)
        or any(PIXIU_TOOLS.intersection(item["recall_tools"]) for item in outcomes)
    ):
        raise EvidenceError("no-memory report contains PIXIU tool execution")


def build_matrix(paths: list[Path], dataset_path: Path) -> dict[str, Any]:
    if len(paths) != 3 or len({path.resolve() for path in paths}) != 3:
        raise EvidenceError("exactly three distinct variant reports are required")
    reports = [read_json(path) for path in paths]
    for report in reports:
        validate_variant_report(report)
    if {report["variant"] for report in reports} != VARIANTS:
        raise EvidenceError("matrix must contain each variant exactly once")
    if len({json.dumps(report["release"], sort_keys=True) for report in reports}) != 1:
        raise EvidenceError("variant reports identify different releases")
    if len({report["task_set_sha256"] for report in reports}) != 1:
        raise EvidenceError("variant reports do not use the same task set")
    task_ids = [{item["task_id"] for item in report["outcomes"]} for report in reports]
    if any(ids != task_ids[0] for ids in task_ids[1:]):
        raise EvidenceError("variant reports do not cover identical tasks")
    dataset_manifest = read_json(dataset_path)
    dataset = dataset_manifest.get("dataset")
    if not (
        dataset_manifest.get("evidence_class") == "pixiu-final-dataset-manifest"
        and dataset_manifest.get("status") == "pass"
        and dataset_manifest.get("release") == reports[0]["release"]
        and isinstance(dataset, dict)
        and isinstance(dataset.get("sha256"), str) and SHA256.fullmatch(dataset["sha256"])
    ):
        raise EvidenceError("dataset manifest does not bind the ablation release")
    result = {
        "schema_version": 1,
        "evidence_class": "kylin-v11-agent-memory-ablation",
        "real_device_evidence": True,
        "status": "pass",
        "captured_at": utc_now(),
        "release": reports[0]["release"],
        "dataset_sha256": dataset["sha256"],
        "task_set_sha256": reports[0]["task_set_sha256"],
        "variants": sorted([
            {"name": report["variant"], "sample_count": report["sample_count"], "metrics": report["metrics"]}
            for report in reports
        ], key=lambda item: item["name"]),
        "source_variant_sha256": {report["variant"]: sha256_file(path) for report, path in zip(reports, paths)},
        "dataset_manifest_sha256": sha256_file(dataset_path),
    }
    validate_matrix(result)
    return result


def validate_matrix(value: dict[str, Any]) -> None:
    release = value.get("release")
    variants = value.get("variants")
    sources = value.get("source_variant_sha256")
    if not (
        value.get("schema_version") == 1
        and value.get("evidence_class") == "kylin-v11-agent-memory-ablation"
        and value.get("real_device_evidence") is True and value.get("status") == "pass"
        and isinstance(release, dict) and COMMIT.fullmatch(str(release.get("git_commit", "")))
        and SHA256.fullmatch(str(release.get("candidate_package_sha256", "")))
        and SHA256.fullmatch(str(value.get("dataset_sha256", "")))
        and SHA256.fullmatch(str(value.get("task_set_sha256", "")))
        and SHA256.fullmatch(str(value.get("dataset_manifest_sha256", "")))
        and isinstance(variants, list) and len(variants) == 3
        and {item.get("name") for item in variants if isinstance(item, dict)} == VARIANTS
        and isinstance(sources, dict) and set(sources) == VARIANTS
        and all(SHA256.fullmatch(str(item)) for item in sources.values())
    ):
        raise EvidenceError("ablation matrix is invalid")
    for variant in variants:
        metrics = variant.get("metrics") if isinstance(variant, dict) else None
        if not (
            isinstance(variant, dict) and isinstance(variant.get("sample_count"), int)
            and variant["sample_count"] >= 30 and isinstance(metrics, dict)
            and set(metrics) == {"task_success_rate", "mean_turns"}
            and isinstance(metrics.get("task_success_rate"), (int, float))
            and not isinstance(metrics.get("task_success_rate"), bool)
            and 0 <= metrics["task_success_rate"] <= 1
            and isinstance(metrics.get("mean_turns"), (int, float))
            and not isinstance(metrics.get("mean_turns"), bool) and metrics["mean_turns"] > 0
        ):
            raise EvidenceError("ablation matrix metrics are invalid")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--variant", choices=sorted(VARIANTS), required=True)
    snap.add_argument("--role", choices=("teach", "recall"), required=True)
    snap.add_argument("--native-evidence", type=Path, required=True)
    snap.add_argument("--runtime-config", type=Path, required=True)
    snap.add_argument("--runtime-env", type=Path, required=True)
    snap.add_argument("--gateway-url", default="http://127.0.0.1:8642")
    snap.add_argument("--backend-url", default="http://127.0.0.1:8765")
    snap.add_argument("--node-manifest", type=Path)
    capture_parser = sub.add_parser("capture")
    capture_parser.add_argument("--variant", choices=sorted(VARIANTS), required=True)
    capture_parser.add_argument("--native-evidence", type=Path, required=True)
    capture_parser.add_argument("--task-set", type=Path, required=True)
    capture_parser.add_argument("--teach-snapshot", type=Path, required=True)
    capture_parser.add_argument("--recall-snapshot", type=Path, required=True)
    capture_parser.add_argument("--teach-url", default="http://127.0.0.1:8642")
    capture_parser.add_argument("--recall-url", default="http://127.0.0.1:8642")
    build = sub.add_parser("build")
    build.add_argument("--variant-report", type=Path, action="append", required=True)
    build.add_argument("--dataset-manifest", type=Path, required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--kind", choices=("matrix", "variant"), default="matrix")
    for command in (snap, capture_parser, build, validate):
        command.add_argument("--output", type=Path, required=True)
    for command in (snap, capture_parser, build):
        command.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "snapshot":
            result = snapshot(variant=args.variant, role=args.role, native_path=args.native_evidence,
                              config_path=args.runtime_config, env_path=args.runtime_env,
                              gateway_url=args.gateway_url, backend_url=args.backend_url,
                              node_path=args.node_manifest)
            write_json(args.output, result, args.overwrite)
        elif args.command == "capture":
            result = capture(variant=args.variant, native_path=args.native_evidence,
                             task_path=args.task_set, teach_snapshot_path=args.teach_snapshot,
                             recall_snapshot_path=args.recall_snapshot,
                             teach_url=args.teach_url, recall_url=args.recall_url)
            write_json(args.output, result, args.overwrite)
        elif args.command == "build":
            result = build_matrix(args.variant_report, args.dataset_manifest)
            write_json(args.output, result, args.overwrite)
        else:
            value = read_json(args.output)
            if args.kind == "variant":
                validate_variant_report(value)
            else:
                validate_matrix(value)
        print("Agent memory ablation evidence: PASS")
        return 0
    except EvidenceError as exc:
        print(f"Agent memory ablation evidence: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
