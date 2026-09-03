from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.foundation.eval.sync_evidence import run_three_node_protocol_evidence


@pytest.mark.asyncio
async def test_three_node_protocol_evidence_is_explicitly_not_final(tmp_path: Path):
    report = await run_three_node_protocol_evidence(
        Path(__file__).resolve().parents[3],
        release_commit="a" * 40,
        generated_at=2_000_000_100,
    )

    assert report["status"] == "passed"
    assert report["final_device_evidence"] is False
    assert report["topology"] == {
        "logical_nodes": 3,
        "processes": 1,
        "isolated_databases": 3,
        "trust_edges": 3,
        "domain": "shared:home",
    }
    assert {scenario["id"] for scenario in report["scenarios"]} == {
        "full-mesh-pairing",
        "concurrent-update-convergence",
        "offline-anti-entropy",
        "offline-forget-no-resurrection",
        "private-scope-never-enters-oplog",
    }
    assert all(scenario["passed"] for scenario in report["scenarios"])
    assert len({node["logical_view_digest"] for node in report["nodes"]}) == 1
    serialized = json.dumps(report, ensure_ascii=False)
    assert str(tmp_path) not in serialized
    assert "must-not-sync" not in serialized
