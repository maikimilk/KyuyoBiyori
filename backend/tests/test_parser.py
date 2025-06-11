from backend.app.ocr.simple_totals import TotalsOnlyParser


def test_parse_totals():
    parser = TotalsOnlyParser()
    data = "支給合計 200\n控除合計 50\n差引支給額 150".encode()
    result = parser.parse(data)
    assert result.gross == 200
    assert result.deduction == 50
    assert result.net == 150
    assert result.paid_leave_remaining_days is None
    assert result.total_paid_leave_days is None


def test_parse_without_gross():
    parser = TotalsOnlyParser()
    data = "控除合計 20\n差引支給額 80".encode()
    result = parser.parse(data)
    assert result.gross == 100
    assert result.net == 80
    assert result.deduction == 20


def test_parse_without_deduction():
    parser = TotalsOnlyParser()
    data = "支給合計 120\n差引支給額 100".encode()
    result = parser.parse(data)
    assert result.gross == 120
    assert result.deduction == 20
    assert result.net == 100


def test_parse_without_net():
    parser = TotalsOnlyParser()
    data = "支給合計 120\n控除合計 20".encode()
    result = parser.parse(data)
    assert result.gross == 120
    assert result.deduction == 20
    assert result.net == 100


def test_parse_fullwidth_digits():
    parser = TotalsOnlyParser()
    data = "支給合計 １００，０００\n控除合計 ２０，０００\n差引支給額 ８０，０００".encode()
    result = parser.parse(data)
    assert result.gross == 100000
    assert result.deduction == 20000
    assert result.net == 80000


def test_parse_items():
    parser = TotalsOnlyParser()
    data = (
        "支給項目\n"
        "本給 100\n"
        "控除項目\n"
        "健康保険料 10\n"
        "支給合計 100\n"
        "控除合計 10\n"
        "差引支給額 90"
    ).encode()
    result = parser.parse(data)
    assert any(i.name == "本給" and i.amount == 100 and i.category == "支給" for i in result.items)
    assert any(i.name == "健康保険料" and i.amount == 10 and i.category == "控除" for i in result.items)


