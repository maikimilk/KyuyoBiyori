from backend.app.routers.payslip import _parse_text


def test_parse_trailing_number_removed_and_small_amount_skip():
    text = "口座振込額1 123\n手当2\n5"
    result = _parse_text(text)
    items = result['items']
    assert any(it.name == '口座振込額' and it.amount == 123 for it in items)
    assert all(it.amount >= 10 or it.amount <= -10 for it in items)


def test_parse_split_lines():
    text = "基本給\n200000"
    result = _parse_text(text)
    items = result['items']
    assert any(it.name == '基本給' and it.amount == 200000 for it in items)

