from datetime import date, timedelta
from pathlib import Path

from ultimate_stock_analyzer.market.entry import EntryConfig, EntryStatus, analyze_entry
from ultimate_stock_analyzer.market.prices import PriceBar

CONFIG = EntryConfig.from_yaml(Path("config/market/entry_v0.8.yml"))


def _history(*, adjusted: bool = True, spike: bool = False) -> list[PriceBar]:
    start = date(2025, 1, 1)
    closes = [100.0 + index * 0.05 + (0.20 if index % 2 == 0 else -0.20) for index in range(260)]
    if spike:
        for offset in range(5, 0, -1):
            index = len(closes) - offset
            previous = closes[index - 1]
            closes[index] = previous * 1.06
    bars: list[PriceBar] = []
    for index, close in enumerate(closes):
        volume = 1_000_000.0
        if spike and index == len(closes) - 1:
            volume = 5_000_000.0
        bars.append(
            PriceBar(
                ticker="TEST3",
                trade_date=start + timedelta(days=index),
                open=close * 0.995,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                adjusted_close=close if adjusted else None,
                volume=volume,
                trades=1000,
                quantity=100000,
            )
        )
    return bars


def test_speculative_spike_raises_risk_and_reduces_entry_score() -> None:
    normal = analyze_entry(
        _history(),
        config=CONFIG,
        valuation_score=80.0,
        valuation_confidence=0.90,
        material_event_explained=False,
    )
    spike = analyze_entry(
        _history(spike=True),
        config=CONFIG,
        valuation_score=80.0,
        valuation_confidence=0.90,
        material_event_explained=False,
    )

    assert spike.speculation_risk > normal.speculation_risk
    assert spike.entry_score < normal.entry_score
    assert "HIGH_SPECULATION_RISK" in spike.flags
    assert spike.status == EntryStatus.EXTENDED_SPECULATIVE


def test_confirmed_material_event_reduces_but_does_not_erase_spike_risk() -> None:
    unexplained = analyze_entry(
        _history(spike=True),
        config=CONFIG,
        valuation_score=80.0,
        material_event_explained=False,
    )
    explained = analyze_entry(
        _history(spike=True),
        config=CONFIG,
        valuation_score=80.0,
        material_event_explained=True,
    )

    assert 0 < explained.speculation_risk < unexplained.speculation_risk


def test_raw_b3_series_is_flagged_instead_of_claiming_adjustment() -> None:
    result = analyze_entry(
        _history(adjusted=False),
        config=CONFIG,
        valuation_score=75.0,
        material_event_explained=False,
    )
    assert "UNADJUSTED_PRICE_SERIES" in result.flags
    assert result.confidence < 1.0


def test_short_history_abstains() -> None:
    result = analyze_entry(
        _history()[:30],
        config=CONFIG,
        valuation_score=None,
        material_event_explained=None,
    )
    assert not result.rankable
    assert result.status == EntryStatus.INSUFFICIENT_DATA
