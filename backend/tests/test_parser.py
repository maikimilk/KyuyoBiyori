from backend.app.ocr.simple_totals import TotalsOnlyParser


def test_parse_totals():
    parser = TotalsOnlyParser()
    data = "支給合計 200\n控除合計 50\n差引支給額 150".encode()
    result = parser.parse(data)
    assert result.gross == 200
    assert result.deduction == 50
    assert result.net == 150


def test_parse_without_gross():
    parser = TotalsOnlyParser()
    data = "控除合計 20\n差引支給額 80".encode()
    result = parser.parse(data)
    assert result.gross == 100
    assert result.net == 80
    assert result.deduction == 20
