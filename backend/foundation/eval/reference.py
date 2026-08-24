"""Versioned synthetic acceptance dataset derived from the competition scenario."""

from __future__ import annotations

from .models import CaseKind, EvalCase, EvalDataset


_QUERY_TEMPLATES = (
    "{month}月的家庭支出清单记录了哪些支出",
    "查询{month}月份 utilities 花费",
    "{month}月的水电燃气总共支出了多少金额",
    "统计{month}月水电燃气费用的总额",
    "{month}月水电燃气总共花了多少",
)


def _expense_fixture(index: int) -> tuple[dict, EvalCase]:
    month = ((index - 1) % 12) + 1
    electricity = 180.0 + index * 2.0
    water = 45.0 + index * 0.5
    gas = 110.0 + index * 1.5
    total = round(electricity + water + gas, 2)
    knowledge_id = f"knw-expense-{index:02d}"
    evidence_id = f"evd-expense-{index:02d}"
    start = f"2026-{month:02d}-01"
    end_month = month + 1
    end_year = 2026
    if end_month == 13:
        end_month = 1
        end_year = 2027
    end = f"{end_year}-{end_month:02d}-01"
    fixture = {
        "knowledge_id": knowledge_id,
        "evidence_id": evidence_id,
        "kind": "FACT",
        "title": f"2026年{month}月家庭支出清单-{index:02d}",
        "scope": "shared:home",
        "body": {
            "items": [
                {
                    "category": "房租",
                    "vendor": "物业公司",
                    "amount": round(300.0 + index, 2),
                    "date": f"2026-{month:02d}-03",
                    "tags": ["房租"],
                },
                {
                    "category": "水电燃气",
                    "vendor": "国家电网",
                    "amount": electricity,
                    "date": f"2026-{month:02d}-10",
                    "tags": ["电费"],
                },
                {
                    "category": "水电燃气",
                    "vendor": "市自来水公司",
                    "amount": water,
                    "date": f"2026-{month:02d}-12",
                    "tags": ["水费"],
                },
                {
                    "category": "水电燃气",
                    "vendor": "燃气集团",
                    "amount": gas,
                    "date": f"2026-{month:02d}-15",
                    "tags": ["燃气费"],
                },
            ]
        },
        "entities": ["国家电网", "市自来水公司", "燃气集团", "水电燃气"],
        "relations": [
            {"from": "国家电网", "to": "水电燃气", "type": "BELONG_TO"},
            {"from": "市自来水公司", "to": "水电燃气", "type": "BELONG_TO"},
            {"from": "燃气集团", "to": "水电燃气", "type": "BELONG_TO"},
        ],
    }
    query = _QUERY_TEMPLATES[(index - 1) % len(_QUERY_TEMPLATES)].format(month=month)
    case = EvalCase(
        id=f"retrieval-{index:02d}",
        task=CaseKind.RETRIEVAL,
        input={
            "text": query,
            "context_hint": {
                "scope": "shared:home",
                "time_range": {"start": start, "end": end},
                "top_k": 1,
            },
        },
        expected={
            "knowledge_ids": [knowledge_id],
            "evidence_ids": [evidence_id],
            "aggregate_amount": total,
            "amount_tolerance": 0.01,
            "top_k": 1,
        },
        tags=["family-expense", "semantic-query"],
    )
    return fixture, case


def build_reference_dataset() -> EvalDataset:
    """Build the stable v1 acceptance corpus: 50 groups and 1000 retrieval runs."""

    fixtures: list[dict] = []
    cases: list[EvalCase] = []
    for index in range(1, 51):
        fixture, case = _expense_fixture(index)
        fixtures.append(fixture)
        cases.append(case)

    preference_specs = (
        ("OP_HABIT", "tool.selection.frequent"),
        ("OUTPUT_STYLE", "output_style.compact"),
        ("SECURITY_POLICY", "security.confirm_sensitive"),
    )
    for index in range(15):
        category, key = preference_specs[index % len(preference_specs)]
        cases.append(
            EvalCase(
                id=f"preference-{index + 1:02d}",
                task=CaseKind.PREFERENCE,
                input={"sample": index + 1, "category": category, "key": key},
                expected={"labels": [f"{category}:{key}"]},
                tags=["preference", category.lower()],
            )
        )

    for index in range(25):
        resolution = "NEW_WINS" if index < 20 else ("MERGE" if index < 23 else "MANUAL")
        cases.append(
            EvalCase(
                id=f"conflict-{index + 1:02d}",
                task=CaseKind.CONFLICT,
                input={"old": index, "new": index + 1, "scenario": resolution.lower()},
                expected={"resolution": resolution},
                tags=["conflict", resolution.lower()],
            )
        )

    return EvalDataset(
        schema_version="1.0",
        name="pixiu-family-expense-v1",
        description=(
            "Synthetic acceptance corpus derived from OriginProblemDescription Appendix A; "
            "50 expense fixtures, semantic golden queries, preference cases, and conflicts."
        ),
        profile="acceptance",
        retrieval_repetitions=20,
        fixtures=fixtures,
        cases=cases,
        metadata={
            "source": "docs/OriginProblemDescription.md Appendix A",
            "synthetic": True,
            "retrieval_groups": 50,
            "retrieval_samples": 1000,
        },
    )
