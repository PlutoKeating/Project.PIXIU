from backend.engine.ingest.expense_draft import expense_draft


def test_bill_draft_excludes_total_and_carries_date():
    assert expense_draft("2026年4月\n燃气费 156元\n电费 ￥210.00\n合计 366元") == [
        {"date": "2026-04-01", "category": "水电燃气", "vendor": "燃气费", "amount": 156.0},
        {"date": "2026-04-01", "category": "水电燃气", "vendor": "电费", "amount": 210.0},
    ]


def test_unknown_lines_are_left_for_user_review():
    assert expense_draft("账单\n2026年4月\n123456\n合计 100") == []
