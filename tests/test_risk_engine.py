from datetime import date, timedelta
from pathlib import Path

from ultimate_stock_analyzer.market.prices import PriceBar
from ultimate_stock_analyzer.risk.engine import RiskConfig, analyze_risk

CONFIG = RiskConfig.from_yaml(Path("config/risk/risk_liquidity_v0.9.yml"))


def _bars(*, stressed: bool, adjusted: bool = True) -> list[PriceBar]:
    start = date(2025, 1, 1)
    price = 100.0
    output: list[PriceBar] = []
    for index in range(180):
        if stressed and index in {60, 61, 62, 120, 121}:
            price *= 0.88
        else:
            price *= 1.0005 + (0.001 if index % 2 == 0 else -0.0008)
        output.append(
            PriceBar(
                ticker="TEST3",
                trade_date=start + timedelta(days=index),
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                close=price,
                adjusted_close=price if adjusted else None,
                volume=2_000_000.0,
                trades=500,
                quantity=100_000,
            )
        )
    return output


def test_stressed_history_has_lower_risk_safety_score() -> None:
    calm = analyze_risk(_bars(stressed=False), config=CONFIG)
    stressed = analyze_risk(_bars(stressed=True), config=CONFIG)
    assert calm.rankable and stressed.rankable
    assert stressed.risk_safety_score < calm.risk_safety_score
    assert stressed.metrics["max_drawdown"] < calm.metrics["max_drawdown"]


def test_unadjusted_risk_history_is_visible_and_less_confident() -> None:
    adjusted = analyze_risk(_bars(stressed=False, adjusted=True), config=CONFIG)
    raw = analyze_risk(_bars(stressed=False, adjusted=False), config=CONFIG)
    assert "UNADJUSTED_RISK_SERIES" in raw.flags
    assert raw.confidence < adjusted.confidence
