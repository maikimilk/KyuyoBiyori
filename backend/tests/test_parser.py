import pytest
from backend.app.routers.payslip import _categorize_items, _parse_text


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


def test_multi_pair_and_section_category():
    text = "支給項目\n本給 269000 通勤費補助 12860\n控除項目\n東友会費 300 共済会費 200"
    result = _parse_text(text)
    items = _categorize_items(result["items"])
    categories = {it.name: it.category for it in items}
    assert categories.get("本給") == "payment"
    assert categories.get("通勤費補助") == "payment"
    assert categories.get("東友会費") == "deduction"
    assert categories.get("共済会費") == "deduction"
    assert len(items) == 4


def test_section_with_colon_and_split_lines():
    text = "支給項目:\n本給\n269000\n控除項目：\n所得税\n2460"
    result = _parse_text(text)
    items = {it.name: (it.amount, it.section) for it in result["items"]}
    assert items.get("本給") == (269000, "payment")
    assert items.get("所得税") == (2460, "deduction")


def test_real_world_ocr_1():
    text = """
2025年4月分 給与支給明細書
三菱電機ディフェンス&スペーステクノロジーズ株式会社

社員番号 4020
氏名   石川 聖幸

支給項目:
本給
269,000
通勤費補助   12,860    その他(非課) 74,390
控除項目：
所得税
2,460
雇用保険料  816  東友会費 300  共済会費 200 社員会費 100
就業項目
所定日数21日
不在籍 10 日
休残(日)  20日

支給合計
222,795
控除合計
3,876

差引支給額
218,919

当月欄
課税対象額
135,545 雇保対象額218,919 148,405
年間累計欄 (賞与額 翌月反映 )
当月総支給額累計
87,250
当月非課税額累計 816
当月社会保険累計 2,460
当月所得税累計
222,795
無関係な数字 999999

備考欄
例：銀行引落など
"""
    result = _parse_text(text)
    items = {it.name: it.amount for it in result["items"]}
    categories = {it.name: it.category for it in result["items"]}
    attendance = result["attendance"]

    assert items.get("本給") == 269000
    assert items.get("通勤費補助") == 12860
    assert items.get("その他(非課)") == 74390
    assert items.get("所得税") == 2460
    assert items.get("雇用保険料") == 816
    assert items.get("東友会費") == 300
    assert items.get("共済会費") == 200
    assert items.get("社員会費") == 100
    assert attendance.get("所定日数") == 21
    assert attendance.get("不在籍") == 10
    assert attendance.get("休残(日)") == 20
    assert categories.get("本給") == "payment"
    assert categories.get("所得税") == "deduction"


def test_real_world_ocr_2():
    text = """
支給項目:  本給 269,000  通勤費補助 12,860
控除項目:  所得税 2,460  雇用保険料 816
控除項目: 東友会費300 共済会費200 社員会費 100
不明な文字列 これは明細ではない
支給合計  222,795
差引支給額: 218,919
"""
    result = _parse_text(text)
    items = {it.name: it.amount for it in result["items"]}
    categories = {it.name: it.category for it in result["items"]}

    assert items.get("本給") == 269000
    assert items.get("通勤費補助") == 12860
    assert items.get("所得税") == 2460
    assert items.get("雇用保険料") == 816
    assert items.get("東友会費") == 300
    assert items.get("共済会費") == 200
    assert items.get("社員会費") == 100
    assert categories.get("本給") == "payment"
    assert categories.get("東友会費") == "deduction"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("\uFFE5\uFF12\uFF16\uFF19,\uFF10\uFF10\uFF10 \u672C\u7D66", ("本給", 269000)),
        ("(2,460) 所得税", ("所得税", -2460)),
        ("+12,860 通勤費補助", ("通勤費補助", 12860)),
    ],
)
def test_amount_variations(raw, expected):
    result = _parse_text(raw)
    items = {it.name: it.amount for it in result["items"]}
    name, amount = expected
    assert items.get(name) == amount


def test_unit_before_number():
    text = "日 21 所定労働日数"
    result = _parse_text(text)
    assert result["attendance"].get("所定労働日数") == 21


def test_duplicate_item_names():
    text = "時間外手当 30000\n時間外手当 15000"
    result = _parse_text(text)
    names = [it.name for it in result["items"]]
    amounts = [it.amount for it in result["items"]]
    assert names == ["時間外手当", "時間外手当"]
    assert amounts == [30000, 15000]


def test_amount_overflow_noise():
    text = "111,111,111,111 本給"
    result = _parse_text(text)
    assert not result["items"]


def test_halfwidth_kana_headers():
    text = "ｼｷｭｳｺｳﾓｸ\n本給 100000"
    result = _parse_text(text)
    items = result["items"]
    assert items and items[0].section == "payment"


def test_line_break_between_unit_and_number():
    text = "所定日数\n21\n日"
    result = _parse_text(text)
    assert result["attendance"].get("所定日数") == 21


def test_section_header_omitted():
    text = "所得税 2460 本給 269000"
    result = _parse_text(text)
    items = _categorize_items(result["items"])
    mapping = {it.name: it.category for it in items}
    assert mapping.get("所得税") == "deduction"
    assert mapping.get("本給") == "payment"


def test_column_header_row_crush():
    """横並びヘッダが行単位で現れてもアイテムを拾える"""
    text = "支給項目\n控除項目\n就業項目\n本給 269,000"
    result = _parse_text(text)
    names = [it.name for it in result["items"]]
    assert "本給" in names


def test_header_repeated_without_amount():
    text = "支給項目\n支給項目\n本給 100000"
    result = _parse_text(text)
    names = [it.name for it in result["items"]]
    assert "本給" in names


def test_amount_before_any_section():
    text = "本給 269000\n所得税 2460"
    result = _parse_text(text)
    items = _categorize_items(result["items"])
    mapping = {it.name: it.category for it in items}
    assert mapping.get("本給") == "payment"
    assert mapping.get("所得税") == "deduction"


def test_totals_in_different_block():
    text = "本給 269000\n年間累計欄\n当月総支給額累計 222,795"
    result = _parse_text(text)
    names = [it.name for it in result["items"]]
    assert names == ["本給"]
    assert result["deduction_amount"] is None


def test_multi_pair_line_not_dropped():
    text = "通勤費補助 12,860  その他(非課) 74,390"
    result = _parse_text(text)
    mapping = {it.name: it.amount for it in result["items"]}
    assert mapping["通勤費補助"] == 12860
    assert mapping["その他(非課)"] == 74390


def test_section_attendance_flush():
    text = "就業項目\n不在籍\n10 日\n休残(日) 20日"
    result = _parse_text(text)
    assert result["attendance"]["不在籍"] == 10
    assert result["attendance"]["休残(日)"] == 20
    assert "不在籍" not in [it.name for it in result["items"]]


def test_attendance_not_items():
    text = "就業項目\n不在籍 10 日\n所定日数 21日"
    result = _parse_text(text)
    assert "不在籍" not in [it.name for it in result["items"]]
    assert result["attendance"]["不在籍"] == 10
    assert result["attendance"]["所定日数"] == 21


def test_amount_unit_space():
    text = "残業時間  5 時間"
    result = _parse_text(text)
    assert result["attendance"]["残業時間"] == 5


def test_total_line_strict():
    text = "当月社会保険累計 2,460\n支給合計 222,795\n差引支給額 218,919"
    result = _parse_text(text)
    assert result["gross_amount"] == 222795
    assert result["net_amount"] == 218919
    assert result["deduction_amount"] is None
