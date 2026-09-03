from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[3]
SCRIPT = ROOT / "build/release/scripts/agent-memory-ablation.py"
SPEC = importlib.util.spec_from_file_location("agent_memory_ablation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
IDENTITY = {"git_commit": "a" * 40, "candidate_package_sha256": "b" * 64}
TASK_SHA = "c" * 64


def variant(name: str, *, success_count: int = 20) -> dict:
    outcomes = [
        {
            "task_id": f"task-{index:02d}",
            "success": index <= success_count,
            "turn_count": 2,
            "recall_run_id_digest": f"{index:064x}",
            "recall_tools": ["pixiu_memory_search"] if name != "no_memory" else [],
        }
        for index in range(1, 31)
    ]
    taught = [
        {
            "task_id": f"task-{index:02d}",
            "run_id_digest": f"{index + 30:064x}",
            "tools": ["pixiu_memory_remember"] if name != "no_memory" else [],
        }
        for index in range(1, 31)
    ]
    return {
        "schema_version": 1,
        "evidence_class": "kylin-v11-agent-memory-ablation-variant",
        "real_device_evidence": True,
        "status": "complete",
        "captured_at": "2026-08-24T00:00:00Z",
        "variant": name,
        "release": IDENTITY,
        "task_set_sha256": TASK_SHA,
        "sample_count": 30,
        "metrics": {"task_success_rate": success_count / 30, "mean_turns": 2.0},
        "outcomes": outcomes,
        "teach_runs": taught,
        "source_sha256": {"native": "d" * 64, "teach_snapshot": "e" * 64, "recall_snapshot": "f" * 64},
    }


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_checked_in_task_set_is_fixed_and_large_enough() -> None:
    tasks = MODULE.validate_task_set(
        MODULE.read_json(ROOT / "build/release/agent-memory-ablation-tasks.json")
    )
    assert len(tasks) == 30
    assert len({task["token"] for task in tasks}) == 30


def test_variant_metrics_are_recomputed() -> None:
    value = variant("single_device_memory")
    MODULE.validate_variant_report(value)
    value["metrics"]["task_success_rate"] = 1.0
    with pytest.raises(MODULE.EvidenceError, match="reproduce"):
        MODULE.validate_variant_report(value)


def test_no_memory_snapshot_requires_all_surfaces_disabled() -> None:
    snapshot = {
        "schema_version": 1,
        "evidence_class": "kylin-v11-agent-ablation-runtime-snapshot",
        "real_device_evidence": True,
        "variant": "no_memory",
        "release": IDENTITY,
        "native_evidence_sha256": "1" * 64,
        "runtime_process_identity_digest": "2" * 64,
        "configuration_sha256": "3" * 64,
        "configuration": {"provider": "", "memory_enabled": False, "user_profile_enabled": False, "profile_enabled": False, "context_engine": "compressor"},
        "strict_provider": False,
        "sync": {"enabled": False},
    }
    MODULE.validate_snapshot(snapshot, "no_memory", IDENTITY)
    snapshot["configuration"]["memory_enabled"] = True
    with pytest.raises(MODULE.EvidenceError, match="isolation"):
        MODULE.validate_snapshot(snapshot, "no_memory", IDENTITY)


def test_distributed_snapshot_requires_full_mesh() -> None:
    snapshot = {
        "schema_version": 1,
        "evidence_class": "kylin-v11-agent-ablation-runtime-snapshot",
        "real_device_evidence": True,
        "variant": "distributed_memory",
        "release": IDENTITY,
        "native_evidence_sha256": "1" * 64,
        "runtime_process_identity_digest": "2" * 64,
        "configuration_sha256": "3" * 64,
        "configuration": {"provider": "pixiu"},
        "strict_provider": True,
        "sync": {"enabled": True, "paused": False, "peers_total": 3, "peers_online": 3, "pending_outgoing_ops": 0},
        "node_identity_digest": "4" * 64,
        "node_manifest_sha256": "5" * 64,
        "topology_run_id": "ablation-run",
    }
    MODULE.validate_snapshot(snapshot, "distributed_memory", IDENTITY)
    snapshot["sync"]["peers_online"] = 2
    with pytest.raises(MODULE.EvidenceError, match="full mesh"):
        MODULE.validate_snapshot(snapshot, "distributed_memory", IDENTITY)


def test_build_matrix_requires_same_tasks_release_and_dataset(tmp_path: Path) -> None:
    paths = []
    for index, name in enumerate(sorted(MODULE.VARIANTS)):
        path = tmp_path / f"{name}.json"
        write_json(path, variant(name, success_count=10 + index * 5))
        paths.append(path)
    dataset = tmp_path / "dataset.json"
    write_json(dataset, {
        "evidence_class": "pixiu-final-dataset-manifest",
        "status": "pass",
        "release": IDENTITY,
        "dataset": {"sha256": "6" * 64},
    })
    matrix = MODULE.build_matrix(paths, dataset)
    MODULE.validate_matrix(matrix)
    assert {item["name"] for item in matrix["variants"]} == MODULE.VARIANTS
    assert matrix["dataset_sha256"] == "6" * 64


def test_build_matrix_rejects_different_task_set(tmp_path: Path) -> None:
    paths = []
    for name in sorted(MODULE.VARIANTS):
        value = variant(name)
        if name == "single_device_memory":
            value["task_set_sha256"] = "9" * 64
        path = tmp_path / f"{name}.json"
        write_json(path, value)
        paths.append(path)
    dataset = tmp_path / "dataset.json"
    write_json(dataset, {"evidence_class": "pixiu-final-dataset-manifest", "status": "pass", "release": IDENTITY, "dataset": {"sha256": "6" * 64}})
    with pytest.raises(MODULE.EvidenceError, match="same task set"):
        MODULE.build_matrix(paths, dataset)
