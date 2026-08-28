from datetime import date, timedelta
from pathlib import Path

from ultimate_stock_analyzer.lending.engine import LendingConfig, analyze_lending
from ultimate_stock_analyzer.lending.models import (
    LendingOpenPositionRecord,
    LoanBalanceRecord,
)

CONFIG = LendingConfig.from_yaml(Path("config/lending/lending_v1.1.yml"))


def _open_history(*, rising: bool) -> list[LendingOpenPositionRecord]:
    start = date(2026, 1, 1)
    records: list[LendingOpenPositionRecord] = []
    for index in range(25):
        quantity = 5_000_000 + (index * 250_000 if rising else 0)
        records.append(
            LendingOpenPositionRecord(
                report_date=start + timedelta(days=index),
                ticker="TEST3",
                isin="BRTESTACNOR1",
                asset="TEST",
                balance_quantity=quantity,
                trade_average_price=10.0,
                price_factor=1.0,
                balance_value=quantity * 10.0,
                market="Total",
            )
        )
    return records


def _flow(report_date: date, rate: float) -> list[LoanBalanceRecord]:
    return [
        LoanBalanceRecord(
            report_date=report_date,
            ticker="TEST3",
            isin="BRTESTACNOR1",
            asset="TEST",
            market="Registro",
            contracts_day=50,
            shares_day=500_000,
            value_day=5_000_000.0,
            donor_min_rate=rate * 0.9,
            donor_avg_rate=rate,
            donor_max_rate=rate * 1.1,
            taker_min_rate=rate * 0.9,
            taker_avg_rate=rate,
            taker_max_rate=rate * 1.1,
        )
    ]


def test_lending_keeps_income_opportunity_and_short_pressure_separate() -> None:
    open_history = _open_history(rising=True)
    flows = _flow(open_history[-1].report_date, 0.12)
    result = analyze_lending(
        flows,
        open_history,
        free_float_shares=50_000_000,
        config=CONFIG,
    )
    assert result.rankable
    assert result.rental_opportunity_score > 70
    assert result.short_pressure_risk > 50
    assert result.metrics["loan_utilization"] is not None
    assert result.metrics["utilization_change_20_observations"] is not None


def test_missing_free_float_does_not_invent_utilization() -> None:
    open_history = _open_history(rising=False)
    flows = _flow(open_history[-1].report_date, 0.08)
    result = analyze_lending(flows, open_history, free_float_shares=None, config=CONFIG)
    assert result.metrics["loan_utilization"] is None
    assert "FREE_FLOAT_UNAVAILABLE" in result.flags
    assert not result.rankable
