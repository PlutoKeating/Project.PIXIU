#!/usr/bin/env python3
"""Minimal Memory write-pipeline demo (Service layer only + Mock repos).

Run from repository root:
    python -m backend.engine.demos.run_write_pipeline

Does not modify core business modules. Orchestrates existing Services and
prints a step-by-step log so humans can verify the write chain.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from backend.engine.ingest import IngestionService
from backend.engine.knowledge import KnowledgeService
from backend.engine.kylin import MockEmbedding
from backend.engine.mocks import (
    MockEntityRepository,
    MockEvidenceRepository,
    MockKnowledgeRepository,
    MockPreferenceRepository,
)
from backend.engine.preference import PreferenceService


USER_UTTERANCE = "以后回答问题尽量简洁，我喜欢先看结论。"


def _dump(obj: Any) -> str:
    if hasattr(obj, "model_dump"):
        data = obj.model_dump()
    elif isinstance(obj, list):
        return "[\n" + ",\n".join(_dump(x) for x in obj) + "\n]"
    else:
        data = obj
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _section(title: str) -> None:
    print(f"\n[{title}]")


def _build_manual_config_raw(utterance: str) -> dict[str, Any]:
    """Wrap natural-language preference into MANUAL_CONFIG for ingest + extract."""
    return {
        "title": "output_style.compact",
        "key": "output_style.compact",
        "enabled": True,
        "detail_level": "concise",
        "user_utterance": utterance,
        "body": {
            "key": "output_style.compact",
            "enabled": True,
            "detail_level": "concise",
            "style": "concise",
            "user_utterance": utterance,
            "preference_hint": "prefer_conclusion_first",
        },
    }


async def run_pipeline() -> dict[str, Any]:
    print("========== PIPELINE START ==========")

    evidence_repo = MockEvidenceRepository()
    pref_repo = MockPreferenceRepository()
    knw_repo = MockKnowledgeRepository()
    entity_repo = MockEntityRepository()

    ingestion = IngestionService(evidence_repo=evidence_repo)
    preference = PreferenceService(pref_repo=pref_repo)
    knowledge = KnowledgeService(
        knw_repo=knw_repo,
        entity_repo=entity_repo,
        embedder=MockEmbedding(dim=32),
    )

    raw = _build_manual_config_raw(USER_UTTERANCE)
    source_type = "MANUAL_CONFIG"
    scope = "user:alice"

    _section("INPUT")
    print("用户输入:")
    print(USER_UTTERANCE)
    print("\n接入形态 (source_type=MANUAL_CONFIG, 供 Preference 规则提取):")
    print(_dump(raw))
    print(f"scope: {scope}")

    # --- Ingest (Service only; internal stages annotated after return) ---
    _section("INGEST")
    print("IngestionService 开始处理")
    print("内部约定管线: Connector → Cleaner → Normalizer → Quality → EvidenceRepository.save")

    evidence = await ingestion.ingest(source_type, raw, scope)

    _section("CLEANER")
    print("执行数据清洗")
    print("(由 IngestionService 内部 Cleaner 完成；绕过检查：demo 未直接调用 Cleaner)")
    print(f"清洗后 body 字段: {list((evidence.raw.get('body') or {}).keys())}")

    _section("NORMALIZER")
    print("执行数据标准化")
    print("(由 IngestionService 内部 Normalizer 完成)")
    print(f"标准化 title: {evidence.raw.get('title')!r}")
    print(f"entities: {evidence.raw.get('entities')}")
    print(f"relations: {evidence.raw.get('relations')}")

    _section("QUALITY")
    print("计算质量评分")
    print("(由 IngestionService 内部 Quality 完成)")
    print(f"quality_score: {evidence.quality_score}")

    _section("EVIDENCE")
    print("生成 Evidence:")
    print(_dump(evidence))

    _section("REPOSITORY")
    print("IngestionService 已调用 EvidenceRepository.save")
    loaded_evidence = await evidence_repo.get(evidence.id)
    assert loaded_evidence is not None, "Evidence 未写入 MockEvidenceRepository"
    print(f"回读 Evidence OK: id={loaded_evidence.id}")

    # --- Preference (Service only) ---
    _section("PREFERENCE")
    print("PreferenceService 开始提取")

    _section("EXTRACTOR")
    print("提取用户偏好")
    print("(由 PreferenceService 内部 Extractor 完成；demo 未直接调用 Extractor)")

    prefs = await preference.extract(evidence)

    _section("PREFERENCE RESULT")
    print("生成 Preference:")
    if not prefs:
        print("(空) — 当前规则未命中偏好信号")
    else:
        print(_dump(prefs))

    _section("REPOSITORY")
    print("PreferenceService 已调用 PreferenceRepository.save")
    for pref in prefs:
        loaded = await pref_repo.get(pref.id)
        assert loaded is not None, f"Preference 未写入: {pref.id}"
        print(f"回读 Preference OK: id={loaded.id} key={loaded.key} version={loaded.version}")

    # --- Knowledge (Service only; already runnable) ---
    _section("KNOWLEDGE")
    print("KnowledgeService 开始处理")
    print("内部约定管线: Structurer → GraphBuilder → EmbedWriter → KnowledgeRepository.save")

    item = await knowledge.structure(evidence)

    print("\nStructurer 结果:")
    print(
        _dump(
            {
                "id": item.id,
                "kind": item.kind,
                "title": item.title,
                "body": item.body,
                "status": item.status,
                "evidence_ids": item.evidence_ids,
            }
        )
    )

    entities = await entity_repo.list_entities()
    relations = await entity_repo.list_relations()
    print("\nGraph 结果:")
    print(_dump({"entities": entities, "relations": relations}))

    print("\nEmbedding 结果:")
    print(
        _dump(
            {
                "embedding_ref": item.embedding_ref,
                "embedder": "MockEmbedding",
                "note": "真实 Kylin SDK 未接入；向量以 embedding_ref 形式挂在 KnowledgeItem",
            }
        )
    )

    loaded_knw = await knw_repo.get(item.id)
    assert loaded_knw is not None, "KnowledgeItem 未写入 MockKnowledgeRepository"
    print(f"\n回读 KnowledgeItem OK: id={loaded_knw.id}")

    # --- Full mock storage dump (read-back verification) ---
    _section("STORAGE RESULT")
    print("打印当前 MockRepository 中保存的全部数据")
    storage = {
        "evidence": [loaded_evidence.model_dump()] if loaded_evidence else [],
        "preferences": [
            (await pref_repo.get(p.id)).model_dump()  # type: ignore[union-attr]
            for p in prefs
        ],
        "knowledge_items": [i.model_dump() for i in await knw_repo.list_active()],
        "entities": [e.model_dump() for e in entities],
        "relations": [r.model_dump() for r in relations],
    }
    print(_dump(storage))

    print("\n========== PIPELINE END ==========")

    return {
        "evidence": evidence,
        "preferences": prefs,
        "knowledge": item,
        "storage": storage,
    }


def main() -> None:
    # Stabilize Unicode logs on Windows consoles
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    result = asyncio.run(run_pipeline())
    # Exit non-zero if preference path produced nothing (demo expectation)
    if not result["preferences"]:
        print("\n[WARN] Preference 列表为空，写入链路部分成功但偏好未提取。", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
