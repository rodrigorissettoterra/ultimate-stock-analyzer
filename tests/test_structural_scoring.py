from pathlib import Path

import pytest

from ultimate_stock_analyzer.scoring.normalization import (
    peer_adjusted_percentile_rank,
    percentile_rank,
)
from ultimate_stock_analyzer.scoring.structural import (
    StructuralScoringConfig,
    StructuralScoringEngine,
)

CONFIG = Path("config/scoring/structural_v0.5.yml")


def _row(ticker: str, sector: str, scale: float) -> dict[str, float | str]:
    return {
        "ticker": ticker,
        "sector": sector,
        "roic": 0.10 * scale,
        "roe": 0.12 * scale,
        "roa": 0.06 * scale,
        "ebit_margin": 0.10 * scale,
        "net_margin": 0.07 * scale,
        "net_debt_ebitda": 3.0 / scale,
        "interest_coverage": 3.0 * scale,
        "debt_to_equity": 1.5 / scale,
        "equity_ratio": 0.30 * scale,
        "cash_to_debt": 0.20 * scale,
        "cash_conversion": 1.0,
        "fcf_margin": 0.08 * scale,
        "cfo_margin": 0.10 * scale,
        "operating_cash_flow_to_debt": 0.20 * scale,
        "revenue_cagr_5y": 0.05 * scale,
        "net_income_cagr_5y": 0.04 * scale,
        "fcf_cagr_5y": 0.04 * scale,
        "dividend_regularity": 60.0 + 10.0 * scale,
        "dividend_sustainability": 55.0 + 10.0 * scale,
        "dividend_cagr_5y": 0.03 * scale,
        "dy_ttm": 0.01 * scale,
        "valuation_score": 100.0 / scale,
        "entry_score": 100.0 / scale,
    }


def test_percentile_rank_uses_average_rank_for_ties() -> None:
    scores = percentile_rank({"A": 1.0, "B": 1.0, "C": 2.0, "D": 3.0})

    assert scores["A"] == pytest.approx(100.0 / 6.0)
    assert scores["B"] == pytest.approx(100.0 / 6.0)
    assert scores["C"] == pytest.approx(200.0 / 3.0)
    assert scores["D"] == pytest.approx(100.0)


def test_small_peer_groups_are_shrunk_toward_neutral() -> None:
    scores, reliability = peer_adjusted_percentile_rank(
        {"A": 1.0, "B": 2.0, "C": 3.0},
        min_peer_count=5,
    )

    assert reliability == pytest.approx(0.5)
    assert scores["A"] == pytest.approx(25.0)
    assert scores["B"] == pytest.approx(50.0)
    assert scores["C"] == pytest.approx(75.0)


def test_structural_score_is_independent_from_price_and_entry_signals() -> None:
    config = StructuralScoringConfig.from_yaml(CONFIG)
    engine = StructuralScoringEngine(config)
    rows = [_row(f"AAA{index}", "Industrial", float(index)) for index in range(1, 9)]
    baseline = engine.score_universe(rows)

    changed = [dict(row) for row in rows]
    changed[-1]["dy_ttm"] = 0.99
    changed[-1]["valuation_score"] = 0.0
    changed[-1]["entry_score"] = 0.0
    rescored = engine.score_universe(changed)

    baseline_score = {item.ticker: item.structural_score for item in baseline}
    rescored_score = {item.ticker: item.structural_score for item in rescored}
    assert baseline_score == rescored_score


def test_structural_ranking_rewards_stronger_peer_and_tracks_coverage() -> None:
    config = StructuralScoringConfig.from_yaml(CONFIG)
    engine = StructuralScoringEngine(config)
    rows = [_row(f"AAA{index}", "Industrial", float(index)) for index in range(1, 9)]

    ranking = engine.rank_universe(rows)

    assert ranking[0].ticker == "AAA8"
    assert ranking[0].structural_score > ranking[-1].structural_score
    assert ranking[0].data_coverage == pytest.approx(1.0)
    assert ranking[0].confidence == pytest.approx(1.0)


def test_low_coverage_company_is_not_rankable() -> None:
    config = StructuralScoringConfig.from_yaml(CONFIG)
    engine = StructuralScoringEngine(config)
    rows = [_row(f"AAA{index}", "Industrial", float(index)) for index in range(1, 9)]
    rows[0] = {
        "ticker": "AAA1",
        "sector": "Industrial",
        "roic": 0.10,
        "roe": 0.12,
    }

    scored = {item.ticker: item for item in engine.score_universe(rows)}

    assert not scored["AAA1"].rankable
    assert "LOW_STRUCTURAL_DATA_COVERAGE" in scored["AAA1"].flags
