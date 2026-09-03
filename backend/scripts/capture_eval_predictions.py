"""Capture live-system predictions for the acceptance reference corpus.

Runs the pixiu-family-expense-v1 dataset through the real foundation/engine
pipeline (same code paths as the installed backend service): ingestion,
knowledge structuring, hybrid retrieval, preference extraction and conflict
arbitration. Emits a PredictionRecord JSON consumable by

    python -m backend.foundation.eval \
        --dataset reference-v1 --predictions <this output>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import aiosqlite

from backend.engine.conflict import ConflictService
from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.kylin import get_embedder
from backend.engine.preference import PreferenceService
from backend.foundation.eval.reference import build_reference_dataset
from backend.foundation.retrieval import RetrievalService
from backend.foundation.storage.migrations import apply_pending
from backend.foundation.storage.repository import (
    SqliteConflictRepo,
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
    SqlitePreferenceRepo,
)
from backend.foundation.storage.vector_store import SqliteVectorStore


async def _capture(db_path: str) -> list[dict]:
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")

    sync_conn = sqlite3.connect(db_path)
    try:
        apply_pending(sync_conn)
        sync_conn.commit()
    finally:
        sync_conn.close()

    embedder = get_embedder("portable")
    evidence_repo = SqliteEvidenceRepo(db)
    knowledge_repo = SqliteKnowledgeRepo(db)
    entity_repo = SqliteEntityRepo(db)
    ingestion = IngestionService(evidence_repo=evidence_repo)
    knowledge = KnowledgeService(
        knw_repo=knowledge_repo,
        entity_repo=entity_repo,
        embedder=embedder,
        vector_store=SqliteVectorStore(db),
    )
    preference = PreferenceService(pref_repo=SqlitePreferenceRepo(db))
    retrieval = RetrievalService(
        knw_repo=knowledge_repo,
        entity_repo=entity_repo,
        evidence_repo=evidence_repo,
        embedder=embedder,
        vector_store=SqliteVectorStore(db),
    )

    dataset = build_reference_dataset()
    golden_evd_to_actual: dict[str, str] = {}
    golden_knw_to_actual: dict[str, str] = {}
    actual_knw_to_golden: dict[str, str] = {}
    actual_evd_to_golden: dict[str, str] = {}

    # 1) 录入 50 组家庭支出清单（赛题场景来源为 OCR）。
    for fixture in dataset.fixtures:
        raw = {
            "title": fixture["title"],
            "body": fixture["body"],
            "entities": fixture["entities"],
            "relations": fixture["relations"],
        }
        evidence = await ingestion.ingest("OCR", raw, fixture["scope"])
        item = await knowledge.structure(evidence)
        golden_evd_to_actual[fixture["evidence_id"]] = evidence.id
        actual_evd_to_golden[evidence.id] = fixture["evidence_id"]
        golden_knw_to_actual[fixture["knowledge_id"]] = item.id
        actual_knw_to_golden[item.id] = fixture["knowledge_id"]

    predictions: list[dict] = []
    for case in dataset.cases:
        if case.task == "retrieval":
            samples: list[float] = []
            atom = None
            for _ in range(dataset.retrieval_repetitions):
                started = time.perf_counter()
                atom = await retrieval.query(
                    case.input["text"], dict(case.input["context_hint"])
                )
                samples.append(round((time.perf_counter() - started) * 1000, 3))

            golden_knw = (
                actual_knw_to_golden.get(atom.source_knowledge)
                if atom.source_knowledge
                else None
            )
            aggregate = None
            if atom.source_knowledge:
                item = await knowledge_repo.get(atom.source_knowledge)
                if item is not None:
                    aggregate = round(
                        sum(
                            float(entry.get("amount", 0))
                            for entry in item.body.get("items", [])
                            if entry.get("category") == "水电燃气"
                        ),
                        2,
                    )
            predictions.append(
                {
                    "case_id": case.id,
                    "prediction": {
                        "knowledge_ids": [golden_knw] if golden_knw else [],
                        "evidence_ids": sorted(
                            actual_evd_to_golden.get(e, e)
                            for e in atom.source_evidence
                        ),
                        "aggregate_amount": aggregate,
                    },
                    "latency_ms": samples[-1] if samples else 0.0,
                    "latency_samples_ms": samples,
                }
            )

        elif case.task == "preference":
            category, key = case.input["category"], case.input["key"]
            source_type = "USER_BEHAVIOR" if category == "OP_HABIT" else "MANUAL_CONFIG"
            evidence = await ingestion.ingest(
                source_type, {"title": key, "key": key, "enabled": True}, "user:eval"
            )
            extracted = await preference.extract(evidence)
            labels = [f"{p.category.value}:{p.key}" for p in extracted]
            predictions.append(
                {
                    "case_id": case.id,
                    "prediction": {"labels": labels},
                    "latency_ms": 0.0,
                }
            )

        else:  # conflict —— 走真实仲裁管线：先写旧知识，再写冲突新知识。
            index = int(case.input["old"])
            entity = f"冲突实体-{index:02d}"
            scenario = case.input.get("scenario", "new_wins")

            def _raw_new_wins() -> dict:
                return {
                    "title": f"冲突场景-{index:02d}",
                    "body": {"items": [{"vendor": "Alpha", "amount": 100.0 + index}]},
                    "entities": [entity],
                    "relations": [],
                }

            def _raw_merge() -> tuple[dict, dict]:
                # MERGE：新知识扩展旧知识的明细项，无字段冲突。
                old_body = {"items": [{"vendor": "Alpha", "amount": 100.0 + index}]}
                new_body = {
                    "items": [
                        {"vendor": "Alpha", "amount": 100.0 + index},
                        {"vendor": "Beta", "amount": 50.0 + index},
                    ]
                }
                return old_body, new_body

            def _raw_manual() -> tuple[dict, dict]:
                # MANUAL：数值冲突 + 标题带人工确认标记。
                old = {
                    "title": f"冲突场景-{index:02d}",
                    "body": {"items": [{"vendor": "Alpha", "amount": 100.0 + index}]},
                    "entities": [entity],
                    "relations": [],
                }
                new = {
                    "title": f"冲突场景-{index:02d}（人工确认）",
                    "body": {"items": [{"vendor": "Alpha", "amount": 200.0 + index}]},
                    "entities": [entity],
                    "relations": [],
                }
                return old, new

            if scenario == "merge":
                old_body, new_body = _raw_merge()
                old_evidence = await ingestion.ingest(
                    "MANUAL_CONFIG",
                    {
                        "title": f"冲突场景-{index:02d}",
                        "body": old_body,
                        "entities": [entity],
                        "relations": [],
                    },
                    "shared:home",
                )
                await knowledge.structure(old_evidence)
                new_evidence = await ingestion.ingest(
                    "MANUAL_CONFIG",
                    {
                        "title": f"冲突场景-{index:02d}",
                        "body": new_body,
                        "entities": [entity],
                        "relations": [],
                    },
                    "shared:home",
                )
            elif scenario == "manual":
                old_raw, new_raw = _raw_manual()
                old_evidence = await ingestion.ingest("MANUAL_CONFIG", old_raw, "shared:home")
                await knowledge.structure(old_evidence)
                new_evidence = await ingestion.ingest("MANUAL_CONFIG", new_raw, "shared:home")
            else:
                old_evidence = await ingestion.ingest(
                    "MANUAL_CONFIG", _raw_new_wins(), "shared:home"
                )
                await knowledge.structure(old_evidence)
                new_evidence = await ingestion.ingest(
                    "MANUAL_CONFIG", _raw_new_wins(), "shared:home"
                )

            record = await ConflictService(
                knw_repo=knowledge_repo, conflict_repo=SqliteConflictRepo(db)
            ).arbitrate(await knowledge.structure(new_evidence))
            predictions.append(
                {
                    "case_id": case.id,
                    "prediction": {
                        "resolution": record.resolution.value if record else "NONE"
                    },
                    "latency_ms": 0.0,
                }
            )

    await db.close()
    return predictions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="predictions JSON 输出路径")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="pixiu-eval-") as tmp:
        predictions = asyncio.run(_capture(str(Path(tmp) / "pixiu.db")))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(predictions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"captured {len(predictions)} predictions -> {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
