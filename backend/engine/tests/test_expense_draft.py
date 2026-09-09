from backend.engine.ingest.expense_draft import expense_draft


def test_bill_draft_excludes_total_and_carries_date():
    assert expense_draft("2026年4月\n燃气费 156元\n电费 ￥210.00\n合计 366元") == [
        {"date": "2026-04-01", "category": "水电燃气", "vendor": "燃气费", "amount": 156.0},
        {"date": "2026-04-01", "category": "水电燃气", "vendor": "电费", "amount": 210.0},
    ]


def test_unknown_lines_are_left_for_user_review():
    assert expense_draft("账单\n2026年4月\n123456\n合计 100") == []


def test_conversational_correction_keeps_other_items_and_dates():
    from backend.engine.ingest.expense_draft import correct_expense_body
    original = {"items": [{"vendor": "新奥燃气", "date": "2026-04-01", "amount": 156},
                          {"vendor": "电费", "date": "2026-04-01", "amount": 210}]}
    corrected = correct_expense_body(original, "燃气费改为186元")
    assert corrected["items"][0]["amount"] == 186
    assert corrected["items"][0]["date"] == "2026-04-01"
    assert corrected["items"][1] == original["items"][1]
    assert original["items"][0]["amount"] == 156
