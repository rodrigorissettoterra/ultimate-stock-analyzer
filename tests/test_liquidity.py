from datetime import date, timedelta
from pathlib import Path

from ultimate_stock_analyzer.market.prices import PriceBar
from ultimate_stock_analyzer.risk.liquidity import (
    LiquidityConfig,
    analyze_liquidity,
    days_to_liquidate,
)

CONFIG = LiquidityConfig.from_yaml(Path("config/risk/risk_liquidity_v0.9.yml"))


def _bars(*, liquid: bool) -> list[PriceBar]:
    start = date(2026, 1, 1)
    output: list[PriceBar] = []
    for index in range(60):
        price = 20.0 + index * 0.01
        if liquid:
            volume = 25_000_000.0
            trades = 2500
            quantity = 1_500_000
            bid = price - 0.01
            ask = price + 0.01
        else:
            volume = 150_000.0
            trades = 20
            quantity = 5_000
            bid = price - 0.30
            ask = price + 0.30
        output.append(
            PriceBar(
                ticker="TEST3",
                trade_date=start + timedelta(days=index),
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                close=price,
                volume=volume,
                trades=trades,
                quantity=quantity,
                best_bid=bid,
                best_ask=ask,
            )
        )
    return output


def test_liquid_security_scores_higher_than_illiquid_security() -> None:
    liquid = analyze_liquidity(_bars(liquid=True), config=CONFIG, free_float_shares=150_000_000)
    illiquid = analyze_liquidity(_bars(liquid=False), config=CONFIG, free_float_shares=150_000_000)
    assert liquid.rankable and illiquid.rankable
    assert liquid.liquidity_score > illiquid.liquidity_score
    assert liquid.metrics["spread_pct_latest"] < illiquid.metrics["spread_pct_latest"]


def test_days_to_liquidate_uses_explicit_participation_limit() -> None:
    assert days_to_liquidate(1_000_000.0, 10_000_000.0, max_participation_rate=0.10) == 1.0
