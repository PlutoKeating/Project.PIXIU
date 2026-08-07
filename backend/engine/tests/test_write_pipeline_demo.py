"""Integration-style check for the Memory write pipeline demo.

Asserts Service-layer orchestration + Mock repository round-trips.
Does not bypass Services to call Cleaner/Extractor/etc.
"""

from __future__ import annotations

import pytest

from backend.engine.demos.run_write_pipeline import USER_UTTERANCE, run_pipeline


@pytest.mark.asyncio
async def test_write_pipeline_demo_end_to_end() -> None:
    result = await run_pipeline()

    evidence = result["evidence"]
    prefs = result["preferences"]
    knowledge = result["knowledge"]
    storage = result["storage"]

    # 1) IngestionService produced Evidence
    assert evidence.id.startswith("evd_")
    assert evidence.source_type == "MANUAL_CONFIG"
    assert evidence.quality_score > 0
    assert USER_UTTERANCE in str(evidence.raw)

    # 2) PreferenceService extracted + saved
    assert len(prefs) >= 1
    assert prefs[0].category == "OUTPUT_STYLE"
    assert "output_style" in prefs[0].key

    # 3) KnowledgeService structured + saved
    assert knowledge.id.startswith("knw_")
    assert evidence.id in knowledge.evidence_ids
    assert knowledge.embedding_ref

    # 4) Mock repos round-trip visible in storage dump
    assert any(e["id"] == evidence.id for e in storage["evidence"])
    assert any(p["id"] == prefs[0].id for p in storage["preferences"])
    assert any(k["id"] == knowledge.id for k in storage["knowledge_items"])
