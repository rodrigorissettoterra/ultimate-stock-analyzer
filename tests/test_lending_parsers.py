import pytest

from ultimate_stock_analyzer.lending.parsers import (
    parse_lending_open_position_csv,
    parse_loan_balance_csv,
)


def test_parse_official_loan_balance_tags_and_rates() -> None:
    text = (
        "RptDt;TckrSymb;ISIN;Asst;QtyCtrctsDay;QtyShrDay;ValCtrctsDay;"
        "DnrMinRate;DnrAvrgRate;DnrMaxRate;TakrMinRate;TakrAvrgRate;TakrMaxRate;MktNm\n"
        "2026-03-26;TEST3;BRTESTACNOR1;TEST;9;27351;30086,10;0,30;0,56;0,60;0,30;0,56;0,60;Registro\n"
    )
    record = parse_loan_balance_csv(text)[0]
    assert record.ticker == "TEST3"
    assert record.contracts_day == 9
    assert record.shares_day == 27351
    assert record.value_day == pytest.approx(30086.10)
    assert record.donor_avg_rate == pytest.approx(0.0056)
    assert record.taker_avg_rate == pytest.approx(0.0056)


def test_parse_open_position_does_not_confuse_stock_with_daily_flow() -> None:
    text = (
        "RptDt;TckrSymb;ISIN;Asst;BalQty;TradAvrgPric;PricFctr;BalVal;MktNm\n"
        "26/03/2026;TEST3;BRTESTACNOR1;TEST;448479;2,8418;1;1274490,36;Total\n"
    )
    record = parse_lending_open_position_csv(text)[0]
    assert record.balance_quantity == 448479
    assert record.balance_value == pytest.approx(1274490.36)
    assert record.market == "Total"
