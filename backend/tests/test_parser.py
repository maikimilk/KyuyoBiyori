from backend.app.routers.payslip import _parse_text, _categorize_items


def test_parse_trailing_number_removed_and_small_amount_skip():
    text = "口座振込額1 123\n手当2\n5"
    result = _parse_text(text)
    items = result["items"]
    assert any(it.name == "口座振込額" and it.amount == 123 for it in items)
    assert all(it.amount >= 10 or it.amount <= -10 for it in items)


def test_parse_split_lines():
    text = "基本給\n200000"
    result = _parse_text(text)
    items = result["items"]
    assert any(it.name == "基本給" and it.amount == 200000 for it in items)


def test_metadata_skipped():
    text = "社員番号 4020\n氏名 山田太郎\n基本給 100000"
    result = _parse_text(text)
    items = result["items"]
    assert all(it.name != "社員番号" and it.name != "氏名" for it in items)
    assert any(it.name == "基本給" and it.amount == 100000 for it in items)


def test_amount_first_pattern():
    text = "-12345 雇用保険料"
    result = _parse_text(text)
    items = result["items"]
    assert any(it.name == "雇用保険料" and it.amount == -12345 for it in items)


def test_quantity_unit_as_attendance():
    text = "日 10\n基本給 100000"
    result = _parse_text(text)
    assert result["attendance"].get("日") == 10
    items = _categorize_items(result["items"])
    assert any(it.name == "基本給" for it in items)


def test_item_line_pattern_with_amount_at_end():
    text = "通勤費補助 12,860"
    result = _parse_text(text)
    items = _categorize_items(result["items"])
    assert any(it.name == "通勤費補助" and it.amount == 12860 for it in items)
    assert any(it.name == "通勤費補助" and it.category == "payment" for it in items)


def test_amount_first_with_pending_name_queue():
    text = "課税対象額\n口座振込額1\n135,545 雇保対象額\n218,919\n148,405"
    result = _parse_text(text)
    names = [it.name for it in result["items"]]
    amounts = [it.amount for it in result["items"]]
    assert names == ["課税対象額", "口座振込額", "雇保対象額"]
    assert amounts == [135545, 218919, 148405]
    assert all(it.name for it in result["items"])


def test_amount_only_with_unit_and_pending_name():
    text = "所定労働日数\n21日\n基本給 100000"
    result = _parse_text(text)
    assert result["attendance"].get("所定労働日数") == 21
    items = _categorize_items(result["items"])
    assert any(it.name == "基本給" for it in items)


def test_totals_not_in_items():
    text = "基本給 100000\n支給合計 100000\n控除合計 0\n差引支給額 100000"
    result = _parse_text(text)
    names = [it.name for it in result["items"]]
    assert names == ["基本給"]
    assert result["gross_amount"] == 100000
    assert result["net_amount"] == 100000
    assert result["deduction_amount"] == 0

def test_section_assignment():
    text = "支給項目\n本給 100000\n控除項目\n所得税 -5000\n勤怠項目\n欠勤日数 2"
    result = _parse_text(text)
    items = result["items"]
    sections = {it.name: it.section for it in items}
    assert sections.get("本給") == "payment"
    assert sections.get("所得税") == "deduction"
    assert result["attendance"].get("欠勤日数") == 2
