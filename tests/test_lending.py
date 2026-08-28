from ultimate_stock_analyzer.lending.metrics import rental_opportunity_score, short_pressure_score, utilization


def test_lending_signals_are_separate() -> None:
    util = utilization(20_000_000, 100_000_000)
    assert util == 0.2
    rental = rental_opportunity_score(0.12, util)
    short = short_pressure_score(util, 0.05, 0.12)
    assert rental > 90
    assert short > 50
