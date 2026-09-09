def test_conversational_correction_keeps_other_items_and_dates():
    from backend.engine.ingest.expense_draft import correct_expense_body
    original = {"items": [{"vendor": "新奥燃气", "date": "2026-04-01", "amount": 156},
                          {"vendor": "电费", "date": "2026-04-01", "amount": 210}]}
    corrected = correct_expense_body(original, "燃气费改为186元")
    assert corrected["items"][0]["amount"] == 186
    assert corrected["items"][0]["date"] == "2026-04-01"
    assert corrected["items"][1] == original["items"][1]
    assert original["items"][0]["amount"] == 156
